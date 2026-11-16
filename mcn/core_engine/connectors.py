"""
Connectors: one-line access to the systems businesses already use.

    use "sheets"          sheets_read, sheets_append, sheets_write          (Google Sheets)
    use "files"           csv_read, csv_write, excel_read, excel_write
    use "sql"             sql_query, sql_execute                            (PostgreSQL, MySQL, SQLite)
    use "hubspot"         hubspot_list, hubspot_search, hubspot_create, hubspot_update
    use "salesforce"      salesforce_query, salesforce_create, salesforce_update
    use "airtable"        airtable_list, airtable_create, airtable_update
    use "slack"           post_message                                      (webhook or bot token)
    use "whatsapp"        whatsapp_send                                      (Meta Cloud API or Twilio)

Credentials come from settings (environment variables, or Studio's Connect panel).
Without them, reads return labelled sample rows and writes are not sent, so a
program runs in Studio or in class before anyone has an account; each connector
says once what to set. A real problem (a wrong key, a missing sheet) raises a
ConnectorError that says what to check.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional


class ConnectorError(Exception):
    """A request a connector couldn't complete, with what to check."""


_NOTED: set = set()


def _note_sample(name: str, how: str) -> None:
    if name not in _NOTED:
        _NOTED.add(name)
        print(f"[{name}] Not connected yet: reads return sample data and nothing is sent. To connect: {how}")


def _env(*names: str) -> str:
    for n in names:
        v = os.getenv(n, "").strip()
        if v:
            return v
    return ""


def _request(method: str, url: str, headers: Optional[Dict[str, str]] = None, body: Any = None,
             form: Optional[Dict[str, str]] = None, timeout: float = 20) -> Any:
    """One HTTP call; JSON in, JSON (or text) out. Tests replace this function."""
    data = None
    headers = dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif body is not None:
        data = json.dumps(body).encode()
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        try:
            j = json.loads(detail)
            err = j.get("error")
            detail = j.get("message") or (err.get("message") if isinstance(err, dict) else err) or detail
        except Exception:
            pass
        raise ConnectorError(f"{exc.code} from {urllib.parse.urlparse(url).netloc}: {detail}")
    except urllib.error.URLError as exc:
        raise ConnectorError(f"couldn't reach {urllib.parse.urlparse(url).netloc}: {exc.reason}")
    try:
        return json.loads(raw) if raw.strip() else {}
    except ValueError:
        return raw


# ── Google Sheets ────────────────────────────────────────────────────────────

_SHEETS_HOW = ("share the sheet with 'Anyone with the link' to read it, or set GOOGLE_SERVICE_ACCOUNT "
               "(a service account's JSON, with the sheet shared to its email) to read and write; run `mcn add sheets`")


def _sheet_id(sheet: str) -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", str(sheet))
    return m.group(1) if m else str(sheet).strip()


def _google_token() -> str:
    raw = _env("GOOGLE_SERVICE_ACCOUNT", "GOOGLE_APPLICATION_CREDENTIALS")
    if not raw:
        return ""
    try:
        info = json.loads(raw) if raw.lstrip().startswith("{") else json.loads(open(raw, encoding="utf-8").read())
    except Exception as exc:
        raise ConnectorError(f"GOOGLE_SERVICE_ACCOUNT should be a service account's JSON or a path to it ({exc})")
    try:
        from google.oauth2 import service_account  # type: ignore
        import google.auth.transport.requests  # type: ignore
    except ImportError:
        raise ConnectorError("Google Sheets support isn't installed. Run: mcn add sheets")
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _rows_from_values(values: List[List[Any]]) -> List[Dict[str, Any]]:
    if not values:
        return []
    head = [str(h).strip() or f"column_{i + 1}" for i, h in enumerate(values[0])]
    return [{head[i]: (row[i] if i < len(row) else "") for i in range(len(head))} for row in values[1:]]


def _sample_sheet() -> List[Dict[str, Any]]:
    return [{"name": "Asha Rao", "email": "asha@example.com", "status": "Active", "amount": "1200"},
            {"name": "Ravi Menon", "email": "ravi@example.com", "status": "Pending", "amount": "450"},
            {"name": "Meera Iyer", "email": "meera@example.com", "status": "Active", "amount": "980"}]


def sheets_read(sheet: str, tab: str = "") -> List[Dict[str, Any]]:
    """Rows of a Google Sheet as maps, using the first row as the column names.
    `sheet` is the sheet's link or id; `tab` the tab's name (the first tab by default)."""
    sid = _sheet_id(sheet)
    token = _google_token()
    key = _env("GOOGLE_SHEETS_API_KEY")
    rng = urllib.parse.quote(tab or "A:ZZ", safe="")
    if token or key:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{rng}" + (f"?key={key}" if key and not token else "")
        res = _request("GET", url, headers={"Authorization": f"Bearer {token}"} if token else None)
        return _rows_from_values(res.get("values", []) if isinstance(res, dict) else [])
    # A sheet shared with "Anyone with the link" reads without any key
    if sid and sid not in ("demo", "sample"):
        url = (f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv"
               + (f"&sheet={urllib.parse.quote(tab)}" if tab else ""))
        try:
            text = _request("GET", url)
            if isinstance(text, str) and not text.lstrip().startswith("<"):
                return [dict(r) for r in csv.DictReader(io.StringIO(text))]
        except ConnectorError:
            pass
    _note_sample("sheets", _SHEETS_HOW)
    return _sample_sheet()


def _sheet_header(sid: str, tab: str, token: str) -> List[str]:
    rng = urllib.parse.quote(f"{tab}!1:1" if tab else "1:1", safe="")
    res = _request("GET", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{rng}",
                   headers={"Authorization": f"Bearer {token}"})
    vals = res.get("values", []) if isinstance(res, dict) else []
    return [str(h) for h in vals[0]] if vals else []


def sheets_append(sheet: str, row: Dict[str, Any], tab: str = "") -> Dict[str, Any]:
    """Add a row (a map) at the bottom of a sheet, matching the sheet's column names."""
    token = _google_token()
    if not token:
        _note_sample("sheets", _SHEETS_HOW)
        return {"success": True, "sample": True, "row": row}
    sid = _sheet_id(sheet)
    head = _sheet_header(sid, tab, token) or list(row)
    values = [[row.get(h, "") for h in head]]
    rng = urllib.parse.quote(tab or "A1", safe="")
    _request("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{rng}:append"
                     "?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS",
             headers={"Authorization": f"Bearer {token}"}, body={"values": values})
    return {"success": True, "row": row}


def sheets_write(sheet: str, rows: List[Dict[str, Any]], tab: str = "") -> Dict[str, Any]:
    """Replace a sheet's contents with rows (maps): the keys become the first row."""
    token = _google_token()
    if not token:
        _note_sample("sheets", _SHEETS_HOW)
        return {"success": True, "sample": True, "rows": len(rows or [])}
    sid = _sheet_id(sheet)
    head: List[str] = []
    for r in rows or []:
        head += [k for k in r if k not in head]
    values = [head] + [[r.get(h, "") for h in head] for r in rows or []]
    rng = urllib.parse.quote(tab or "A1", safe="")
    _request("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{urllib.parse.quote(tab or 'A:ZZ', safe='')}:clear",
             headers={"Authorization": f"Bearer {token}"}, body={})
    _request("PUT", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{rng}?valueInputOption=USER_ENTERED",
             headers={"Authorization": f"Bearer {token}"}, body={"values": values})
    return {"success": True, "rows": len(rows or [])}


# ── Files: CSV and Excel ─────────────────────────────────────────────────────

def csv_read(path: str, delimiter: str = ",") -> List[Dict[str, Any]]:
    """Rows of a CSV file as maps (the first line names the columns)."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return [dict(r) for r in csv.DictReader(f, delimiter=delimiter)]
    except FileNotFoundError:
        raise ConnectorError(f"there's no file '{path}'")


def csv_write(path: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Write rows (maps) to a CSV file; the keys become the header."""
    head: List[str] = []
    for r in rows or []:
        head += [k for k in r if k not in head]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=head)
        w.writeheader()
        for r in rows or []:
            w.writerow({k: r.get(k, "") for k in head})
    return {"success": True, "rows": len(rows or []), "path": path}


def _openpyxl():
    try:
        import openpyxl  # type: ignore
        return openpyxl
    except ImportError:
        raise ConnectorError("Excel support isn't installed. Run: mcn add excel")


def excel_read(path: str, sheet: str = "") -> List[Dict[str, Any]]:
    """Rows of an Excel sheet (.xlsx) as maps (the first row names the columns)."""
    xl = _openpyxl()
    try:
        wb = xl.load_workbook(path, read_only=True, data_only=True)
    except FileNotFoundError:
        raise ConnectorError(f"there's no file '{path}'")
    ws = wb[sheet] if sheet else wb.worksheets[0]
    values = [["" if c is None else c for c in row] for row in ws.iter_rows(values_only=True)]
    return _rows_from_values(values)


def excel_write(path: str, rows: List[Dict[str, Any]], sheet: str = "Sheet1") -> Dict[str, Any]:
    """Write rows (maps) to an Excel file; the keys become the first row."""
    xl = _openpyxl()
    wb = xl.Workbook()
    ws = wb.active
    ws.title = sheet or "Sheet1"
    head: List[str] = []
    for r in rows or []:
        head += [k for k in r if k not in head]
    ws.append(head)
    for r in rows or []:
        ws.append([r.get(h, "") for h in head])
    wb.save(path)
    return {"success": True, "rows": len(rows or []), "path": path}


# ── SQL databases ────────────────────────────────────────────────────────────

def _sql_connect(url: str):
    url = str(url or "").strip()
    if not url:
        raise ConnectorError("sql_query needs a database URL, such as env(\"CRM_DATABASE_URL\")")
    scheme = url.split(":", 1)[0].lower()
    if scheme in ("postgres", "postgresql"):
        try:
            import psycopg2  # type: ignore
        except ImportError:
            raise ConnectorError("PostgreSQL support isn't installed. Run: mcn add postgres")
        return psycopg2.connect(url), "%s"
    if scheme in ("mysql", "mariadb"):
        try:
            import pymysql  # type: ignore
        except ImportError:
            raise ConnectorError("MySQL support isn't installed. Run: mcn add mysql")
        p = urllib.parse.urlparse(url)
        return pymysql.connect(host=p.hostname, port=p.port or 3306, user=urllib.parse.unquote(p.username or ""),
                               password=urllib.parse.unquote(p.password or ""), database=p.path.lstrip("/"),
                               cursorclass=pymysql.cursors.DictCursor), "%s"
    if scheme == "sqlite":
        import sqlite3
        # sqlite:///data.db is relative to the app's folder, sqlite:////var/data.db absolute
        path = url[len("sqlite:///"):] if url.startswith("sqlite:///") else url[len("sqlite:"):]
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn, "?"
    raise ConnectorError(f"unsupported database '{scheme}': use postgres://, mysql:// or sqlite:///path")


def _params(params: Any) -> tuple:
    if params is None:
        return ()
    return tuple(params) if isinstance(params, (list, tuple)) else (params,)


def sql_query(url: str, sql: str, params: Any = None) -> List[Dict[str, Any]]:
    """Rows from another database (PostgreSQL, MySQL or SQLite) as maps. Use ? for values."""
    conn, mark = _sql_connect(url)
    try:
        cur = conn.cursor()
        cur.execute(sql.replace("?", mark) if mark != "?" else sql, _params(params))
        rows = cur.fetchall()
        if rows and not isinstance(rows[0], dict):
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in rows]
        return [dict(r) for r in rows]
    except ConnectorError:
        raise
    except Exception as exc:
        raise ConnectorError(f"the database said: {exc}")
    finally:
        conn.close()


def sql_execute(url: str, sql: str, params: Any = None) -> Dict[str, Any]:
    """Run an INSERT, UPDATE or DELETE on another database. Use ? for values."""
    conn, mark = _sql_connect(url)
    try:
        cur = conn.cursor()
        cur.execute(sql.replace("?", mark) if mark != "?" else sql, _params(params))
        conn.commit()
        return {"success": True, "rows_affected": cur.rowcount}
    except Exception as exc:
        raise ConnectorError(f"the database said: {exc}")
    finally:
        conn.close()


# ── HubSpot ──────────────────────────────────────────────────────────────────

_HUBSPOT_HOW = "set HUBSPOT_TOKEN (a private app's access token: HubSpot → Settings → Integrations → Private apps)"
_HUBSPOT_PROPS = {
    "contacts":  ["firstname", "lastname", "email", "phone", "company", "lifecyclestage"],
    "companies": ["name", "domain", "industry", "city", "phone"],
    "deals":     ["dealname", "amount", "dealstage", "closedate", "pipeline"],
    "tickets":   ["subject", "content", "hs_pipeline_stage", "hs_ticket_priority"],
}
_HUBSPOT_SAMPLE = {
    "contacts":  [{"id": "101", "firstname": "Asha", "lastname": "Rao", "email": "asha@example.com", "company": "Acme"},
                  {"id": "102", "firstname": "Ravi", "lastname": "Menon", "email": "ravi@example.com", "company": "Globex"}],
    "companies": [{"id": "201", "name": "Acme", "domain": "acme.example", "industry": "Software"}],
    "deals":     [{"id": "301", "dealname": "Acme renewal", "amount": "24000", "dealstage": "contractsent"},
                  {"id": "302", "dealname": "Globex pilot", "amount": "8000", "dealstage": "qualifiedtobuy"}],
    "tickets":   [{"id": "401", "subject": "Can't log in", "hs_ticket_priority": "HIGH"}],
}


def _hubspot(method: str, path: str, body: Any = None) -> Any:
    return _request(method, "https://api.hubapi.com" + path,
                    headers={"Authorization": f"Bearer {_env('HUBSPOT_TOKEN')}"}, body=body)


def _flat(obj: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": obj.get("id"), **(obj.get("properties") or {})}


def hubspot_list(object_type: str = "contacts", limit: int = 20) -> List[Dict[str, Any]]:
    """HubSpot records (contacts, companies, deals, tickets) as maps with their main fields."""
    kind = str(object_type).lower()
    if not _env("HUBSPOT_TOKEN"):
        _note_sample("hubspot", _HUBSPOT_HOW)
        return [dict(r) for r in _HUBSPOT_SAMPLE.get(kind, [])][: int(limit)]
    props = ",".join(_HUBSPOT_PROPS.get(kind, []))
    res = _hubspot("GET", f"/crm/v3/objects/{kind}?limit={int(limit)}" + (f"&properties={props}" if props else ""))
    return [_flat(o) for o in res.get("results", [])]


def hubspot_search(object_type: str, text: str, limit: int = 20) -> List[Dict[str, Any]]:
    """HubSpot records matching some text (a name, an email, a company)."""
    kind = str(object_type).lower()
    if not _env("HUBSPOT_TOKEN"):
        _note_sample("hubspot", _HUBSPOT_HOW)
        t = str(text).lower()
        return [dict(r) for r in _HUBSPOT_SAMPLE.get(kind, []) if t in json.dumps(r).lower()]
    res = _hubspot("POST", f"/crm/v3/objects/{kind}/search",
                   {"query": str(text), "limit": int(limit), "properties": _HUBSPOT_PROPS.get(kind, [])})
    return [_flat(o) for o in res.get("results", [])]


def hubspot_create(object_type: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Create a HubSpot record from a map of its fields; returns it with its id."""
    kind = str(object_type).lower()
    if not _env("HUBSPOT_TOKEN"):
        _note_sample("hubspot", _HUBSPOT_HOW)
        return {"id": "sample", **fields, "sample": True}
    return _flat(_hubspot("POST", f"/crm/v3/objects/{kind}", {"properties": fields}))


def hubspot_update(object_type: str, record_id: Any, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Change some fields of a HubSpot record."""
    kind = str(object_type).lower()
    if not _env("HUBSPOT_TOKEN"):
        _note_sample("hubspot", _HUBSPOT_HOW)
        return {"id": str(record_id), **fields, "sample": True}
    return _flat(_hubspot("PATCH", f"/crm/v3/objects/{kind}/{record_id}", {"properties": fields}))


# ── Salesforce ───────────────────────────────────────────────────────────────

_SF_HOW = "set SALESFORCE_INSTANCE_URL (like https://yourcompany.my.salesforce.com) and SALESFORCE_TOKEN (an access token)"
_SF_SAMPLE = [{"Id": "001S1", "Name": "Acme Corporation", "Industry": "Technology"},
              {"Id": "001S2", "Name": "Globex", "Industry": "Manufacturing"}]


def _sf(method: str, path: str, body: Any = None) -> Any:
    base = _env("SALESFORCE_INSTANCE_URL").rstrip("/")
    return _request(method, f"{base}/services/data/v60.0{path}",
                    headers={"Authorization": f"Bearer {_env('SALESFORCE_TOKEN')}"}, body=body)


def _sf_ready() -> bool:
    return bool(_env("SALESFORCE_INSTANCE_URL") and _env("SALESFORCE_TOKEN"))


def salesforce_query(soql: str) -> List[Dict[str, Any]]:
    """Records from a SOQL query, like "SELECT Id, Name FROM Account LIMIT 10"."""
    if not _sf_ready():
        _note_sample("salesforce", _SF_HOW)
        return [dict(r) for r in _SF_SAMPLE]
    res = _sf("GET", "/query?q=" + urllib.parse.quote(soql))
    return [{k: v for k, v in r.items() if k != "attributes"} for r in res.get("records", [])]


def salesforce_create(object_name: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Create a record (Account, Contact, Lead, Opportunity...) from a map of fields."""
    if not _sf_ready():
        _note_sample("salesforce", _SF_HOW)
        return {"id": "sample", "success": True, "sample": True}
    res = _sf("POST", f"/sobjects/{object_name}", fields)
    return {"id": res.get("id"), "success": bool(res.get("success", True))}


def salesforce_update(object_name: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Change some fields of a record."""
    if not _sf_ready():
        _note_sample("salesforce", _SF_HOW)
        return {"id": record_id, "success": True, "sample": True}
    _sf("PATCH", f"/sobjects/{object_name}/{record_id}", fields)
    return {"id": record_id, "success": True}


# ── Airtable ─────────────────────────────────────────────────────────────────

_AIRTABLE_HOW = "set AIRTABLE_TOKEN (a personal access token: airtable.com/create/tokens)"


def _airtable(method: str, base: str, table: str, suffix: str = "", body: Any = None) -> Any:
    url = f"https://api.airtable.com/v0/{base}/{urllib.parse.quote(table)}{suffix}"
    return _request(method, url, headers={"Authorization": f"Bearer {_env('AIRTABLE_TOKEN')}"}, body=body)


def airtable_list(base: str, table: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Records of an Airtable table as maps (with their id)."""
    if not _env("AIRTABLE_TOKEN"):
        _note_sample("airtable", _AIRTABLE_HOW)
        return _sample_sheet()
    res = _airtable("GET", base, table, f"?maxRecords={int(limit)}")
    return [{"id": r.get("id"), **(r.get("fields") or {})} for r in res.get("records", [])]


def airtable_create(base: str, table: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Add a record to an Airtable table."""
    if not _env("AIRTABLE_TOKEN"):
        _note_sample("airtable", _AIRTABLE_HOW)
        return {"id": "sample", **fields, "sample": True}
    res = _airtable("POST", base, table, body={"records": [{"fields": fields}]})
    rec = (res.get("records") or [{}])[0]
    return {"id": rec.get("id"), **(rec.get("fields") or {})}


def airtable_update(base: str, table: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Change some fields of an Airtable record."""
    if not _env("AIRTABLE_TOKEN"):
        _note_sample("airtable", _AIRTABLE_HOW)
        return {"id": record_id, **fields, "sample": True}
    rec = _airtable("PATCH", base, table, f"/{record_id}", body={"fields": fields})
    return {"id": rec.get("id"), **(rec.get("fields") or {})}


# ── Slack ────────────────────────────────────────────────────────────────────

def post_message(channel: str, text: str, webhook_url: str = "") -> Dict[str, Any]:
    """Post a message to Slack, with SLACK_WEBHOOK_URL (one channel) or SLACK_BOT_TOKEN (any channel)."""
    url = webhook_url or _env("SLACK_WEBHOOK_URL")
    token = _env("SLACK_BOT_TOKEN")
    if url:
        _request("POST", url, body={"text": text})
        return {"ok": True}
    if token:
        res = _request("POST", "https://slack.com/api/chat.postMessage",
                       headers={"Authorization": f"Bearer {token}"}, body={"channel": channel, "text": text})
        if isinstance(res, dict) and not res.get("ok", False):
            raise ConnectorError(f"Slack said: {res.get('error', 'not ok')}")
        return {"ok": True, "ts": res.get("ts") if isinstance(res, dict) else None}
    _note_sample("slack", "set SLACK_WEBHOOK_URL (an incoming webhook) or SLACK_BOT_TOKEN")
    return {"ok": True, "sample": True, "channel": channel, "text": text}


# ── WhatsApp ─────────────────────────────────────────────────────────────────

def whatsapp_send(to: str, text: str) -> Dict[str, Any]:
    """Send a WhatsApp message (WHATSAPP_TOKEN and WHATSAPP_PHONE_ID for Meta's Cloud API,
    or TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM for Twilio)."""
    number = re.sub(r"[^\d+]", "", str(to))
    if _env("WHATSAPP_TOKEN") and _env("WHATSAPP_PHONE_ID"):
        res = _request("POST", f"https://graph.facebook.com/v20.0/{_env('WHATSAPP_PHONE_ID')}/messages",
                       headers={"Authorization": f"Bearer {_env('WHATSAPP_TOKEN')}"},
                       body={"messaging_product": "whatsapp", "to": number.lstrip("+"), "type": "text",
                             "text": {"body": str(text)}})
        msg = (res.get("messages") or [{}])[0] if isinstance(res, dict) else {}
        return {"success": True, "id": msg.get("id")}
    sid, auth, frm = _env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN"), _env("TWILIO_WHATSAPP_FROM", "TWILIO_FROM_NUMBER")
    if sid and auth and frm:
        import base64
        basic = base64.b64encode(f"{sid}:{auth}".encode()).decode()
        res = _request("POST", f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                       headers={"Authorization": f"Basic {basic}"},
                       form={"From": f"whatsapp:{frm.replace('whatsapp:', '')}", "To": f"whatsapp:{number}", "Body": str(text)})
        return {"success": True, "id": res.get("sid") if isinstance(res, dict) else None}
    _note_sample("whatsapp", "set WHATSAPP_TOKEN and WHATSAPP_PHONE_ID (Meta), or TWILIO_ACCOUNT_SID, "
                             "TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM (Twilio)")
    return {"success": True, "sample": True, "to": number, "text": text}


# ── The catalog: packages, settings, what Studio shows ───────────────────────

CATALOG: Dict[str, Dict[str, Any]] = {
    "sheets": {
        "ready": lambda: bool(_env("GOOGLE_SERVICE_ACCOUNT", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_SHEETS_API_KEY")),
        "title": "Google Sheets", "what": "Read, add and replace rows in a Google Sheet",
        "functions": {"sheets_read": sheets_read, "sheets_append": sheets_append, "sheets_write": sheets_write},
        "settings": [("GOOGLE_SERVICE_ACCOUNT", "Service account JSON (to write; share the sheet with its email)", True),
                     ("GOOGLE_SHEETS_API_KEY", "API key (optional: reads sheets shared with a link)", True)],
        "install": "sheets",
        "example": 'use "sheets"\nvar rows = sheets_read("https://docs.google.com/spreadsheets/d/…", "Leads")\nsheets_append("…", {name: "Asha", email: "asha@example.com"}, "Leads")',
        "test": None,
    },
    "files": {
        "ready": lambda: True,
        "title": "CSV and Excel", "what": "Read and write .csv and .xlsx files",
        "functions": {"csv_read": csv_read, "csv_write": csv_write, "excel_read": excel_read, "excel_write": excel_write},
        "settings": [], "install": "excel",
        "example": 'use "files"\nvar rows = excel_read("orders.xlsx")\ncsv_write("report.csv", rows)',
        "test": None,
    },
    "sql": {
        "ready": lambda: bool(_env("EXTERNAL_DATABASE_URL")),
        "title": "SQL databases", "what": "Query another PostgreSQL, MySQL or SQLite database",
        "functions": {"sql_query": sql_query, "sql_execute": sql_execute},
        "settings": [("EXTERNAL_DATABASE_URL", "Database URL (postgres://, mysql:// or sqlite:///path)", True)],
        "install": "postgres",
        "example": 'use "sql"\nvar orders = sql_query(env("EXTERNAL_DATABASE_URL"), "SELECT * FROM orders WHERE status = ?", ["open"])',
        "test": lambda: sql_query(_env("EXTERNAL_DATABASE_URL"), "SELECT 1 AS ok") if _env("EXTERNAL_DATABASE_URL") else None,
    },
    "hubspot": {
        "ready": lambda: bool(_env("HUBSPOT_TOKEN")),
        "title": "HubSpot", "what": "Contacts, companies, deals and tickets",
        "functions": {"hubspot_list": hubspot_list, "hubspot_search": hubspot_search,
                      "hubspot_create": hubspot_create, "hubspot_update": hubspot_update},
        "settings": [("HUBSPOT_TOKEN", "Private app access token", True)], "install": None,
        "example": 'use "hubspot"\nvar deals = hubspot_list("deals", 50)\nhubspot_create("contacts", {firstname: "Asha", email: "asha@example.com"})',
        "test": lambda: hubspot_list("contacts", 1),
    },
    "salesforce": {
        "ready": _sf_ready,
        "title": "Salesforce", "what": "SOQL queries, and creating and updating records",
        "functions": {"salesforce_query": salesforce_query, "salesforce_create": salesforce_create,
                      "salesforce_update": salesforce_update},
        "settings": [("SALESFORCE_INSTANCE_URL", "Instance URL", False), ("SALESFORCE_TOKEN", "Access token", True)],
        "install": None,
        "example": 'use "salesforce"\nvar accounts = salesforce_query("SELECT Id, Name FROM Account LIMIT 20")',
        "test": lambda: salesforce_query("SELECT Id FROM Account LIMIT 1"),
    },
    "airtable": {
        "ready": lambda: bool(_env("AIRTABLE_TOKEN")),
        "title": "Airtable", "what": "Records in Airtable bases",
        "functions": {"airtable_list": airtable_list, "airtable_create": airtable_create, "airtable_update": airtable_update},
        "settings": [("AIRTABLE_TOKEN", "Personal access token", True)], "install": None,
        "example": 'use "airtable"\nvar rows = airtable_list("appXXXXXXXX", "Orders")',
        "test": None,
    },
    "slack": {
        "ready": lambda: bool(_env("SLACK_WEBHOOK_URL", "SLACK_BOT_TOKEN")),
        "title": "Slack", "what": "Post messages to channels",
        "functions": {"post_message": post_message},
        "settings": [("SLACK_WEBHOOK_URL", "Incoming webhook URL (one channel)", True),
                     ("SLACK_BOT_TOKEN", "Bot token (any channel the bot is in)", True)], "install": None,
        "example": 'use "slack"\npost_message("#sales", "New deal: Acme, $24,000")',
        "test": None,
    },
    "whatsapp": {
        "ready": lambda: bool((_env("WHATSAPP_TOKEN") and _env("WHATSAPP_PHONE_ID")) or (_env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN"))),
        "title": "WhatsApp", "what": "Send WhatsApp messages (Meta Cloud API or Twilio)",
        "functions": {"whatsapp_send": whatsapp_send},
        "settings": [("WHATSAPP_TOKEN", "Meta access token", True), ("WHATSAPP_PHONE_ID", "Meta phone number id", False),
                     ("TWILIO_ACCOUNT_SID", "Or Twilio account SID", False), ("TWILIO_AUTH_TOKEN", "Twilio auth token", True),
                     ("TWILIO_WHATSAPP_FROM", "Twilio WhatsApp number", False)], "install": None,
        "example": 'use "whatsapp"\nwhatsapp_send("+919876543210", "Your order is on its way")',
        "test": None,
    },
}


def package(name: str) -> Optional[Dict[str, Callable]]:
    entry = CATALOG.get(name)
    return dict(entry["functions"]) if entry else None


def status() -> List[Dict[str, Any]]:
    """Every connector, whether its settings are present, for Studio's Connect panel."""
    out = []
    for name, c in CATALOG.items():
        settings = [{"key": k, "label": label, "secret": secret, "set": bool(_env(k))} for k, label, secret in c["settings"]]
        out.append({"name": name, "title": c["title"], "what": c["what"], "functions": list(c["functions"]),
                    "settings": settings, "connected": bool(c["ready"]()), "install": c["install"],
                    "example": c["example"], "testable": c["test"] is not None})
    return out


def test(name: str) -> Dict[str, Any]:
    """Try a connector with its current settings: a small read."""
    c = CATALOG.get(name)
    if not c:
        raise ConnectorError(f"there's no connector '{name}'")
    if c["test"] is None:
        return {"success": True, "message": "Nothing to try for this one; use it from your code."}
    _NOTED.discard(name)
    result = c["test"]()
    if result is None:
        return {"success": False, "message": "Add its settings first."}
    rows = result if isinstance(result, list) else [result]
    sample = any(isinstance(r, dict) and r.get("sample") for r in rows) or name in _NOTED
    return {"success": True, "sample": sample, "rows": len(rows),
            "message": ("Not connected yet: this is sample data." if sample else f"Connected: read {len(rows)} row(s).")}
