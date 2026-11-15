"""
Control policies: what each physical device may do, enforced on every action.

    policy("pump", {max_on: 600, cooldown: 300, hours: [6, 20]})
    policy("drive", {min: -50, max: 70, rate: 30})
    policy("vent", {check: vent_allowed})            // your own function: true, or a reason to refuse
    policy("door_lock", {approve: true})             // a person approves each change
    emergency_stop()                                  // every output to its safe value; changes refused until released

A policy applies whoever asks: the program, an AI agent calling it through a
tool, or someone in Studio's IoT panel. A refused action raises an error that
says why (an agent gets it back as the tool's result), and every refusal,
automatic switch-off and approval is recorded in the device command log.
In a virtual lab world, times and hours follow the world's simulated clock.
"""
from __future__ import annotations

import itertools
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

RULES = ("min", "max", "max_on", "cooldown", "rate", "hours", "check", "approve", "safe", "audit")


class PolicyError(Exception):
    """An action the device's policy doesn't allow."""


class ApprovalPending(PolicyError):
    """The action waits for a person to approve it."""


def _fmt_seconds(s: float) -> str:
    s = float(s)
    if s >= 3600 and s % 3600 == 0:
        return f"{int(s // 3600)} hour{'s' if s != 3600 else ''}"
    if s >= 60 and s % 60 == 0:
        return f"{int(s // 60)} minute{'s' if s != 60 else ''}"
    return f"{s:g} second{'s' if s != 1 else ''}"


class PolicyBook:
    """The policies of one device registry, their state, pending approvals and the emergency stop."""

    def __init__(self, registry):
        self.registry = registry
        self.rules: Dict[str, Dict[str, Any]] = {}
        self.on_since: Dict[str, float] = {}
        self.off_since: Dict[str, float] = {}
        self.changes: Dict[str, deque] = {}
        self.pending: Dict[str, Dict[str, Any]] = {}
        self.stopped = False
        self.stopped_at: Optional[float] = None
        self.lock = threading.RLock()
        self._ids = itertools.count(1)
        self._thread: Optional[threading.Thread] = None

    # ── Declaring ───────────────────────────────────────────────────────────

    def set(self, device_id: str, rules: Dict[str, Any]) -> Dict[str, Any]:
        device = self.registry.get(device_id)            # the device must exist
        unknown = [k for k in rules if k not in RULES]
        if unknown:
            raise PolicyError(f"unknown policy rule '{unknown[0]}' for '{device_id}'. Use: {', '.join(RULES)}")
        clean = dict(rules)
        hours = clean.get("hours")
        if hours is not None:
            if not (isinstance(hours, (list, tuple)) and len(hours) == 2):
                raise PolicyError("hours is [start, end] in 24-hour time, like [6, 20]")
            clean["hours"] = [float(hours[0]), float(hours[1])]
        for key in ("max_on", "cooldown", "rate"):
            if key in clean and (not isinstance(clean[key], (int, float)) or clean[key] <= 0):
                raise PolicyError(f"{key} must be a positive number")
        if "check" in clean and not callable(clean["check"]):
            raise PolicyError("check must be a function: policy(\"vent\", {check: vent_allowed})")
        with self.lock:
            self.rules[device.id] = clean
            if device.kind == "switch" and device.value:
                self.on_since.setdefault(device.id, self._now(device))
        if "max_on" in clean:
            self._ensure_thread()
        return self.describe(device.id)

    def remove(self, device_id: str) -> bool:
        with self.lock:
            return self.rules.pop(device_id, None) is not None

    def describe(self, device_id: str) -> Dict[str, Any]:
        rules = {k: ("function" if k == "check" else v) for k, v in self.rules.get(device_id, {}).items()}
        return {"device": device_id, "rules": rules, "summary": self.summary(device_id)}

    def summary(self, device_id: str) -> str:
        r = self.rules.get(device_id) or {}
        parts = []
        if "min" in r or "max" in r:
            parts.append(f"{r.get('min', '…')} to {r.get('max', '…')}")
        if "max_on" in r:
            parts.append(f"on for at most {_fmt_seconds(r['max_on'])}")
        if "cooldown" in r:
            parts.append(f"{_fmt_seconds(r['cooldown'])} rest between runs")
        if "rate" in r:
            parts.append(f"at most {r['rate']:g} changes a minute")
        if "hours" in r:
            a, b = r["hours"]
            parts.append(f"on between {a:g}:00 and {b:g}:00")
        if "check" in r:
            parts.append("its own check")
        if r.get("approve"):
            parts.append("a person approves each change")
        return ", ".join(parts)

    # ── Time: real, or the lab world's simulated clock ──────────────────────

    def _world(self, device):
        if getattr(device, "driver_name", "") != "lab":
            return None
        from .iot_lab import shared_lab
        found = shared_lab().world_for(device.id)
        return found[0] if found else None

    def _now(self, device) -> float:
        world = self._world(device)
        return world.clock if world is not None else time.time()

    def _hour(self, device) -> float:
        world = self._world(device)
        if world is not None and hasattr(world, "hour"):
            return world.hour()
        t = time.localtime()
        return t.tm_hour + t.tm_min / 60

    # ── Checking an action ──────────────────────────────────────────────────

    def check(self, device, value: Any, source: str) -> None:
        """Raise PolicyError when `device` may not be set to `value` now; record the refusal."""
        try:
            self._check(device, value, source)
        except PolicyError as exc:
            if not isinstance(exc, ApprovalPending):
                self._log(device.id, "refused", {"value": value, "source": source, "reason": str(exc)})
                self._audit(device.id, "refused", value, source, str(exc))
            raise

    def _safe_value(self, device) -> Any:
        r = self.rules.get(device.id, {})
        if "safe" in r:
            return r["safe"]
        if device.kind in ("switch", "level"):
            return 0 if not (device.type == "servo") else device.default
        return device.value

    def _check(self, device, value: Any, source: str) -> None:
        if self.stopped and source != "policy":
            if value != self._safe_value(device):
                raise PolicyError(f"Emergency stop is on: '{device.id}' can't be changed until it's released")
            return
        r = self.rules.get(device.id)
        if not r or source in ("policy", "approved-replay"):
            return
        name = device.id
        is_on = device.kind == "switch" and bool(value)
        if "min" in r and isinstance(value, (int, float)) and value < r["min"]:
            raise PolicyError(f"Refused: '{name}' can't go below {r['min']} (asked for {value})")
        if "max" in r and isinstance(value, (int, float)) and value > r["max"]:
            raise PolicyError(f"Refused: '{name}' can't go above {r['max']} (asked for {value})")
        turning_on = is_on and not device.value
        changing = value != device.value
        now = self._now(device)
        if turning_on and "cooldown" in r and name in self.off_since:
            rest = now - self.off_since[name]
            if rest < r["cooldown"]:
                raise PolicyError(f"Refused: '{name}' must rest {_fmt_seconds(r['cooldown'])} between runs "
                                  f"({_fmt_seconds(round(r['cooldown'] - rest))} to go)")
        if (turning_on or (device.kind != "switch" and changing)) and "hours" in r:
            a, b = r["hours"]
            h = self._hour(device)
            inside = a <= h < b if a <= b else (h >= a or h < b)
            if not inside:
                raise PolicyError(f"Refused: '{name}' may only be switched on between {a:g}:00 and {b:g}:00 "
                                  f"(it's {int(h):02d}:{int(h % 1 * 60):02d})")
        if changing and "rate" in r:
            recent = self.changes.setdefault(name, deque())
            while recent and now - recent[0] > 60:
                recent.popleft()
            if len(recent) >= r["rate"]:
                raise PolicyError(f"Refused: '{name}' may change at most {r['rate']:g} times a minute")
        if "check" in r:
            verdict = _call_check(r["check"], value, name)
            if verdict is not True and verdict is not None:
                reason = verdict if isinstance(verdict, str) and verdict else "its check said no"
                raise PolicyError(f"Refused: '{name}': {reason}")
        if r.get("approve") and changing and source != "approved":
            req = self._request(device, value, source)
            raise ApprovalPending(f"Waiting for a person to approve: set '{name}' to {value} (request {req['id']})")

    def written(self, device, value: Any, source: str) -> None:
        """Remember what happened, for cooldowns, rates and automatic switch-off."""
        name = device.id
        now = self._now(device)
        with self.lock:
            if name in self.rules:
                self.changes.setdefault(name, deque()).append(now)
            if device.kind == "switch":
                if value and name not in self.on_since:
                    self.on_since[name] = now
                elif not value and name in self.on_since:
                    del self.on_since[name]
                    self.off_since[name] = now
        if name in self.rules and self.rules[name].get("audit"):
            self._audit(name, "set", value, source, "")

    # ── Approvals ───────────────────────────────────────────────────────────

    def _request(self, device, value: Any, source: str) -> Dict[str, Any]:
        with self.lock:
            for req in self.pending.values():        # the same request again isn't a new one
                if req["device"] == device.id and req["value"] == value:
                    return req
            req = {"id": f"r{next(self._ids)}", "device": device.id, "value": value, "source": source,
                   "at": time.time(), "current": device.value}
            self.pending[req["id"]] = req
        self._log(device.id, "approval requested", {"value": value, "source": source, "request": req["id"]})
        return req

    def decide(self, request_id: str, approve: bool, by: str = "a person") -> Dict[str, Any]:
        with self.lock:
            req = self.pending.pop(str(request_id), None)
        if req is None:
            raise PolicyError(f"there's no pending request '{request_id}'")
        if approve:
            self._log(req["device"], "approved", {"value": req["value"], "by": by, "request": req["id"]})
            value = self.registry.write(req["device"], req["value"], source="approved")
            return {"success": True, "approved": True, "device": req["device"], "value": value}
        self._log(req["device"], "rejected", {"value": req["value"], "by": by, "request": req["id"]})
        return {"success": True, "approved": False, "device": req["device"]}

    # ── Emergency stop ──────────────────────────────────────────────────────

    def emergency_stop(self, on: bool = True) -> Dict[str, Any]:
        if not on:
            with self.lock:
                self.stopped, self.stopped_at = False, None
            self._log("*", "emergency stop released", {})
            return {"success": True, "stopped": False}
        with self.lock:
            self.stopped, self.stopped_at = True, time.time()
            self.pending.clear()
        made_safe = []
        for device_id, device in list(self.registry.devices.items()):
            if not device.writable or device.kind == "text":
                continue
            safe = self._safe_value(device)
            if device.value != safe:
                try:
                    self.registry.write(device_id, safe, source="policy")
                    made_safe.append(device_id)
                except Exception as exc:                 # keep stopping the rest
                    self._log(device_id, "couldn't make safe", {"reason": str(exc)})
        self._log("*", "emergency stop", {"made_safe": made_safe})
        return {"success": True, "stopped": True, "made_safe": made_safe}

    # ── Automatic switch-off ────────────────────────────────────────────────

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True, name="mcn-policy")
            self._thread.start()

    def _loop(self) -> None:
        while any("max_on" in r for r in self.rules.values()):
            time.sleep(0.1)
            self.tick()

    def tick(self) -> None:
        for name, r in list(self.rules.items()):
            if "max_on" not in r or name not in self.on_since:
                continue
            device = self.registry.devices.get(name)
            if device is None:
                continue
            if self._now(device) - self.on_since[name] >= r["max_on"]:
                try:
                    self.registry.write(name, 0, source="policy")
                    self._log(name, "switched off by policy", {"after": _fmt_seconds(r["max_on"])})
                except Exception:
                    pass

    # ── Records ─────────────────────────────────────────────────────────────

    def _log(self, device_id: str, command: str, params: Dict[str, Any]) -> None:
        self.registry.command_log.append({"timestamp": time.time(), "device_id": device_id,
                                          "command": command, "params": params})

    def _audit(self, device_id: str, action: str, value: Any, source: str, reason: str) -> None:
        if not (self.rules.get(device_id) or {}).get("audit"):
            return
        try:
            from .security import audit_log
            audit_log(f"device_{action}", {"device": device_id, "value": value, "source": source,
                                           **({"reason": reason} if reason else {})}, source)
        except Exception:
            pass

    def state(self) -> Dict[str, Any]:
        with self.lock:
            return {"stopped": self.stopped, "stopped_at": self.stopped_at,
                    "pending": list(self.pending.values()),
                    "policies": {name: self.describe(name) for name in self.rules}}


def _call_check(fn: Callable, value: Any, device_id: str) -> Any:
    params = getattr(fn, "mcn_params", None)
    count = len(params) if params is not None else 2
    try:
        return fn(*[value, device_id][:count])
    except PolicyError:
        raise
    except Exception as exc:
        return f"its check failed ({exc})"


def policy(operation: Any, rules: Any = None) -> Any:
    """The `policy(...)` built-in.

    policy("pump", {max_on: 600, ...})   set a device's policy (replaces the old one)
    policy("pump")                         the device's policy
    policy("list")                         every policy, pending approvals and the emergency stop state
    policy("remove", "pump")               remove a policy
    policy("approvals")                    actions waiting for approval
    policy("approve", "r1") / policy("reject", "r1")
    """
    from .iot import shared_registry
    book = shared_registry().policies
    op = str(operation or "")
    if op == "list":
        return book.state()
    if op == "approvals":
        return book.state()["pending"]
    if op in ("approve", "reject"):
        return book.decide(str(rules), op == "approve", by="the program")
    if op == "remove":
        return {"success": book.remove(str(rules))}
    if rules is None:
        if op not in book.rules:
            shared_registry().get(op)
        return book.describe(op)
    if not isinstance(rules, dict):
        raise PolicyError("policy(\"pump\", {max_on: 600}) takes a map of rules")
    return book.set(op, rules)


def emergency_stop(on: Any = True) -> Any:
    """The `emergency_stop(...)` built-in: emergency_stop() stops, emergency_stop(false) releases."""
    from .iot import shared_registry
    release = on is False or str(on).lower() in ("release", "off", "false", "0")
    return shared_registry().policies.emergency_stop(not release)
