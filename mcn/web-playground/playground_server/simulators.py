"""DB explorer, IoT device simulator and AI & RAG trace."""
from pathlib import Path
from flask import Blueprint
from .core import (
    _BACKEND_PORT,
    _SIMULATED_DEVICES,
    seed_demo_devices,
    _request_workspace,
    jsonify,
    request,
)

bp = Blueprint("simulators", __name__)

# ── DB, IoT, and AI Trace Simulator Endpoints ─────────────────────────────────

def _db_path() -> Path:
    db_path = _request_workspace() / "mcn_data.db"
    return db_path if db_path.exists() else Path("mcn_data.db")


def _app_tables() -> set:
    """Tables the workspace's own code creates (from the app map)."""
    try:
        from mcn.core_engine.app_map import build_map
        nodes = build_map(_request_workspace())["nodes"].values()
        return {n["name"] for n in nodes if n["kind"] == "table"}
    except Exception:
        return set()


def get_sqlite_schema():
    """Every table with its columns, row count, and whether this app's code creates it."""
    import sqlite3
    db_path = _db_path()
    if not db_path.exists():
        return []
    mine = _app_tables()
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        schema = []
        for (tbl,) in cur.fetchall():
            quoted = '"' + tbl.replace('"', '""') + '"'
            cur.execute(f"PRAGMA table_info({quoted})")
            columns = [{"name": c[1], "type": c[2] or "", "notnull": bool(c[3]), "default": c[4], "pk": bool(c[5])}
                       for c in cur.fetchall()]
            cur.execute(f"SELECT COUNT(*) FROM {quoted}")
            rows = cur.fetchone()[0]
            schema.append({"table": tbl, "columns": columns, "rows": rows, "in_app": tbl in mine})
        return schema
    finally:
        conn.close()


def run_sqlite_query(sql: str):
    """{columns, rows, affected, ms} for one SQL statement."""
    import sqlite3
    import time
    db_path = _db_path()
    if not db_path.exists():
        raise Exception("There's no database yet. Run your backend once so it creates its tables.")
    conn = sqlite3.connect(str(db_path))
    try:
        started = time.perf_counter()
        cur = conn.cursor()
        cur.execute(sql)
        if cur.description:                       # SELECT, PRAGMA, WITH ... return rows
            columns = [d[0] for d in cur.description]
            rows = cur.fetchmany(1000)
            result = {"columns": columns, "rows": [list(r) for r in rows], "truncated": len(rows) == 1000}
        else:
            conn.commit()
            result = {"columns": [], "rows": [], "affected": cur.rowcount}
        result["ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result
    finally:
        conn.close()

@bp.route("/api/db/schema", methods=["GET"])
def get_db_schema():
    try:
        return jsonify({"success": True, "schema": get_sqlite_schema()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/db/query", methods=["POST"])
def exec_db_query():
    data = request.get_json(silent=True) or {}
    sql = (data.get("sql") or "").strip()
    if not sql:
        return jsonify({"success": False, "error": "Write a SQL query first"})
    try:
        return jsonify({"success": True, "result": run_sqlite_query(sql)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def _iot():
    """This process's device registry (scripts run with Run), with the demo devices."""
    from mcn.core_engine.iot import shared_registry
    registry = shared_registry()
    seed_demo_devices(registry)
    return registry


def _backend(method: str, action: str, body: dict = None):
    """The running Preview backend's devices: (status, json) or None when it isn't running."""
    from . import core
    from .devserver import _DEV_TOKEN
    if not (core._mcn_backend and core._mcn_backend.poll() is None):
        return None
    import json as _json
    import urllib.error
    import urllib.request
    req = urllib.request.Request(
        f"http://127.0.0.1:{_BACKEND_PORT}/_mcn/iot/{action}", method=method,
        data=_json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_DEV_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=2) as res:
            return res.status, _json.loads(res.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, _json.loads(e.read())
        except ValueError:
            return e.code, {"success": False, "error": f"backend returned {e.code}"}
    except Exception:
        return None


@bp.route("/api/iot/devices", methods=["GET"])
def get_iot_devices():
    devices = {k: {**v, "source": "studio"} for k, v in _iot().snapshot().items()}
    if any(k not in _SIMULATED_DEVICES for k in devices):      # the user's own devices replace the demo ones
        devices = {k: v for k, v in devices.items() if k not in _SIMULATED_DEVICES}
    remote = _backend("GET", "devices")
    if remote and remote[0] == 200 and remote[1].get("devices"):
        # The app's own devices replace Studio's demo ones
        devices = {k: v for k, v in devices.items() if k not in _SIMULATED_DEVICES}
        devices.update({k: {**v, "source": "backend"} for k, v in remote[1]["devices"].items()})
    return jsonify({"success": True, "devices": devices, "backend": remote is not None})


@bp.route("/api/iot/device/value", methods=["POST"])
def set_iot_device_value():
    """Set an output, or hold an input at a value (null releases it)."""
    data = request.get_json(silent=True) or {}
    device_id, value = data.get("device_id"), data.get("value")
    action = "pin" if data.get("pin") or value is None else "value"
    if data.get("source") == "backend":
        remote = _backend("POST", action, {"device_id": device_id, "value": value})
        if remote is None:
            return jsonify({"success": False, "error": "The backend isn't running"})
        return jsonify(remote[1])
    iot = _iot()
    if not device_id or device_id not in iot.devices:
        return jsonify({"success": False, "error": "Invalid device ID"})
    try:
        result = iot.pin(device_id, value) if action == "pin" else iot.write(device_id, value, source="simulator")
        return jsonify({"success": True, "value": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/iot/commands", methods=["GET"])
def get_iot_commands():
    commands = [{**c, "source": "studio"} for c in _iot().command_log]
    remote = _backend("GET", "commands")
    if remote and remote[0] == 200:
        commands += [{**c, "source": "backend"} for c in remote[1].get("commands", [])]
    commands.sort(key=lambda c: c.get("timestamp", 0))
    return jsonify({"success": True, "commands": commands[-200:]})


def _ai_trace():
    try:
        from mcn.core_engine import ai_trace
    except ImportError:
        from core_engine import ai_trace  # type: ignore
    return ai_trace


@bp.route("/api/ai/trace", methods=["GET"])
def get_ai_trace():
    """Recent ai()/llm()/extract/classify/embed/vector_search/rag calls made by scripts."""
    trace = _ai_trace()
    return jsonify({"success": True, "model": trace.active_model_label(), "trace": trace.recent()})


@bp.route("/api/ai/trace", methods=["DELETE"])
def clear_ai_trace():
    _ai_trace().clear()
    return jsonify({"success": True})
