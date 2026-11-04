"""
Feature tests for the playground's simulators and inspectors: they must reflect
what MCN code actually does, not canned data.
"""
from playground_app import load, quiet

pg, client = load()


def run(code):
    res = quiet(client.post, "/api/execute", json={"code": code}).get_json()
    assert res.get("success") is True, res.get("error")
    return res["output"]


# ── IoT: code, simulator panel and command log share one device registry ─────

def test_iot_device_registered_in_code_appears_in_panel():
    run('device("register", "greenhouse_temp", {type: "temperature_sensor"})')
    devices = client.get("/api/iot/devices").get_json()["devices"]
    assert devices["greenhouse_temp"]["type"] == "temperature_sensor"
    assert devices["greenhouse_temp"]["unit"] == "°C"


def test_iot_panel_override_changes_what_code_reads():
    run('device("register", "lab_temp", {type: "temperature_sensor"})')
    res = client.post("/api/iot/device/value", json={"device_id": "lab_temp", "value": 31.5}).get_json()
    assert res["success"] is True
    out = run('var r = device("read", "lab_temp")\nlog(str(r.value))')
    assert out == ["31.5"]


def test_iot_commands_from_code_show_in_log():
    run('device("register", "fan_1", {type: "fan"})\n'
        'device("command", "fan_1", {command: "on", speed: 3})')
    log = client.get("/api/iot/commands").get_json()["commands"]
    last = log[-1]
    assert (last["device_id"], last["command"], last["params"]["speed"]) == ("fan_1", "on", 3)
    # outputs report what they were set to
    assert client.get("/api/iot/devices").get_json()["devices"]["fan_1"]["value"] == 1


def test_iot_demo_devices_and_validation(monkeypatch):
    from mcn.core_engine import iot
    monkeypatch.setattr(iot, "_SHARED", None)            # a fresh registry: only the demo devices
    devices = client.get("/api/iot/devices").get_json()["devices"]
    assert {"office_temp", "office_occupancy", "hvac_system"} <= set(devices)
    run('device("register", "mine", {type: "light"})')   # the user's own devices replace them
    devices = client.get("/api/iot/devices").get_json()["devices"]
    assert "mine" in devices and "office_temp" not in devices
    bad = client.post("/api/iot/device/value", json={"device_id": "nope", "value": 1}).get_json()
    assert bad["success"] is False


# ── AI & RAG trace: every AI call a script makes is recorded ─────────────────

def test_ai_trace_records_script_calls(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)   # mock provider, no network
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client.delete("/api/ai/trace")
    run('var a = ai("Summarise MCN in one line")\n'
        'var c = classify("I want a refund", ["purchase", "refund"])\n'
        'var v = embed("hello world")\n'
        'var r = rag("What is MCN?", ["MCN is a language for full-stack apps"])')
    data = client.get("/api/ai/trace").get_json()
    kinds = [t["type"] for t in data["trace"]]
    assert kinds[:2] == ["ai", "classify"] and "embed" in kinds and kinds[-1] == "rag"
    first = data["trace"][0]
    assert first["prompt"] == "Summarise MCN in one line" and "duration_ms" in first
    assert "mock mode" in data["model"]


def test_ai_trace_clear():
    client.delete("/api/ai/trace")
    assert client.get("/api/ai/trace").get_json()["trace"] == []


# ── Telemetry: submissions are kept locally until delivered ──────────────────

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _receiver():
    """A local stand-in for the PHP feedback endpoint; returns (url, received, server)."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/feedback.php", received, server


def test_feedback_saved_locally_without_endpoint(monkeypatch):
    monkeypatch.delenv("MCN_FEEDBACK_ENDPOINT", raising=False)
    res = client.post("/api/telemetry/feedback", json={"message": "offline report"}).get_json()
    assert res["success"] and res["delivered"] is False and res["pending"] >= 1
    assert "saved" in res["message"]


def test_feedback_delivered_and_queue_flushed(monkeypatch):
    url, received, server = _receiver()
    monkeypatch.setenv("MCN_FEEDBACK_ENDPOINT", url)
    monkeypatch.setenv("MCN_TELEMETRY_ENDPOINT", url)
    try:
        res = client.post("/api/telemetry/feedback", json={"message": "online report"}).get_json()
    finally:
        server.shutdown()
    assert res["delivered"] is True and res["pending"] == 0
    # earlier offline submissions are retried and delivered too
    assert "online report" in [r.get("message") for r in received]
    assert client.get("/api/telemetry/status").get_json()["pending_submissions"] == 0


def test_registration_newsletter_is_opt_in(monkeypatch):
    monkeypatch.delenv("MCN_TELEMETRY_ENDPOINT", raising=False)
    res = client.post("/api/telemetry/register", json={"email": "student@example.com"}).get_json()
    assert res["profile"]["newsletter_opt_in"] is False


# ── Packages: mock/demo results say so; audit logs persist ───────────────────

def test_mock_and_demo_results_are_labelled(monkeypatch):
    from mcn.core_engine.mcn_packages import get_registry
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    stripe = get_registry().load("stripe")
    assert stripe["charge"](10)["mock"] is True
    finance = get_registry().load("finance")
    assert finance["kyc_check"]({"name": "Ada"})["demo"] is True
    assert finance["regulatory_report"]("sar", {})["status"] != "submitted"
    health = get_registry().load("healthcare")
    assert "warning" in health["check_drug_interactions"](["ibuprofen", "paracetamol"])


def test_hipaa_audit_log_persists(monkeypatch, tmp_path):
    from mcn.core_engine.mcn_packages import get_registry
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MCN_AUDIT_LOG", str(log))
    health = get_registry().load("healthcare")
    health["hipaa_audit_log"]("view", "dr_1", "pt_9", "chart")
    health["hipaa_audit_log"]("edit", "dr_1", "pt_9", "meds")
    entries = [json.loads(l) for l in log.read_text().splitlines()]
    assert [e["action"] for e in entries] == ["view", "edit"]
