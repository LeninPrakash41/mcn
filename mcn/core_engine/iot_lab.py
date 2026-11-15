"""
The virtual lab: simulated worlds whose devices behave like the real thing.

    lab("greenhouse")                 // soil, temperature, light and humidity sensors; pump, fan, grow light, vent
    lab("rover", {speed: 1})          // a robot in a room: drive motor, steering, three distance sensors, a bumper

Each world adds ordinary devices (driver "lab"), so a program reads and drives
them with device(...) exactly as it would real hardware, and the same program
later runs on a Raspberry Pi or an ESP32 by changing the driver. A background
thread moves the world forward: soil dries in the sun and gets wetter while the
pump runs, the rover drives where its motor and steering send it, and its
distance sensors measure the walls and obstacles in front of it.

Studio's IoT panel draws each world from lab("state").
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, List, Optional


class LabError(Exception):
    """A request the lab can't carry out."""


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class World:
    name = "world"
    title = "World"
    default_speed = 1.0
    # device id → device config (type and anything else device() accepts)
    devices: Dict[str, Dict[str, Any]] = {}

    def __init__(self, speed: Optional[float] = None, prefix: str = ""):
        self.speed = float(speed) if speed else self.default_speed
        self.prefix = prefix
        self.outputs: Dict[str, Any] = {}
        self.events: List[Dict[str, Any]] = []
        self.reset()

    # The device ids this world adds (with the prefix)
    def device_ids(self) -> Dict[str, str]:
        return {self.prefix + key: key for key in self.devices}

    def reset(self) -> None:
        self.clock = 0.0                     # simulated seconds since the start
        self.outputs = {k: c.get("default", 0) for k, c in self.devices.items() if _writable(c["type"])}
        self.events = []

    def tick(self, real_dt: float) -> None:
        dt = real_dt * self.speed
        self.clock += dt
        self.step(dt)

    def step(self, dt: float) -> None:          # pragma: no cover - each world defines it
        raise NotImplementedError

    def read(self, key: str) -> Any:            # pragma: no cover
        raise NotImplementedError

    def write(self, key: str, value: Any) -> None:
        self.outputs[key] = value

    def note(self, text: str) -> None:
        self.events.append({"at": round(self.clock), "text": text})
        del self.events[:-20]

    def scene(self) -> Dict[str, Any]:
        return {"world": self.name, "title": self.title, "speed": self.speed, "clock": round(self.clock, 1),
                "prefix": self.prefix, "events": list(self.events)}


def _writable(device_type: str) -> bool:
    from .iot import TYPES
    return TYPES.get(device_type, ("text",))[0] in ("switch", "level", "text")


# ── Greenhouse ───────────────────────────────────────────────────────────────

class Greenhouse(World):
    """A day in a small greenhouse. One real second is one simulated minute by default
    (speed 60), so a day passes in 24 minutes; lab("greenhouse", {speed: 600}) runs it in under 3."""
    name = "greenhouse"
    title = "Greenhouse"
    default_speed = 60.0
    devices = {
        "soil_moisture": {"type": "soil_moisture", "location": "Greenhouse"},
        "temperature":   {"type": "temperature_sensor", "location": "Greenhouse"},
        "humidity":      {"type": "humidity_sensor", "location": "Greenhouse"},
        "light":         {"type": "light_sensor", "location": "Greenhouse", "max": 1500},
        "pump":          {"type": "pump", "location": "Greenhouse"},
        "fan":           {"type": "fan", "location": "Greenhouse"},
        "grow_light":    {"type": "light", "location": "Greenhouse"},
        "vent":          {"type": "servo", "location": "Greenhouse", "default": 0},
    }
    START_HOUR = 8.0

    def reset(self) -> None:
        super().reset()
        self.soil, self.temp, self.humid = 45.0, 21.0, 55.0
        self.water_used = 0.0                  # litres
        self.plant = 80.0                      # plant health, 0–100

    def hour(self) -> float:
        return (self.START_HOUR + self.clock / 3600) % 24

    def sun(self) -> float:
        """0 at night, 1 at noon."""
        h = self.hour()
        return max(0.0, math.sin((h - 6) / 12 * math.pi)) if 6 <= h <= 18 else 0.0

    def step(self, dt: float) -> None:
        minutes = dt / 60
        sun = self.sun()
        pump = 1 if self.outputs.get("pump") else 0
        fan = 1 if self.outputs.get("fan") else 0
        grow = 1 if self.outputs.get("grow_light") else 0
        vent = _clamp(float(self.outputs.get("vent") or 0), 0, 180) / 180
        # Soil: dries faster in sun and heat; the pump wets it
        drying = (0.03 + 0.12 * sun + 0.004 * max(0.0, self.temp - 20)) * minutes
        self.soil = _clamp(self.soil - drying + 2.5 * pump * minutes, 0, 100)
        self.water_used += 0.5 * pump * minutes
        # Temperature: follows the day outside, the sun warms it, the fan and vent cool it
        outside = 14 + 10 * math.sin((self.hour() - 9) / 24 * 2 * math.pi)
        target = outside + 12 * sun * (1 - 0.6 * vent) + 1.5 * grow - 5 * fan - 3 * vent
        self.temp += (target - self.temp) * min(1.0, minutes / 25)
        # Humidity: wet soil raises it, the fan and vent let it out
        h_target = 35 + 0.5 * self.soil - 15 * fan - 12 * vent
        self.humid = _clamp(self.humid + (h_target - self.humid) * min(1.0, minutes / 30), 5, 98)
        # The plant does well with moist soil, mild air and enough light
        light_ok = sun > 0.2 or grow or not (8 <= self.hour() <= 18)
        good = 30 <= self.soil <= 75 and 15 <= self.temp <= 30 and light_ok
        self.plant = _clamp(self.plant + (0.05 if good else -0.08) * minutes, 0, 100)

    def read(self, key: str) -> Any:
        if key == "soil_moisture":
            return round(self.soil, 1)
        if key == "temperature":
            return round(self.temp, 1)
        if key == "humidity":
            return round(self.humid, 1)
        if key == "light":
            return round(950 * self.sun() + (450 if self.outputs.get("grow_light") else 0))
        return self.outputs.get(key, 0)

    def write(self, key: str, value: Any) -> None:
        before = self.outputs.get(key)
        super().write(key, value)
        if key in ("pump", "fan", "grow_light") and bool(before) != bool(value):
            self.note(f"{key.replace('_', ' ').capitalize()} {'on' if value else 'off'}")

    def scene(self) -> Dict[str, Any]:
        h = self.hour()
        return {**super().scene(), "time": f"{int(h):02d}:{int(h % 1 * 60):02d}", "hour": round(h, 2),
                "day": int((self.START_HOUR + self.clock / 3600) // 24) + 1, "sun": round(self.sun(), 2),
                "soil_moisture": round(self.soil, 1), "temperature": round(self.temp, 1), "humidity": round(self.humid, 1),
                "light": self.read("light"), "water_used": round(self.water_used, 1), "plant": round(self.plant),
                "outputs": dict(self.outputs)}


# ── Rover ────────────────────────────────────────────────────────────────────

class Rover(World):
    """A small robot in a 6 m × 4 m room with obstacles and a charging pad.
    drive (-100 to 100 %, negative backs up) sets its speed, steering (0–180°, 90 straight
    ahead, above 90 turns left) turns it;
    front, left and right distance sensors measure the nearest wall or obstacle
    (up to 400 cm), and the bumper reads 1 while it's touching one."""
    name = "rover"
    title = "Rover"
    default_speed = 1.0
    devices = {
        "drive":          {"type": "motor", "location": "Rover", "min": -100, "max": 100},
        "steering":       {"type": "servo", "location": "Rover", "default": 90},
        "headlight":      {"type": "led", "location": "Rover"},
        "front_distance": {"type": "distance_sensor", "location": "Rover"},
        "left_distance":  {"type": "distance_sensor", "location": "Rover"},
        "right_distance": {"type": "distance_sensor", "location": "Rover"},
        "bumper":         {"type": "button", "location": "Rover"},
    }
    WIDTH, HEIGHT = 6.0, 4.0                  # metres
    OBSTACLES = [(1.6, 0.0, 0.3, 1.6), (3.2, 2.2, 0.3, 1.8), (4.4, 0.9, 0.9, 0.5)]   # x, y, w, h
    PAD = (5.3, 3.3, 0.5)                     # charging pad: centre x, y and radius
    MAX_SPEED = 0.6                           # m/s at 100 %
    WHEELBASE = 0.25
    RADIUS = 0.15

    def reset(self) -> None:
        super().reset()
        # Metres from the top-left corner (y points down, as on screen); heading in radians, 0 = facing right
        self.x, self.y, self.heading = 0.6, 0.6, 0.0
        self.bump = 0
        self.distance = 0.0
        self.trail: List[List[float]] = [[round(self.x, 2), round(self.y, 2)]]
        self.reached = False

    def _blocked(self, x: float, y: float) -> bool:
        r = self.RADIUS
        if x < r or y < r or x > self.WIDTH - r or y > self.HEIGHT - r:
            return True
        return any(ox - r < x < ox + w + r and oy - r < y < oy + h + r for ox, oy, w, h in self.OBSTACLES)

    def _ray(self, angle: float) -> float:
        """Distance in cm from the rover's front to the nearest wall or obstacle along `angle`."""
        step = 0.02
        x0 = self.x + math.cos(self.heading) * self.RADIUS
        y0 = self.y + math.sin(self.heading) * self.RADIUS
        d = 0.0
        while d < 4.0:
            px, py = x0 + math.cos(angle) * d, y0 + math.sin(angle) * d
            if px <= 0 or py <= 0 or px >= self.WIDTH or py >= self.HEIGHT:
                break
            if any(ox <= px <= ox + w and oy <= py <= oy + h for ox, oy, w, h in self.OBSTACLES):
                break
            d += step
        return round(_clamp(d * 100, 2, 400))

    def step(self, dt: float) -> None:
        # Small steps keep the motion smooth at higher speeds
        steps = max(1, int(dt / 0.05))
        sub = dt / steps
        for _ in range(steps):
            v = _clamp(float(self.outputs.get("drive") or 0), -100, 100) / 100 * self.MAX_SPEED
            steer = math.radians(_clamp(float(self.outputs.get("steering", 90)) - 90, -35, 35))
            if v == 0:
                continue
            heading = self.heading - v / self.WHEELBASE * math.tan(steer) * sub   # above 90° turns left
            nx = self.x + math.cos(heading) * v * sub
            ny = self.y + math.sin(heading) * v * sub
            if self._blocked(nx, ny):
                # Touching something: slide along it if part of the move is free, else stop
                # (like a real car it can't turn on the spot, so it has to back up)
                if not self.bump:
                    self.note("Bumped into something")
                self.bump = 1
                if not self._blocked(nx, self.y):
                    ny = self.y
                elif not self._blocked(self.x, ny):
                    nx = self.x
                else:
                    continue
            else:
                self.bump = 0
            self.heading = heading % (2 * math.pi)
            self.distance += math.hypot(nx - self.x, ny - self.y)
            self.x, self.y = nx, ny
            if math.hypot(self.x - self.trail[-1][0], self.y - self.trail[-1][1]) > 0.05:
                self.trail.append([round(self.x, 2), round(self.y, 2)])
                del self.trail[:-400]
            px, py, pr = self.PAD
            if not self.reached and math.hypot(self.x - px, self.y - py) < pr:
                self.reached = True
                self.note("Reached the charging pad")

    def read(self, key: str) -> Any:
        if key == "front_distance":
            return self._ray(self.heading)
        if key == "left_distance":          # the room's y axis points down, as on screen: left is -45°
            return self._ray(self.heading - math.radians(45))
        if key == "right_distance":
            return self._ray(self.heading + math.radians(45))
        if key == "bumper":
            return self.bump
        return self.outputs.get(key, 0)

    def scene(self) -> Dict[str, Any]:
        return {**super().scene(), "width": self.WIDTH, "height": self.HEIGHT, "x": round(self.x, 3), "y": round(self.y, 3),
                "heading": round(math.degrees(self.heading), 1), "obstacles": [list(o) for o in self.OBSTACLES],
                "pad": list(self.PAD), "trail": self.trail[-200:], "bumper": self.bump, "reached": self.reached,
                "distance_m": round(self.distance, 2),
                "sensors": {k: self.read(k) for k in ("front_distance", "left_distance", "right_distance")},
                "outputs": dict(self.outputs)}


WORLDS = {"greenhouse": Greenhouse, "rover": Rover}


# ── The running lab ──────────────────────────────────────────────────────────

class Lab:
    """The worlds this process is running, and the thread that moves them forward."""

    TICK = 0.1

    def __init__(self):
        self.worlds: Dict[str, World] = {}
        self.lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None

    def world_for(self, device_id: str) -> Optional[tuple]:
        with self.lock:
            for w in self.worlds.values():
                key = w.device_ids().get(device_id)
                if key:
                    return w, key
        return None

    def start(self, name: str, options: Optional[Dict[str, Any]] = None) -> World:
        from .iot import shared_registry
        options = dict(options or {})
        cls = WORLDS.get(str(name or "").lower())
        if cls is None:
            raise LabError(f"there's no lab world called '{name}'. Use one of: {', '.join(WORLDS)}")
        world = cls(speed=options.get("speed"), prefix=str(options.get("prefix") or ""))
        reg = shared_registry()
        with self.lock:
            old = self.worlds.get(world.name)
            if old is not None:
                for device_id in old.device_ids():
                    reg.remove(device_id)
            self.worlds[world.name] = world
        for device_id, key in world.device_ids().items():
            reg.register(device_id, {**world.devices[key], "driver": "lab", "world": world.name})
        self._ensure_thread()
        return world

    def stop(self, name: str) -> bool:
        from .iot import shared_registry
        with self.lock:
            world = self.worlds.pop(str(name).lower(), None)
        if world is None:
            return False
        reg = shared_registry()
        for device_id in world.device_ids():
            reg.remove(device_id)
        return True

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True, name="mcn-lab")
            self._thread.start()

    def _loop(self) -> None:
        last = time.time()
        while self.worlds:
            time.sleep(self.TICK)
            now = time.time()
            dt, last = min(now - last, 0.5), now
            with self.lock:
                for w in list(self.worlds.values()):
                    try:
                        w.tick(dt)
                    except Exception as exc:          # a world never stops the program
                        w.note(f"Simulation error: {exc}")

    def scenes(self) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            return {name: w.scene() for name, w in self.worlds.items()}


_LAB: Optional[Lab] = None


def shared_lab() -> Lab:
    global _LAB
    if _LAB is None:
        _LAB = Lab()
    return _LAB


def lab(operation: str, options: Any = None) -> Any:
    """The `lab(...)` built-in.

    lab("greenhouse") / lab("rover", {speed, prefix})  start a world and add its devices
    lab("state")                                        every running world, as Studio draws it
    lab("reset", "rover")                               put a world back to its start
    lab("speed", {world: "greenhouse", speed: 600})     run it faster or slower
    lab("remove", "rover")                              stop a world and remove its devices
    """
    the_lab = shared_lab()
    op = str(operation or "").lower()
    if op in WORLDS:
        world = the_lab.start(op, options if isinstance(options, dict) else {})
        return {"success": True, "world": world.name, "devices": list(world.device_ids()), "speed": world.speed}
    if op == "state":
        scenes = the_lab.scenes()
        return scenes.get(str(options).lower()) if isinstance(options, str) else scenes
    if op in ("reset", "remove", "stop"):
        name = str(options or "").lower()
        if op == "reset":
            with the_lab.lock:
                world = the_lab.worlds.get(name)
                if world is None:
                    raise LabError(f"the {name or '?'} lab isn't running. Start it with lab(\"{name or 'greenhouse'}\")")
                world.reset()
            return {"success": True}
        return {"success": the_lab.stop(name)}
    if op == "speed":
        opts = options if isinstance(options, dict) else {}
        with the_lab.lock:
            world = the_lab.worlds.get(str(opts.get("world", "")).lower())
            if world is None:
                raise LabError("lab(\"speed\", {world: \"greenhouse\", speed: 600}) needs a running world")
            world.speed = _clamp(float(opts.get("speed") or world.default_speed), 0, 10000)
        return {"success": True, "speed": world.speed}
    raise LabError(f"unknown lab operation '{operation}'. Use {', '.join(WORLDS)}, state, reset, speed or remove")
