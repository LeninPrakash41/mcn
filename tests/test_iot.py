"""
device(): the registry, simulation, and each hardware driver, tested without
hardware (gpiozero's mock pins, a fake serial board, a fake MQTT client and a
local HTTP server).
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import iot  # noqa: E402
from mcn.core_engine.mcn_interpreter import MCNInterpreter  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(iot, "_SHARED", None)
    monkeypatch.setattr(iot, "_WARNED", set())
    monkeypatch.setenv("MCN_IOT_SIMULATE", "0")      # hardware drivers must really load in these tests
    yield
    iot._SerialLink._links.clear()
    iot.MQTTDriver._clients.clear()


def run(code):
    interp = MCNInterpreter()
    interp.execute(code, quiet=True)
    return interp.variables


# ── Registry and simulation ─────────────────────────────────────────────────

def test_simulated_devices_read_write_and_coerce(monkeypatch):
    monkeypatch.setenv("MCN_IOT_SIMULATE", "1")
    v = run('device("register", "t", {type: "temperature_sensor"})\n'
            'device("register", "lamp", {type: "light"})\n'
            'device("register", "arm", {type: "servo"})\n'
            'var temp = device("read", "t").value\n'
            'device("on", "lamp")\n'
            'device("write", "arm", 500)\n'
            'device("command", "lamp", {command: "toggle"})\n'
            'var lamp = device("read", "lamp").value\n'
            'var arm = device("read", "arm").value')
    assert 15 < v["temp"] < 30
    assert v["lamp"] == 0 and v["arm"] == 180          # toggled back off; servo clamped to 0-180


def test_inputs_cant_be_set_and_unknown_devices_explain(monkeypatch):
    monkeypatch.setenv("MCN_IOT_SIMULATE", "1")
    with pytest.raises(Exception) as err:
        run('device("register", "t", {type: "temperature_sensor"})\ndevice("write", "t", 5)')
    assert "can be read but not set" in str(err.value)
    with pytest.raises(Exception) as err:
        run('var x = device("read", "missing")')
    assert 'device("register", "missing"' in str(err.value)


def test_studio_pin_holds_inputs_and_survives_reregister(monkeypatch):
    monkeypatch.setenv("MCN_IOT_SIMULATE", "1")
    reg = iot.shared_registry()
    reg.register("door", {"type": "door_sensor"})
    reg.pin("door", 1)
    reg.register("door", {"type": "door_sensor"})       # pressing Run again keeps the panel's value
    assert reg.read("door") == 1
    reg.pin("door", None)
    assert reg.read("door") == 0


def test_watch_calls_handler_on_change(monkeypatch):
    monkeypatch.setenv("MCN_IOT_SIMULATE", "1")
    v = run('var seen = []\n'
            'function on_motion(value, previous)\n'
            '    seen.push([value, previous])\n'
            'device("register", "pir", {type: "motion_sensor"})\n'
            'device("watch", "pir", on_motion, 0.05)')
    reg = iot.shared_registry()
    reg.pin("pir", 1)
    time.sleep(0.3)
    reg.pin("pir", 0)
    time.sleep(0.3)
    assert v["seen"] == [[1, 0], [0, 1]]


def test_missing_hardware_falls_back_unless_strict(monkeypatch, capsys):
    monkeypatch.setenv("MCN_IOT_SIMULATE", "")
    monkeypatch.setattr(iot._SerialLink, "_find_port", staticmethod(lambda: (_ for _ in ()).throw(iot.HardwareError("no Arduino found on USB"))))
    d = iot.shared_registry().register("pump", {"type": "relay", "driver": "serial", "pin": 7})
    assert d.simulated and "no Arduino" in d.note
    iot.shared_registry().register("pump2", {"type": "relay", "driver": "serial", "pin": 8})
    assert capsys.readouterr().out.count("No Arduino found") == 1          # one warning per reason
    monkeypatch.setenv("MCN_IOT_SIMULATE", "0")
    with pytest.raises(iot.HardwareError):
        iot.shared_registry().register("pump3", {"type": "relay", "driver": "serial", "pin": 9})


# ── Raspberry Pi GPIO (gpiozero mock pins) ──────────────────────────────────

@pytest.fixture
def mock_pins():
    gpiozero = pytest.importorskip("gpiozero")
    from gpiozero.pins.mock import MockFactory, MockPWMPin
    old = gpiozero.Device.pin_factory
    gpiozero.Device.pin_factory = MockFactory(pin_class=MockPWMPin)
    yield gpiozero.Device.pin_factory
    gpiozero.Device.pin_factory.reset()
    gpiozero.Device.pin_factory = old


def test_gpio_outputs_and_inputs(mock_pins):
    reg = iot.shared_registry()
    reg.register("fan", {"type": "relay", "driver": "gpio", "pin": 17})
    reg.register("dim", {"type": "dimmer", "driver": "gpio", "pin": 18})
    reg.register("pir", {"type": "motion_sensor", "driver": "gpio", "pin": 4})
    assert not reg.get("fan").simulated
    reg.command("fan", "on")
    assert mock_pins.pin(17).state == 1
    reg.write("dim", 50)
    assert mock_pins.pin(18).state == pytest.approx(0.5)
    mock_pins.pin(4).drive_high()
    assert reg.read("pir") == 1


def test_gpio_analog_needs_an_adc(mock_pins):
    with pytest.raises(iot.HardwareError) as err:
        iot.shared_registry().register("soil", {"type": "soil_moisture", "driver": "gpio", "pin": 5})
    assert "mcp3008" in str(err.value)


# ── Arduino over USB (a fake board speaking the firmware protocol) ──────────

class FakeBoard:
    """Answers like mcn_firmware.ino."""
    def __init__(self, *a, **k):
        self.pins = {"A0": 512, "7": 0}
        self.out = [b"MCN READY 1\n"]
        self.sent = []

    def write(self, data):
        line = data.decode().strip()
        self.sent.append(line)
        op, *args = line.split()
        if op == "R":
            self.out.append(f"OK {self.pins.get(args[0], 0)}\n".encode())
        elif op in ("W", "P", "S"):
            self.pins[args[0]] = int(args[1])
            self.out.append(f"OK {args[1]}\n".encode())
        else:
            self.out.append(b"ERR unknown command\n")

    def readline(self):
        return self.out.pop(0) if self.out else b""


def test_serial_reads_scales_and_writes(monkeypatch):
    serial = pytest.importorskip("serial")
    board = FakeBoard()
    monkeypatch.setattr(serial, "Serial", lambda *a, **k: board)
    reg = iot.shared_registry()
    reg.register("soil", {"type": "soil_moisture", "driver": "serial", "port": "/dev/fake", "pin": "A0", "scale": [0, 100]})
    reg.register("pump", {"type": "relay", "driver": "serial", "port": "/dev/fake", "pin": 7})
    reg.register("lamp", {"type": "dimmer", "driver": "serial", "port": "/dev/fake", "pin": 9})
    assert reg.read("soil") == pytest.approx(50.05, abs=0.01)
    reg.command("pump", "on")
    reg.write("lamp", 100)
    assert board.sent[-2:] == ["W 7 1", "P 9 255"]
    assert reg.read("pump") == 1


# ── MQTT (a fake paho client) ───────────────────────────────────────────────

class FakeMQTT:
    def __init__(self, *a, **k):
        self.callbacks, self.published = {}, []

    def username_pw_set(self, *a): pass
    def tls_set(self): pass
    def connect(self, host, port): self.where = (host, port)
    def loop_start(self): pass
    def subscribe(self, topic): pass
    def message_callback_add(self, topic, fn): self.callbacks[topic] = fn
    def message_callback_remove(self, topic): self.callbacks.pop(topic, None)
    def publish(self, topic, payload): self.published.append((topic, payload))

    def deliver(self, topic, payload):
        msg = type("Msg", (), {"payload": payload.encode(), "topic": topic})()
        self.callbacks[topic](self, None, msg)


def test_mqtt_state_and_commands(monkeypatch):
    mqtt = pytest.importorskip("paho.mqtt.client")
    fake = FakeMQTT()
    monkeypatch.setattr(mqtt, "Client", lambda *a, **k: fake)
    reg = iot.shared_registry()
    reg.register("soil", {"type": "soil_moisture", "driver": "mqtt", "broker": "mqtt://broker:1883", "scale": [0, 100]})
    reg.register("porch", {"type": "light", "driver": "mqtt", "broker": "mqtt://broker:1883", "topic": "home/porch"})
    reg.register("climate", {"type": "temperature_sensor", "driver": "mqtt", "broker": "mqtt://broker:1883",
                             "topic": "zigbee/climate", "field": "temperature"})
    fake.deliver("mcn/soil", "4095")
    fake.deliver("zigbee/climate", json.dumps({"temperature": 21.5, "battery": 90}))
    assert reg.read("soil") == 100 and reg.read("climate") == 21.5
    reg.command("porch", "on")
    assert fake.published[-1] == ("home/porch/set", "ON")
    fake.deliver("home/porch/state", "OFF")
    assert reg.read("porch") == 0
    assert fake.where == ("broker", 1883)


# ── HTTP ────────────────────────────────────────────────────────────────────

def test_http_reads_json_and_posts_values():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"value": 42.5}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a): pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/"
    reg = iot.shared_registry()
    reg.register("tank", {"type": "distance_sensor", "driver": "http", "url": url})
    reg.register("valve", {"type": "relay", "driver": "http", "url": url})
    assert reg.read("tank") == 42.5
    reg.command("valve", "on")
    srv.shutdown()
    assert received == [{"value": 1}]


# ── Studio ↔ backend bridge ─────────────────────────────────────────────────

def test_dev_routes_need_dev_mode_and_token(monkeypatch):
    from mcn.core_engine.mcn_server import _dev_iot
    monkeypatch.setenv("MCN_IOT_SIMULATE", "1")
    iot.shared_registry().register("lamp", {"type": "light"})
    monkeypatch.delenv("MCN_DEV_TOOLS", raising=False)
    assert _dev_iot("GET", "/_mcn/iot/devices", {}, None)[0] == 404
    monkeypatch.setenv("MCN_DEV_TOOLS", "1")
    monkeypatch.setenv("MCN_API_TOKEN", "dev")
    assert _dev_iot("GET", "/_mcn/iot/devices", {}, "Bearer nope")[0] == 401
    status, body = _dev_iot("POST", "/_mcn/iot/value", {"device_id": "lamp", "value": 1}, "Bearer dev")
    assert status == 200 and iot.shared_registry().read("lamp") == 1
    assert "lamp" in _dev_iot("GET", "/_mcn/iot/devices", {}, "Bearer dev")[1]["devices"]
    assert _dev_iot("GET", "/health", {}, None) is None


# ── mcn iot ─────────────────────────────────────────────────────────────────

def test_firmware_and_service_files(tmp_path, monkeypatch):
    from mcn.core_engine import iot_cli
    assert iot_cli.firmware("arduino", str(tmp_path)) == 0
    sketch = (tmp_path / "mcn_firmware" / "mcn_firmware.ino").read_text()
    assert "MCN READY" in sketch and "OK " in sketch
    assert iot_cli.firmware("esp32", str(tmp_path)) == 0
    assert "PubSubClient" in (tmp_path / "mcn_esp32" / "mcn_esp32.ino").read_text()
    app = tmp_path / "home.mcn"
    app.write_text("service home\n    endpoint a()\n        return 1\n")
    monkeypatch.chdir(tmp_path)
    assert iot_cli.service(str(app)) == 0
    unit = (tmp_path / "mcn-home.service").read_text()
    assert "serve home.mcn --host 0.0.0.0" in unit and "MCN_IOT_SIMULATE=0" in unit


@pytest.mark.skipif(not __import__("shutil").which("arduino-cli"), reason="needs arduino-cli with the arduino:avr core")
def test_arduino_firmware_compiles():
    import subprocess
    sketch = ROOT / "mcn" / "iot_firmware" / "mcn_firmware"
    proc = subprocess.run(["arduino-cli", "compile", "-b", "arduino:avr:uno", str(sketch)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
