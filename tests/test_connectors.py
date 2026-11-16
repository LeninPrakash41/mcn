"""
Connectors: Google Sheets, CSV and Excel, SQL databases, HubSpot, Salesforce, Airtable,
Slack and WhatsApp as one-line packages. Sample data without credentials; with them,
the right API calls (the HTTP layer is replaced here, so nothing leaves the machine).
"""
import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine import connectors as cx  # noqa: E402

KEYS = ["HUBSPOT_TOKEN", "SALESFORCE_INSTANCE_URL", "SALESFORCE_TOKEN", "AIRTABLE_TOKEN", "SLACK_WEBHOOK_URL",
        "SLACK_BOT_TOKEN", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM", "TWILIO_FROM_NUMBER", "GOOGLE_SERVICE_ACCOUNT", "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_SHEETS_API_KEY", "EXTERNAL_DATABASE_URL"]


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    cx._NOTED.clear()


@pytest.fixture
def http(monkeypatch):
    """Record every call and answer from a queue of responses."""
    calls, answers = [], []

    def fake(method, url, headers=None, body=None, form=None, timeout=20):
        calls.append({"method": method, "url": url, "headers": headers or {}, "body": body, "form": form})
        return answers.pop(0) if answers else {}
    monkeypatch.setattr(cx, "_request", fake)
    return calls, answers


def test_without_credentials_reads_are_samples_and_writes_are_not_sent(http, capsys):
    calls, _ = http
    assert cx.hubspot_list("deals")[0]["dealname"] == "Acme renewal"
    assert cx.salesforce_query("SELECT Id FROM Account")[0]["Name"] == "Acme Corporation"
    assert cx.airtable_list("app1", "Orders")[0]["name"] == "Asha Rao"
    assert cx.post_message("#sales", "hi")["sample"] and cx.whatsapp_send("+91 98765 43210", "hi")["to"] == "+919876543210"
    assert cx.hubspot_create("contacts", {"email": "a@b.c"})["sample"] and cx.sheets_append("demo", {"a": 1})["sample"]
    assert calls == []                                              # nothing was sent anywhere
    out = capsys.readouterr().out
    assert out.count("[hubspot] Not connected yet") == 1 and "HUBSPOT_TOKEN" in out   # said once, with what to set


def test_hubspot_calls_the_crm_api(http, monkeypatch):
    calls, answers = http
    monkeypatch.setenv("HUBSPOT_TOKEN", "pat-123")
    answers.append({"results": [{"id": "9", "properties": {"dealname": "Big deal", "amount": "500"}}]})
    assert cx.hubspot_list("deals", 5) == [{"id": "9", "dealname": "Big deal", "amount": "500"}]
    assert calls[0]["url"].startswith("https://api.hubapi.com/crm/v3/objects/deals?limit=5&properties=dealname")
    assert calls[0]["headers"]["Authorization"] == "Bearer pat-123"
    answers.append({"id": "77", "properties": {"email": "asha@example.com"}})
    assert cx.hubspot_create("contacts", {"email": "asha@example.com"})["id"] == "77"
    assert calls[1]["method"] == "POST" and calls[1]["body"] == {"properties": {"email": "asha@example.com"}}
    cx.hubspot_update("contacts", 77, {"phone": "1"})
    assert calls[2]["method"] == "PATCH" and calls[2]["url"].endswith("/crm/v3/objects/contacts/77")
    cx.hubspot_search("contacts", "asha")
    assert calls[3]["url"].endswith("/contacts/search") and calls[3]["body"]["query"] == "asha"


def test_salesforce_airtable_and_their_shapes(http, monkeypatch):
    calls, answers = http
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "https://acme.my.salesforce.com/")
    monkeypatch.setenv("SALESFORCE_TOKEN", "tok")
    answers.append({"records": [{"attributes": {"type": "Account"}, "Id": "001", "Name": "Acme"}]})
    assert cx.salesforce_query("SELECT Id, Name FROM Account") == [{"Id": "001", "Name": "Acme"}]
    assert calls[0]["url"].startswith("https://acme.my.salesforce.com/services/data/v60.0/query?q=SELECT%20Id")
    answers.append({"id": "003X", "success": True})
    assert cx.salesforce_create("Contact", {"LastName": "Rao"}) == {"id": "003X", "success": True}
    monkeypatch.setenv("AIRTABLE_TOKEN", "pat")
    answers.append({"records": [{"id": "rec1", "fields": {"Name": "Asha"}}]})
    assert cx.airtable_list("appX", "My Orders") == [{"id": "rec1", "Name": "Asha"}]
    assert "/v0/appX/My%20Orders?maxRecords=100" in calls[2]["url"]


def test_slack_and_whatsapp_send_for_real(http, monkeypatch):
    calls, answers = http
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb")
    answers.append({"ok": False, "error": "channel_not_found"})
    with pytest.raises(cx.ConnectorError, match="channel_not_found"):
        cx.post_message("#nope", "hi")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+14155238886")
    answers.append({"sid": "SM1"})
    assert cx.whatsapp_send("+1 (555) 010-2000", "Your order shipped") == {"success": True, "id": "SM1"}
    assert calls[1]["form"] == {"From": "whatsapp:+14155238886", "To": "whatsapp:+15550102000", "Body": "Your order shipped"}
    monkeypatch.setenv("WHATSAPP_TOKEN", "meta")
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "123")
    answers.append({"messages": [{"id": "wamid.1"}]})
    assert cx.whatsapp_send("+15550102000", "hi")["id"] == "wamid.1"           # Meta's API is preferred
    assert calls[2]["url"] == "https://graph.facebook.com/v20.0/123/messages" and calls[2]["body"]["to"] == "15550102000"


def test_google_sheets_reads_a_shared_sheet_and_uses_an_api_key(http, monkeypatch):
    calls, answers = http
    answers.append("name,email\nAsha,asha@example.com\n")
    rows = cx.sheets_read("https://docs.google.com/spreadsheets/d/AbC_123/edit#gid=0", "Leads")
    assert rows == [{"name": "Asha", "email": "asha@example.com"}]
    assert calls[0]["url"] == "https://docs.google.com/spreadsheets/d/AbC_123/gviz/tq?tqx=out:csv&sheet=Leads"
    monkeypatch.setenv("GOOGLE_SHEETS_API_KEY", "k")
    answers.append({"values": [["name", "amount"], ["Ravi", "450"], ["Meera"]]})
    assert cx.sheets_read("AbC_123") == [{"name": "Ravi", "amount": "450"}, {"name": "Meera", "amount": ""}]
    assert calls[1]["url"].startswith("https://sheets.googleapis.com/v4/spreadsheets/AbC_123/values/A%3AZZ?key=k")


def test_a_private_sheet_without_credentials_falls_back_to_samples(http):
    _, answers = http
    answers.append("<html>Sign in</html>")
    assert cx.sheets_read("PrivateId")[0]["name"] == "Asha Rao"


def test_sql_and_files_work_for_real(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    url = "sqlite:///shop.db"
    cx.sql_execute(url, "CREATE TABLE orders (id INTEGER, status TEXT)")
    assert cx.sql_execute(url, "INSERT INTO orders VALUES (?, ?)", [1, "open"])["rows_affected"] == 1
    assert cx.sql_query(url, "SELECT * FROM orders WHERE status = ?", ["open"]) == [{"id": 1, "status": "open"}]
    with pytest.raises(cx.ConnectorError, match="the database said"):
        cx.sql_query(url, "SELECT * FROM nope")
    with pytest.raises(cx.ConnectorError, match="unsupported database 'oracle'"):
        cx.sql_query("oracle://x", "SELECT 1")
    cx.csv_write("out.csv", [{"a": 1, "b": "x"}, {"a": 2, "c": "y"}])
    assert cx.csv_read("out.csv") == [{"a": "1", "b": "x", "c": ""}, {"a": "2", "b": "", "c": "y"}]
    with pytest.raises(cx.ConnectorError, match="there's no file"):
        cx.csv_read("missing.csv")


def test_excel_round_trip(tmp_path):
    pytest.importorskip("openpyxl")
    path = str(tmp_path / "t.xlsx")
    cx.excel_write(path, [{"name": "Asha", "amount": 1200}])
    assert cx.excel_read(path) == [{"name": "Asha", "amount": 1200}]


def test_connectors_are_use_packages(tmp_path, monkeypatch):
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    monkeypatch.chdir(tmp_path)
    src = '''use "hubspot"
use "sql"
var deals = hubspot_list("deals")
sql_execute("sqlite:///x.db", "CREATE TABLE t (n TEXT)")
sql_execute("sqlite:///x.db", "INSERT INTO t VALUES (?)", [deals[0].dealname])
var back = sql_query("sqlite:///x.db", "SELECT n FROM t")[0].n
'''
    interp = MCNInterpreter()
    with contextlib.redirect_stdout(io.StringIO()):
        interp.execute(src, quiet=True)
    assert interp._evaluator.variables["back"] == "Acme renewal"


def test_studio_connect_panel(tmp_path, monkeypatch):
    from playground_app import load
    _, client = load()
    from playground_server import secrets_api
    monkeypatch.setattr(secrets_api, "_SECRETS_FILE", tmp_path / "secrets.json")
    monkeypatch.delenv("MCN_STUDIO_MODE", raising=False)
    listed = {c["name"]: c for c in client.get("/api/connectors").get_json()["connectors"]}
    assert set(listed) >= {"sheets", "files", "sql", "hubspot", "salesforce", "airtable", "slack", "whatsapp"}
    assert listed["hubspot"]["connected"] is False and listed["files"]["connected"] is True
    res = client.post("/api/connectors/hubspot/settings", json={"HUBSPOT_TOKEN": "pat-9", "OTHER": "x"}).get_json()
    assert res["connector"]["connected"] is True
    saved = json.loads((tmp_path / "secrets.json").read_text())
    assert saved == {"HUBSPOT_TOKEN": "pat-9"}                      # only the connector's own settings
    client.post("/api/connectors/hubspot/settings", json={"HUBSPOT_TOKEN": ""})
    assert "HUBSPOT_TOKEN" not in json.loads((tmp_path / "secrets.json").read_text())
    t = client.post("/api/connectors/hubspot/test").get_json()
    assert t["success"] and t["sample"]
    monkeypatch.setenv("MCN_STUDIO_MODE", "hosted")
    assert client.post("/api/connectors/hubspot/settings", json={"HUBSPOT_TOKEN": "x"}).status_code in (401, 403)   # never shared on hosted Studio
