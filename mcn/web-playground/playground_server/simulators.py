"""DB explorer, IoT device simulator and AI & RAG trace."""
from pathlib import Path
from flask import Blueprint
from .core import (
    _SIMULATED_DEVICES,
    _request_workspace,
    jsonify,
    request,
)

bp = Blueprint("simulators", __name__)

# ── DB, IoT, and AI Trace Simulator Endpoints ─────────────────────────────────

def get_sqlite_schema():
    import sqlite3
    db_path = _request_workspace() / "mcn_data.db"
    if not db_path.exists():
        db_path = Path("mcn_data.db")
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall() if r[0] != "sqlite_sequence"]
        schema = []
        for tbl in tables:
            cursor.execute(f"PRAGMA table_info({tbl})")
            cols = [f"{c[1]} ({c[2]})" for c in cursor.fetchall()]
            schema.append({"table": tbl, "columns": cols})
        conn.close()
        return schema
    except Exception as e:
        return [{"error": str(e)}]

def run_sqlite_query(sql: str):
    import sqlite3
    db_path = _request_workspace() / "mcn_data.db"
    if not db_path.exists():
        db_path = Path("mcn_data.db")
    if not db_path.exists():
        raise Exception("Database file does not exist yet. Run some database operations first.")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(sql)
    if sql.strip().upper().startswith("SELECT"):
        cols = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        result = [dict(zip(cols, row)) for row in rows]
    else:
        conn.commit()
        result = [{"affected_rows": cursor.rowcount}]
    conn.close()
    return result


@bp.route("/api/db/schema", methods=["GET"])
def get_db_schema():
    try:
        schema = get_sqlite_schema()
        return jsonify({"success": True, "schema": schema})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route("/api/db/query", methods=["POST"])
def exec_db_query():
    try:
        data = request.get_json(silent=True) or {}
        sql = data.get("sql", "")
        if not sql:
            return jsonify({"success": False, "error": "No SQL query provided"})
        result = run_sqlite_query(sql)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def _iot():
    """The process-wide device registry shared with every MCN script run."""
    try:
        from mcn.core_engine.mcn_v3_extensions import get_shared_iot_connector
    except ImportError:
        from core_engine.mcn_v3_extensions import get_shared_iot_connector  # type: ignore
    iot = get_shared_iot_connector()
    # Demo devices so the panel is useful before a script registers its own
    for device_id, spec in _SIMULATED_DEVICES.items():
        if device_id not in iot.devices:
            iot.register_device(device_id, spec["type"], {"simulated": True})
            if spec["type"] in iot.UNITS:
                iot.set_override(device_id, spec["value"])
            else:
                iot.devices[device_id]["state"] = spec["value"]
    return iot


@bp.route("/api/iot/devices", methods=["GET"])
def get_iot_devices():
    return jsonify({"success": True, "devices": _iot().snapshot()})

@bp.route("/api/iot/device/value", methods=["POST"])
def set_iot_device_value():
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id")
    iot = _iot()
    if not device_id or device_id not in iot.devices:
        return jsonify({"success": False, "error": "Invalid device ID"})
    try:
        if iot.devices[device_id]["type"] in iot.UNITS:
            iot.set_override(device_id, data.get("value"))
        else:
            iot.send_command(device_id, "set", {"value": data.get("value"), "source": "simulator"})
        return jsonify({"success": True})
    except (TypeError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)})

@bp.route("/api/iot/commands", methods=["GET"])
def get_iot_commands():
    return jsonify({"success": True, "commands": list(_iot().command_log)})


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
