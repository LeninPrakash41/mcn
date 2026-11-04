"""
Devices for MCN programs.

The same `device(...)` code runs simulated in Studio and drives real hardware:

    device("register", "fan", {type: "relay", driver: "gpio", pin: 17})          // Raspberry Pi pin
    device("register", "soil", {type: "soil_moisture", driver: "serial", pin: "A0", scale: [0, 100]})  // Arduino over USB
    device("register", "porch", {type: "light", driver: "mqtt", topic: "home/porch"})                 // ESP32, Tasmota, Home Assistant
    device("register", "tank", {type: "distance_sensor", driver: "http", url: "http://10.0.0.7/level"})

MCN_IOT_SIMULATE decides what happens to hardware drivers:
  1      always simulate (Studio sets this)
  0      always use hardware; a missing board or library is an error
  unset  use hardware when it's there, otherwise simulate and say so once
"""
from __future__ import annotations

import json
import math
import os
import random
import threading
import time
import urllib.request
from collections import deque
from typing import Any, Callable, Dict, List, Optional

# type → (kind, unit, default, min, max)
TYPES: Dict[str, tuple] = {
    "temperature_sensor": ("sensor", "°C", 22.5, -10, 50),
    "humidity_sensor":    ("sensor", "%", 45.0, 0, 100),
    "light_sensor":       ("sensor", "lux", 300, 0, 1000),
    "distance_sensor":    ("sensor", "cm", 100, 2, 400),
    "soil_moisture":      ("sensor", "%", 40, 0, 100),
    "gas_sensor":         ("sensor", "ppm", 400, 0, 2000),
    "pressure_sensor":    ("sensor", "hPa", 1013, 900, 1100),
    "power_meter":        ("sensor", "W", 120, 0, 3000),
    "analog_sensor":      ("sensor", "", 512, 0, 1023),
    "motion_sensor":      ("binary_sensor", "", 0, 0, 1),
    "button":             ("binary_sensor", "", 0, 0, 1),
    "door_sensor":        ("binary_sensor", "", 0, 0, 1),
    "digital_input":      ("binary_sensor", "", 0, 0, 1),
    "led":                ("switch", "", 0, 0, 1),
    "light":              ("switch", "", 0, 0, 1),
    "relay":              ("switch", "", 0, 0, 1),
    "fan":                ("switch", "", 0, 0, 1),
    "pump":               ("switch", "", 0, 0, 1),
    "lock":               ("switch", "", 0, 0, 1),
    "buzzer":             ("switch", "", 0, 0, 1),
    "switch":             ("switch", "", 0, 0, 1),
    "digital_output":     ("switch", "", 0, 0, 1),
    "dimmer":             ("level", "%", 0, 0, 100),
    "pwm":                ("level", "%", 0, 0, 100),
    "motor":              ("level", "%", 0, 0, 100),
    "servo":              ("level", "°", 90, 0, 180),
    "hvac_controller":    ("text", "", "idle", None, None),
    "display":            ("text", "", "", None, None),
}

DRIVERS = ("simulated", "gpio", "serial", "mqtt", "http")
_ON = {"1", "on", "true", "yes", "high", "open", "active", "detected"}


class HardwareError(Exception):
    """A device couldn't be reached. The message says what to check."""


def _mode() -> str:
    v = os.getenv("MCN_IOT_SIMULATE", "").strip().lower()
    return "simulate" if v in ("1", "true", "yes") else "strict" if v in ("0", "false", "no") else "auto"


def _coerce(kind: str, value: Any, lo=None, hi=None) -> Any:
    if kind in ("switch", "binary_sensor"):
        if isinstance(value, str):
            return 1 if value.strip().lower() in _ON else 0
        return 1 if value else 0
    if kind in ("sensor", "level"):
        if isinstance(value, bool):
            value = int(value)
        number = float(value)
        if kind == "level" and lo is not None:
            number = max(lo, min(hi, number))
        return int(number) if number.is_integer() else round(number, 2)
    return "" if value is None else str(value)


def _scale(device: "Device", raw: float, raw_max: float) -> float:
    """scale: [lo, hi] maps a board's raw 0..raw_max reading onto lo..hi."""
    scale = device.config.get("scale")
    if isinstance(scale, (list, tuple)) and len(scale) == 2:
        top = float(device.config.get("raw_max", raw_max)) or raw_max
        return round(scale[0] + raw / top * (scale[1] - scale[0]), 2)
    return raw


# ── Drivers ─────────────────────────────────────────────────────────────────

class SimulatedDriver:
    """Sensors drift around a believable value; outputs remember what they were set to."""
    name = "simulated"

    def __init__(self, device: "Device"):
        self.device = device
        self.phase = random.random() * math.tau

    def read(self) -> Any:
        d = self.device
        if d.kind == "sensor":
            lo, hi = d.min, d.max
            span = (hi - lo) if lo is not None else 10
            t = time.time()
            wave = math.sin(t / 90 + self.phase) * span * 0.04 + math.sin(t / 7 + self.phase) * span * 0.005
            return _coerce("sensor", round(d.default + wave, 1))
        if d.kind == "binary_sensor":
            return d.default             # resting state until Studio's panel triggers it
        return d.value if d.value is not None else d.default

    def write(self, value: Any) -> None:
        pass

    def close(self) -> None:
        pass


_DHT_SENSORS: Dict[Any, Any] = {}


class GPIODriver:
    """Raspberry Pi pins through gpiozero (BCM numbering: pin 17 is GPIO17)."""
    name = "gpio"

    def __init__(self, device: "Device"):
        try:
            import gpiozero  # noqa: F401
        except ImportError:
            raise HardwareError("the gpio driver needs a Raspberry Pi with IoT support. On the Pi, run: mcn add iot")
        c, d = device.config, device
        self.device, self.dht = device, None
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")          # gpiozero warns about each pin library it tries
            self._open(c, d)

    def _open(self, c: dict, d: "Device") -> None:
        if "pin" not in c and c.get("adc") != "mcp3008":
            raise HardwareError(f"'{d.id}' needs a pin, e.g. {{driver: \"gpio\", pin: 17}}")
        try:
            pin = c.get("pin")
            if d.kind == "binary_sensor":
                from gpiozero import Button, DigitalInputDevice, MotionSensor
                if d.type == "motion_sensor":
                    self.io = MotionSensor(pin)
                elif d.type == "button":
                    self.io = Button(pin, pull_up=bool(c.get("pull_up", True)))
                else:
                    self.io = DigitalInputDevice(pin, pull_up=c.get("pull_up"))
            elif d.kind == "switch":
                from gpiozero import DigitalOutputDevice
                self.io = DigitalOutputDevice(pin, active_high=bool(c.get("active_high", True)))
            elif d.type == "servo":
                from gpiozero import AngularServo
                self.io = AngularServo(pin, min_angle=d.min, max_angle=d.max)
            elif d.kind == "level":
                from gpiozero import PWMOutputDevice
                self.io = PWMOutputDevice(pin)
            elif str(c.get("sensor", "")).lower() in ("dht22", "dht11"):
                import adafruit_dht
                import board
                cls = adafruit_dht.DHT22 if str(c["sensor"]).lower() == "dht22" else adafruit_dht.DHT11
                if pin not in _DHT_SENSORS:      # temperature and humidity often share one sensor
                    _DHT_SENSORS[pin] = cls(getattr(board, f"D{pin}"))
                self.dht = _DHT_SENSORS[pin]
                self.io = None
            elif c.get("adc") == "mcp3008":
                from gpiozero import MCP3008
                self.io = MCP3008(channel=int(c.get("channel", 0)))
            else:
                raise HardwareError(f"Raspberry Pi pins are digital, so '{d.id}' can't read {d.type} directly. "
                                    "Use sensor: \"dht22\", adc: \"mcp3008\", or an Arduino (driver: \"serial\")")
        except HardwareError:
            raise
        except ImportError as exc:
            if exc.name:
                raise HardwareError(f"the {exc.name} library isn't installed (on the Pi, run: mcn add iot)")
            raise HardwareError("there are no Raspberry Pi GPIO pins here")
        except Exception as exc:   # gpiozero raises BadPinFactory etc. off a Pi
            if type(exc).__name__ in ("BadPinFactory", "PinFactoryFallback"):
                raise HardwareError("there are no Raspberry Pi GPIO pins here")
            raise HardwareError(f"couldn't open GPIO pin {c.get('pin')} for '{d.id}': {exc}")

    def read(self) -> Any:
        d = self.device
        if self.dht is not None:
            try:
                return _coerce("sensor", self.dht.temperature if d.type == "temperature_sensor" else self.dht.humidity)
            except RuntimeError:          # DHT sensors miss reads now and then
                return d.value
        if d.type == "servo":
            return _coerce("level", self.io.angle or 0)
        if d.kind == "level":
            return _coerce("level", self.io.value * 100)
        if d.kind == "sensor":           # MCP3008: 0..1 scaled to the type's range
            return _coerce("sensor", d.min + self.io.value * (d.max - d.min))
        return 1 if self.io.value else 0

    def write(self, value: Any) -> None:
        d = self.device
        if d.kind == "switch":
            self.io.on() if value else self.io.off()
        elif d.type == "servo":
            self.io.angle = value
        elif d.kind == "level":
            self.io.value = value / 100
        else:
            raise HardwareError(f"'{d.id}' is an input; it can't be set")

    def close(self) -> None:
        if getattr(self, "io", None) is not None:
            self.io.close()


class _SerialLink:
    """One USB connection to a board running the MCN firmware (`mcn iot firmware arduino`)."""
    _links: Dict[str, "_SerialLink"] = {}
    _guard = threading.Lock()

    @classmethod
    def open(cls, port: str, baud: int) -> "_SerialLink":
        with cls._guard:
            port = cls._find_port() if port in ("", "auto", None) else port
            if port not in cls._links:
                cls._links[port] = cls(port, baud)
            return cls._links[port]

    @staticmethod
    def _find_port() -> str:
        from serial.tools import list_ports
        for p in list_ports.comports():
            text = f"{p.device} {p.description} {p.manufacturer or ''}".lower()
            if any(k in text for k in ("arduino", "usbmodem", "ttyacm", "ttyusb", "ch340", "cp210", "esp32", "usbserial")):
                return p.device
        raise HardwareError("no Arduino found on USB. Plug it in, or set port: \"/dev/ttyACM0\" (see: mcn iot ports)")

    def __init__(self, port: str, baud: int):
        import serial
        self.port, self.lock = port, threading.Lock()
        try:
            self.conn = serial.Serial(port, baud, timeout=2)
        except Exception as exc:
            raise HardwareError(f"couldn't open {port}: {exc}")
        deadline = time.time() + 4          # most boards reset when the port opens
        while time.time() < deadline:
            line = self.conn.readline().decode(errors="replace").strip()
            if line.startswith("MCN READY"):
                return
        self.request("HELLO")               # boards that don't reset answer straight away

    def request(self, line: str) -> str:
        with self.lock:
            self.conn.write((line + "\n").encode())
            deadline = time.time() + 3
            while time.time() < deadline:
                reply = self.conn.readline().decode(errors="replace").strip()
                if reply.startswith("OK"):
                    return reply[2:].strip()
                if reply.startswith("ERR"):
                    raise HardwareError(f"the board on {self.port} said: {reply[3:].strip()}")
        raise HardwareError(f"no answer from {self.port}. Is the MCN firmware uploaded? (mcn iot firmware arduino)")


class SerialDriver:
    """Arduino, ESP32 or Pico over USB, running the MCN firmware."""
    name = "serial"

    def __init__(self, device: "Device"):
        try:
            import serial  # noqa: F401
        except ImportError:
            raise HardwareError("the serial driver needs IoT support. Run: mcn add iot")
        c = device.config
        if "pin" not in c:
            raise HardwareError(f"'{device.id}' needs a pin, e.g. {{driver: \"serial\", pin: \"A0\"}}")
        self.device, self.pin = device, str(c["pin"]).upper()
        self.link = _SerialLink.open(c.get("port", "auto"), int(c.get("baud", 115200)))

    def read(self) -> Any:
        d, c = self.device, self.device.config
        sensor = str(c.get("sensor", "")).lower()
        if sensor in ("dht22", "dht11"):
            raw = float(self.link.request(f"D {self.pin} {'T' if d.type == 'temperature_sensor' else 'H'}"))
            return _coerce("sensor", raw)
        raw = float(self.link.request(f"R {self.pin}"))
        if d.kind in ("binary_sensor", "switch"):
            return 1 if raw else 0
        return _coerce("sensor", _scale(d, raw, 1023))

    def write(self, value: Any) -> None:
        d = self.device
        if d.kind == "switch":
            self.link.request(f"W {self.pin} {1 if value else 0}")
        elif d.type == "servo":
            self.link.request(f"S {self.pin} {int(value)}")
        elif d.kind == "level":
            self.link.request(f"P {self.pin} {round(value / 100 * 255)}")
        else:
            raise HardwareError(f"'{d.id}' is an input; it can't be set")

    def close(self) -> None:
        pass


class MQTTDriver:
    """Anything on an MQTT broker: ESP32/ESP8266 (`mcn iot firmware esp32`), Tasmota, Zigbee2MQTT, Home Assistant."""
    name = "mqtt"
    _clients: Dict[str, Any] = {}
    _guard = threading.Lock()

    def __init__(self, device: "Device"):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise HardwareError("the mqtt driver needs IoT support. Run: mcn add iot")
        c = device.config
        self.device = device
        self.topic = c.get("topic") or f"mcn/{device.id}"
        self.command_topic = c.get("command_topic") or f"{self.topic}/set"
        self.state_topic = c.get("state_topic") or (self.topic if device.kind not in ("switch", "level", "text") else f"{self.topic}/state")
        self.payload_on, self.payload_off = str(c.get("payload_on", "ON")), str(c.get("payload_off", "OFF"))
        self.last: Any = None
        url = c.get("broker") or os.getenv("MCN_MQTT_URL", "mqtt://localhost:1883")
        self.client = self._client(mqtt, url, c)
        self.client.message_callback_add(self.state_topic, self._on_message)
        self.client.subscribe(self.state_topic)

    @classmethod
    def _client(cls, mqtt, url: str, c: dict):
        with cls._guard:
            if url not in cls._clients:
                from urllib.parse import urlparse
                u = urlparse(url if "://" in url else f"mqtt://{url}")
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"mcn-{os.getpid()}-{random.randint(0, 9999)}")
                user = u.username or c.get("username") or os.getenv("MCN_MQTT_USER")
                if user:
                    client.username_pw_set(user, u.password or c.get("password") or os.getenv("MCN_MQTT_PASSWORD"))
                if u.scheme == "mqtts":
                    client.tls_set()
                try:
                    client.connect(u.hostname or "localhost", u.port or (8883 if u.scheme == "mqtts" else 1883))
                except Exception as exc:
                    raise HardwareError(f"couldn't reach the MQTT broker at {url}: {exc}")
                client.loop_start()
                cls._clients[url] = client
            return cls._clients[url]

    def _on_message(self, _client, _userdata, msg) -> None:
        text = msg.payload.decode(errors="replace").strip()
        field = self.device.config.get("field")
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = data.get(field or "value", data.get("state"))
        except ValueError:
            data = text
        if self.device.kind in ("switch", "binary_sensor") and isinstance(data, str):
            data = 1 if data.upper() == self.payload_on.upper() or data.lower() in _ON else 0
        elif self.device.kind == "sensor":
            try:
                data = _scale(self.device, float(data), 4095)    # ESP32 ADCs read 0..4095
            except (TypeError, ValueError):
                pass
        try:
            self.last = _coerce(self.device.kind, data, self.device.min, self.device.max)
        except (TypeError, ValueError):
            self.last = data

    def read(self) -> Any:
        return self.last if self.last is not None else self.device.value

    def write(self, value: Any) -> None:
        d = self.device
        payload = (self.payload_on if value else self.payload_off) if d.kind == "switch" else str(value)
        self.client.publish(self.command_topic, payload)
        if d.kind in ("switch", "level", "text"):
            self.last = value

    def close(self) -> None:
        self.client.message_callback_remove(self.state_topic)


class HTTPDriver:
    """A device with an HTTP API: GET url reads it, POST {value} to write_url (or url) sets it."""
    name = "http"

    def __init__(self, device: "Device"):
        if not device.config.get("url"):
            raise HardwareError(f"'{device.id}' needs a url, e.g. {{driver: \"http\", url: \"http://10.0.0.7/temp\"}}")
        self.device = device

    def read(self) -> Any:
        c = self.device.config
        try:
            with urllib.request.urlopen(c["url"], timeout=5) as res:
                text = res.read().decode(errors="replace").strip()
        except Exception as exc:
            raise HardwareError(f"couldn't read {c['url']}: {exc}")
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = data.get(c.get("field") or "value")
        except ValueError:
            data = text
        return _coerce(self.device.kind, data, self.device.min, self.device.max)

    def write(self, value: Any) -> None:
        c = self.device.config
        req = urllib.request.Request(c.get("write_url") or c["url"], data=json.dumps({"value": value}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=5).close()
        except Exception as exc:
            raise HardwareError(f"couldn't set {c.get('write_url') or c['url']}: {exc}")

    def close(self) -> None:
        pass


_WARNED: set = set()

_DRIVER_CLASSES = {"simulated": SimulatedDriver, "gpio": GPIODriver, "serial": SerialDriver,
                   "mqtt": MQTTDriver, "http": HTTPDriver}


# ── Devices and the registry ────────────────────────────────────────────────

class Device:
    def __init__(self, device_id: str, config: Dict[str, Any]):
        self.id = device_id
        self.config = dict(config or {})
        self.type = str(self.config.get("type") or "digital_output")
        kind, unit, default, lo, hi = TYPES.get(self.type, ("text", "", "idle", None, None))
        self.kind = str(self.config.get("kind") or kind)
        self.unit = str(self.config.get("unit", unit))
        self.min = self.config.get("min", lo)
        self.max = self.config.get("max", hi)
        self.default = self.config.get("default", default)
        self.value: Any = self.default
        self.override: Any = None
        self.updated_at = time.time()
        self.note = ""
        wanted = str(self.config.get("driver") or "simulated").lower()
        if wanted not in _DRIVER_CLASSES:
            raise HardwareError(f"unknown driver '{wanted}' for '{device_id}'. Use one of: {', '.join(DRIVERS)}")
        self.driver_name = wanted
        self.driver = self._open(wanted)

    def _open(self, wanted: str):
        if wanted == "simulated" or _mode() == "simulate":
            return SimulatedDriver(self)
        try:
            return _DRIVER_CLASSES[wanted](self)
        except HardwareError as exc:
            if _mode() == "strict":
                raise
            self.note = f"simulated: {exc}"
            if str(exc) not in _WARNED:          # one line per reason, not per device
                _WARNED.add(str(exc))
                print(f"[iot] {str(exc)[0].upper() + str(exc)[1:]}, so devices that need it are simulated. "
                      "Set MCN_IOT_SIMULATE=0 to make this an error.")
            return SimulatedDriver(self)

    @property
    def simulated(self) -> bool:
        return isinstance(self.driver, SimulatedDriver)

    @property
    def writable(self) -> bool:
        return self.kind in ("switch", "level", "text")

    def info(self) -> Dict[str, Any]:
        where = {k: self.config[k] for k in ("pin", "port", "topic", "url", "channel", "sensor") if k in self.config}
        return {"type": self.type, "kind": self.kind, "value": self.value, "unit": self.unit,
                "min": self.min, "max": self.max, "driver": self.driver_name, "simulated": self.simulated,
                "pinned": self.override is not None, "writable": self.writable, "where": where,
                "location": self.config.get("location"), "note": self.note, "updated_at": self.updated_at}


class DeviceRegistry:
    """Every device this process knows about. Studio's IoT panel reads and drives it."""

    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.command_log: deque = deque(maxlen=200)
        self.lock = threading.RLock()
        self.watchers: Dict[str, List[dict]] = {}
        self._watch_thread: Optional[threading.Thread] = None

    def register(self, device_id: str, config: Optional[Dict[str, Any]] = None) -> Device:
        if not device_id:
            raise HardwareError("a device needs an id: device(\"register\", \"fan\", {type: \"relay\"})")
        with self.lock:
            old = self.devices.get(device_id)
            if old is not None:
                old.driver.close()
                self.watchers.pop(device_id, None)   # running the script again re-adds its watches
            device = Device(str(device_id), config or {})
            if old is not None and old.override is not None and device.simulated:
                device.override = old.override       # keep what the simulator pinned across reruns
            self.devices[device.id] = device
            return device

    def get(self, device_id: str) -> Device:
        device = self.devices.get(device_id)
        if device is None:
            raise HardwareError(f"no device named '{device_id}'. Register it first: "
                                f"device(\"register\", \"{device_id}\", {{type: \"temperature_sensor\"}})")
        return device

    def read(self, device_id: str) -> Any:
        device = self.get(device_id)
        with self.lock:
            value = device.override if device.override is not None else device.driver.read()
            if value is not None:
                device.value = value
            device.updated_at = time.time()
            return device.value

    def write(self, device_id: str, value: Any, source: str = "code") -> Any:
        device = self.get(device_id)
        if not device.writable:
            if source == "simulator":
                return self.pin(device_id, value)
            raise HardwareError(f"'{device_id}' is a {device.type}, so it can be read but not set")
        value = _coerce(device.kind, value, device.min, device.max)
        with self.lock:
            device.driver.write(value)
            device.value, device.updated_at = value, time.time()
            self.command_log.append({"timestamp": device.updated_at, "device_id": device_id,
                                     "command": "set", "params": {"value": value, "source": source}})
        self._check_soon(device_id)
        return value

    def command(self, device_id: str, command: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """on / off / toggle / set (with value) for outputs; anything else is recorded for text devices."""
        device = self.get(device_id)
        params = dict(params or {})
        command = str(command or "set").lower()
        if device.kind == "switch" and command in ("on", "off", "toggle"):
            value = 1 if command == "on" else 0 if command == "off" else (0 if device.value else 1)
        elif "value" in params:
            value = params["value"]
        elif device.kind == "text":
            value = params.get("mode", command)
        else:
            value = None
        if value is not None and device.writable:
            self.write(device_id, value, source=params.get("source", "code"))
            self.command_log[-1].update({"command": command, "params": params})
        else:
            self.command_log.append({"timestamp": time.time(), "device_id": device_id, "command": command, "params": params})
        return device.value

    def pin(self, device_id: str, value: Any) -> Any:
        """Studio: hold an input at a value (None goes back to the simulated reading)."""
        device = self.get(device_id)
        with self.lock:
            device.override = None if value is None or value == "" else _coerce(device.kind, value, device.min, device.max)
            if device.override is not None:
                device.value = device.override
            device.updated_at = time.time()
        self._check_soon(device_id)
        return device.override

    def _check_soon(self, device_id: str) -> None:
        for w in self.watchers.get(device_id, []):
            w["due"] = 0.0

    def remove(self, device_id: str) -> bool:
        with self.lock:
            device = self.devices.pop(device_id, None)
            self.watchers.pop(device_id, None)
        if device:
            device.driver.close()
        return device is not None

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            out = {}
            for device_id, device in list(self.devices.items()):
                if device.kind in ("sensor", "binary_sensor"):
                    try:
                        self.read(device_id)
                    except Exception as exc:
                        device.note = str(exc)
                out[device_id] = device.info()
            return out

    # Watching: call a function when a reading changes
    def watch(self, device_id: str, handler: Callable, interval: float = 0.5) -> None:
        device = self.get(device_id)
        with self.lock:
            self.watchers.setdefault(device_id, []).append(
                {"fn": handler, "interval": max(0.05, float(interval)), "last": device.value, "due": 0.0})
            if self._watch_thread is None or not self._watch_thread.is_alive():
                self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True, name="mcn-iot-watch")
                self._watch_thread.start()

    def _watch_loop(self) -> None:
        while self.watchers:
            now = time.time()
            for device_id, items in list(self.watchers.items()):
                for w in items:
                    if now < w["due"]:
                        continue
                    w["due"] = now + w["interval"]
                    try:
                        value = self.read(device_id)
                    except Exception:
                        continue
                    if value != w["last"]:
                        previous, w["last"] = w["last"], value
                        _call(w["fn"], value, previous, device_id)
            time.sleep(0.05)

    # Names the rest of MCN used before this module existed
    def register_device(self, device_id: str, device_type: str, connection_info: Optional[Dict] = None) -> str:
        self.register(device_id, {**(connection_info or {}), "type": device_type})
        return f"Device '{device_id}' registered as {device_type}"

    def read_device(self, device_id: str) -> Any:
        return self.read(device_id)

    def send_command(self, device_id: str, command: str, params: Optional[Dict] = None) -> str:
        self.command(device_id, command, params)
        return f"Command '{command}' sent to device '{device_id}'"

    def set_override(self, device_id: str, value: Any) -> Any:
        return self.pin(device_id, value)


def _call(fn: Callable, value: Any, previous: Any, device_id: str) -> None:
    """Call a watch handler with as many of (value, previous, id) as it takes."""
    params = getattr(fn, "mcn_params", None)
    count = len(params) if params is not None else 3
    try:
        fn(*[value, previous, device_id][:max(1, count)])
    except Exception as exc:
        print(f"[iot] watch handler for '{device_id}' failed: {exc}")


_SHARED: Optional[DeviceRegistry] = None


def shared_registry() -> DeviceRegistry:
    """One registry per process, shared by every script run and Studio's panel."""
    global _SHARED
    if _SHARED is None:
        _SHARED = DeviceRegistry()
    return _SHARED


def device(operation: str, device_id: Any = None, config: Any = None, extra: Any = None) -> Any:
    """The `device(...)` built-in."""
    reg = shared_registry()
    op = str(operation or "").lower()
    if op == "register":
        if isinstance(config, str):
            config = {"type": config}
        d = reg.register(str(device_id), config or {})
        return {"success": True, "device": d.info(), "message": f"Device '{d.id}' registered as {d.type}"}
    if op == "read":
        value = reg.read(str(device_id))
        d = reg.get(str(device_id))
        return {"value": value, "unit": d.unit, "at": d.updated_at}
    if op in ("write", "set"):
        value = config.get("value") if isinstance(config, dict) else config
        return {"success": True, "value": reg.write(str(device_id), value)}
    if op == "command":
        params = config if isinstance(config, dict) else {"value": config}
        value = reg.command(str(device_id), params.get("command", "set"), params)
        return {"success": True, "value": value, "message": f"Command '{params.get('command', 'set')}' sent to '{device_id}'"}
    if op in ("on", "off", "toggle"):
        return {"success": True, "value": reg.command(str(device_id), op)}
    if op == "list":
        return reg.snapshot()
    if op == "watch":
        if not callable(config):
            raise HardwareError("watch needs a function: device(\"watch\", \"door\", on_door)")
        reg.watch(str(device_id), config, float(extra) if extra else 0.5)
        return {"success": True}
    if op == "remove":
        return {"success": reg.remove(str(device_id))}
    raise HardwareError(f"unknown device operation '{operation}'. Use register, read, write, on, off, toggle, "
                        "command, watch, list or remove")
