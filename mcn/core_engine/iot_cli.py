"""
`mcn iot`: tools for running MCN with real hardware.

    mcn iot firmware arduino      # write the USB firmware sketch for Arduino/ESP32/Pico
    mcn iot firmware esp32        # write the WiFi (MQTT) sketch for ESP32/ESP8266
    mcn iot ports                 # list boards plugged in over USB
    mcn iot service app.mcn       # start an MCN app when a Raspberry Pi boots
"""
from __future__ import annotations

import getpass
import os
import shutil
import sys
from pathlib import Path

FIRMWARE = Path(__file__).resolve().parent.parent / "iot_firmware"
SKETCHES = {"arduino": "mcn_firmware", "esp32": "mcn_esp32"}


def firmware(board: str, out: str = ".") -> int:
    name = SKETCHES.get(board)
    if not name:
        print(f"error: unknown board '{board}'. Use: {', '.join(SKETCHES)}", file=sys.stderr)
        return 1
    target = Path(out) / name                       # Arduino wants the folder named after the sketch
    target.mkdir(parents=True, exist_ok=True)
    dest = target / f"{name}.ino"
    if dest.exists():
        print(f"error: {dest} already exists", file=sys.stderr)
        return 1
    shutil.copy(FIRMWARE / name / f"{name}.ino", dest)
    print(f"wrote {dest}")
    if board == "arduino":
        print("Open it in the Arduino IDE, upload it to the board, then use driver: \"serial\" in device().")
    else:
        print("Fill in WiFi, the MQTT broker and the DEVICES table, upload it, then use driver: \"mqtt\" in device().")
    return 0


def ports() -> int:
    try:
        from serial.tools import list_ports
    except ImportError:
        print("USB boards need IoT support. Run: mcn add iot", file=sys.stderr)
        return 1
    found = list(list_ports.comports())
    if not found:
        print("No serial ports found. Plug the board in with a data (not charge-only) USB cable.")
        return 0
    for p in found:
        print(f"{p.device:<28} {p.description}")
    return 0


UNIT = """[Unit]
Description=MCN app {name}
After=network-online.target
Wants=network-online.target

[Service]
User={user}
WorkingDirectory={cwd}
Environment=MCN_IOT_SIMULATE=0
EnvironmentFile=-{cwd}/.env
ExecStart={mcn} {command} {file}{args}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def service(file: str, serve: bool = False, port: int = 0) -> int:
    """Write a systemd unit that runs (or serves) the app at boot."""
    path = Path(file).resolve()
    if not path.exists():
        print(f"error: file not found: {file}", file=sys.stderr)
        return 1
    mcn = shutil.which("mcn") or f"{sys.executable} -m mcn.core_engine.mcn_cli"
    is_service = serve or "service " in path.read_text(encoding="utf-8")
    name = path.stem.replace("_", "-")
    unit = UNIT.format(
        name=name, user=getpass.getuser(), cwd=path.parent, mcn=mcn,
        command="serve" if is_service else "run", file=path.name,
        args=(f" --host 0.0.0.0 --port {port}" if port else " --host 0.0.0.0") if is_service else "")
    out = Path(f"mcn-{name}.service")
    out.write_text(unit, encoding="utf-8")
    print(f"wrote {out}\n\nInstall and start it:\n"
          f"  sudo cp {out} /etc/systemd/system/\n"
          f"  sudo systemctl enable --now {out.name}\n\n"
          f"Logs: journalctl -u {out.name} -f")
    return 0


def main(args) -> int:
    if args.iot_command == "firmware":
        return firmware(args.board, args.out)
    if args.iot_command == "ports":
        return ports()
    if args.iot_command == "service":
        return service(args.file, serve=args.serve, port=args.port or 0)
    print(__doc__.strip())
    return 0


def add_parser(subparsers) -> None:
    p = subparsers.add_parser("iot", help="Hardware tools: board firmware, USB ports, run on boot")
    sub = p.add_subparsers(dest="iot_command")
    fw = sub.add_parser("firmware", help="Write the firmware sketch for a board")
    fw.add_argument("board", choices=list(SKETCHES), help="arduino (USB) or esp32 (WiFi + MQTT)")
    fw.add_argument("--out", default=".", help="Folder to write the sketch into (default: here)")
    sub.add_parser("ports", help="List boards plugged in over USB")
    sv = sub.add_parser("service", help="Start an MCN app when a Raspberry Pi boots (systemd)")
    sv.add_argument("file", help="The .mcn file to run")
    sv.add_argument("--serve", action="store_true", help="Serve it as an API (automatic for files with a service)")
    sv.add_argument("--port", type=int, help="Port for the API")
