"""
Platform features: triggers, scheduled jobs, approvals, files, PDF, email,
CSV import/export, field-level permissions, single sign-on and PWA output.
"""

import base64
import json
import os
import sys
import threading
import urllib.parse
from datetime import datetime
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

import pytest

from mcn.core_engine.lexer import Lexer
from mcn.core_engine.mcn_interpreter import MCNInterpreter
from mcn.core_engine.parser import ParseError, Parser

APP = '''
auth
    roles admin, manager, staff

contract Customer
    name: str unique

contract Expense
    title:    str
    amount:   float
    customer: ref Customer?
    receipt:  file?
    note:     str?  read admin, manager  write admin, manager

service finance
    crud Customer
    crud Expense
        approval
            approvers admin, manager
            when record.amount > 10000
        import
        export
        audit

    on create Expense
        events = events + ["created " + record.title + " " + record.approval_status]

    on update Expense
        if changed("amount")
            events = events + ["amount " + old.amount + " -> " + record.amount]

    on approve Expense
        var pdf = make_pdf("Approved", [record.title, [["Item", "Amount"], [record.title, record.amount]]])
        send_email("finance@acme.in", "Approved: {record.title}", "Attached.", [pdf])

    job digest every day at "09:00"
        send_email("boss@acme.in", "Digest", "{list_expenses({approval_status: 'pending'}).total} pending")

var events = []
create_user({name: "Ada", email: "admin@x.in", role: "admin", password: "adminpass1"})
create_user({name: "Mo", email: "mgr@x.in", role: "manager", password: "mgrpass12"})
create_user({name: "Sid", email: "staff@x.in", role: "staff", password: "staffpass1"})
'''


@pytest.fixture
def app(tmp_path, monkeypatch):
    from mcn.core_engine.mcn_server import _make_handler
    monkeypatch.chdir(tmp_path)
    for k in ("MCN_SECRET", "MCN_SMTP_HOST", "MCN_APP_URL"):
        monkeypatch.delenv(k, raising=False)
    interp = MCNInterpreter()
    interp.execute(APP, quiet=True)
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(interp._evaluator))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"

    def call(path, body=None, as_=None, raw=False):
        headers = {"Content-Type": "application/json"}
        if as_:
            headers["Authorization"] = "Bearer " + tokens[as_]
        data = json.dumps(body).encode() if body is not None else None
        try:
            with urlopen(Request(path if path.startswith("http") else base + path,
                                 data=data, headers=headers)) as r:
                payload = r.read()
                return r.status, (payload if raw else json.loads(payload))
        except HTTPError as e:
            return e.code, json.loads(e.read())

    call.base = base
    tokens = {}
    for who, pw in (("admin", "adminpass1"), ("mgr", "mgrpass12"), ("staff", "staffpass1")):
        tokens[who] = call("/login", {"email": f"{who}@x.in", "password": pw})[1]["token"]
    yield call, interp
    httpd.shutdown()


# ── syntax ────────────────────────────────────────────────────────────────────

def test_parse_platform_syntax():
    body = Parser(Lexer(APP).tokenize()).parse().body
    exp = body[2]
    assert [f.type_name for f in exp.fields][3] == "file"
    assert (exp.fields[4].read_roles, exp.fields[4].write_roles) == (["admin", "manager"], ["admin", "manager"])
    svc = body[3]
    crud = svc.cruds[1]
    assert crud.approval.approvers == ["admin", "manager"] and crud.csv_import and crud.csv_export
    assert [(t.event, t.contract) for t in svc.triggers] == [("create", "Expense"), ("update", "Expense"),
                                                              ("approve", "Expense")]
    assert [(j.name, j.every, j.unit, j.at) for j in svc.jobs] == [("digest", 1, "day", "09:00")]


@pytest.mark.parametrize("src,msg", [
    ("service s\n    job x every 5 minutes at \"09:00\"\n        log(1)\n", "'at' only works"),
    ("service s\n    job x every fortnight\n        log(1)\n", "Unknown schedule 'fortnight'"),
    ("service s\n    on archive Lead\n        log(1)\n", "Unknown trigger 'archive'"),
    ("service s\n    crud A\n        approval\n            when true\n", "approval needs an 'approvers'"),
])
def test_platform_syntax_errors(src, msg):
    with pytest.raises(ParseError, match=msg):
        Parser(Lexer(src).tokenize()).parse()


def test_trigger_needs_crud(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exception, match="add 'crud Lead'"):
        MCNInterpreter().execute("contract Lead\n    name: str\nservice s\n    on create Lead\n        log(1)\n",
                                 quiet=True)


# ── triggers, approvals, field permissions ───────────────────────────────────

def test_triggers_and_approvals(app):
    call, interp = app
    _, small = call("/create_expense", {"title": "Taxi", "amount": 450}, "staff")
    _, big = call("/create_expense", {"title": "Laptop", "amount": 95000}, "staff")
    assert (small["approval_status"], big["approval_status"]) == ("approved", "pending")
    assert call("/approve_expense", {"id": big["id"]}, "staff")[0] == 403            # not an approver
    _, own = call("/create_expense", {"title": "Trip", "amount": 20000}, "mgr")
    assert call("/approve_expense", {"id": own["id"]}, "mgr")[1]["error"] == "You can't approve your own request"
    s, ok = call("/approve_expense", {"id": big["id"], "note": "Q4"}, "mgr")
    assert s == 200 and ok["approval_status"] == "approved" and ok["approval_by"] == "mgr@x.in"
    assert call("/approve_expense", {"id": big["id"]}, "admin")[0] == 400             # not pending
    _, edited = call("/update_expense", {"id": small["id"], "amount": 15000}, "staff")
    assert edited["approval_status"] == "pending"                                      # back for approval
    assert call("/list_expenses?approval_status=pending", None, "admin")[1]["total"] == 2
    events = interp.variables["events"]
    assert events[:2] == ["created Taxi approved", "created Laptop pending"]
    assert "amount 450.0 -> 15000.0" in events
    outbox = call("/list_outbox", None, "admin")[1]["items"]
    assert outbox[0]["subject"] == "Approved: Laptop" and "approved.pdf" in outbox[0]["attachments"]
    log = [e["action"] for e in call("/list_audit_log?entity=Expense", None, "admin")[1]["items"]]
    assert "approve" in log


def test_field_permissions(app):
    call, _ = app
    s, err = call("/create_expense", {"title": "X", "amount": 1, "note": "hi"}, "staff")
    assert s == 400 and err["errors"]["note"] == "can't be changed with your role"
    _, row = call("/create_expense", {"title": "Y", "amount": 1, "note": "secret"}, "mgr")
    assert row["note"] == "secret"
    assert "note" not in call(f"/get_expense/{row['id']}", None, "staff")[1]
    assert all("note" not in r for r in call("/list_expenses", None, "staff")[1]["items"])
    assert call("/list_expenses?sort=note", None, "staff")[0] == 400


# ── files, PDF, email ─────────────────────────────────────────────────────────

def test_upload_and_signed_download(app):
    call, _ = app
    s, f = call("/upload", {"name": "../../etc/receipt.txt", "type": "text/plain",
                            "data": base64.b64encode(b"Taxi 450").decode()}, "staff")
    assert s == 200 and f["name"] == "receipt.txt"                       # path stripped
    _, row = call("/create_expense", {"title": "Taxi", "amount": 450, "receipt": f["id"]}, "staff")
    assert row["receipt_file"]["name"] == "receipt.txt"
    assert call("/create_expense", {"title": "T", "amount": 1, "receipt": 999}, "staff")[1]["errors"] == \
        {"receipt": "must be an uploaded file"}
    url = row["receipt_file"]["url"]
    assert call(url, raw=True) == (200, b"Taxi 450")                     # signed link, no token
    assert call(url.replace("sig=", "sig=0"))[0] == 403
    assert call("/upload", {"name": "a", "data": "not base64!"}, "staff")[0] == 400
    assert call("/upload", {"name": "a", "data": "eA=="})[0] == 401      # signed in only


def test_pdf_is_valid():
    from mcn.core_engine.files import build_pdf
    data = build_pdf("Report ₹ “x”", ["Para " * 200, {"heading": "Rows"},
                                       [{"name": f"r{i}", "v": i} for i in range(150)]])
    assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")
    assert data.count(b"/Type /Page ") >= 3                             # multi-page
    try:
        import pypdf, io
        reader = pypdf.PdfReader(io.BytesIO(data))
        assert "Rs" in reader.pages[0].extract_text()
    except ImportError:
        pass


def test_smtp_delivery(tmp_path, monkeypatch):
    import smtplib
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None): sent.append(("connect", host, port))
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self): sent.append(("tls",))
        def login(self, u, p): sent.append(("login", u))
        def send_message(self, msg): sent.append(("msg", msg["To"], msg["Subject"],
                                                  [a.get_filename() for a in msg.iter_attachments()]))
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCN_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("MCN_SMTP_USER", "bot@example.com")
    interp = MCNInterpreter()
    interp.execute('var pdf = make_pdf("Hi", "Body")\nsend_email("a@x.in, b@x.in", "Hello", "Hi!", [pdf])\n',
                   quiet=True)
    assert sent[0] == ("connect", "smtp.example.com", 587) and ("tls",) in sent
    assert sent[-1] == ("msg", "a@x.in, b@x.in", "Hello", ["hi.pdf"])
    with pytest.raises(Exception, match="is not an email address"):
        interp.execute('send_email("nope", "x", "y")\n', quiet=True)


# ── CSV ───────────────────────────────────────────────────────────────────────

def test_csv_import_export(app):
    call, _ = app
    call("/create_customer", {"name": "Finly"}, "admin")
    csv = "title,amount,customer\nPens,120,Finly\nChair,abc,Nowhere\nDesk,25000,\n"
    s, res = call("/import_expenses", {"csv": csv}, "staff")
    assert s == 200 and res["created"] == 2 and res["total"] == 3
    assert res["failed"] == [{"line": 3, "errors": {"amount": "must be a number",
                                                    "customer": "no customer named 'Nowhere'"}}]
    assert call("/import_expenses", {"csv": "title,amount,note\nA,1,x\n"}, "staff")[0] == 400
    assert call("/import_expenses", {"csv": "title,bogus\nA,1\n"}, "staff")[1]["error"].startswith("Unknown column 'bogus'")
    _, out = call("/export_expenses", None, "staff")
    lines = out["content"].strip().splitlines()
    assert lines[0].split(",")[:4] == ["id", "title", "amount", "customer"] and "note" not in lines[0]
    assert "Finly" in lines[1] and out["filename"].startswith("expenses-")


# ── jobs ──────────────────────────────────────────────────────────────────────

def test_jobs(app):
    from mcn.core_engine.workflow import Scheduler, next_run
    call, interp = app
    jobs = call("/list_jobs", None, "admin")[1]["items"]
    assert jobs[0]["name"] == "digest" and jobs[0]["schedule"] == "every day at 09:00"
    assert call("/list_jobs", None, "staff")[0] == 403
    assert call("/run_job", {"name": "digest"}, "admin")[1]["last_status"] == "ok"
    assert call("/list_outbox", None, "admin")[1]["items"][0]["body"] == "0 pending"
    job = interp._evaluator.jobs[0]
    sched = Scheduler([job], interp._evaluator.lock)
    assert sched.tick(job.next_run) == ["digest"] and job.next_run > datetime.now()
    monday = datetime(2026, 11, 2, 10, 7)
    assert next_run(15, "minute", "", monday) == datetime(2026, 11, 2, 10, 15)
    assert next_run(1, "friday", "18:00", monday) == datetime(2026, 11, 6, 18, 0)
    assert next_run(1, "day", "09:00", monday) == datetime(2026, 11, 3, 9, 0)


# ── SSO ───────────────────────────────────────────────────────────────────────

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def test_sso_flow(tmp_path, monkeypatch):
    sys.path.insert(0, os.path.dirname(__file__))
    from mock_oidc import Provider
    from mcn.core_engine.mcn_server import _make_handler
    p = Provider({"lenin": {"email": "lenin@acme.in", "email_verified": True, "name": "Lenin"},
                  "priya": {"email": "priya@acme.in", "email_verified": True, "name": "Priya"},
                  "eve": {"email": "eve@evil.com", "email_verified": True}})
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCN_APP_URL", raising=False)
    monkeypatch.setenv("ISSUER", p.base)
    interp = MCNInterpreter()
    interp.execute('''
auth
    roles admin, staff
    sso
        issuer        env("ISSUER")
        client_id     "client-1"
        client_secret "s3cret"
        allow_domains "acme.in"
        default_role  staff
contract Note
    title: str
service s
    crud Note
''', quiet=True)
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(interp._evaluator))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    opener = build_opener(_NoRedirect)

    def get(url):
        try:
            r = opener.open(url)
            return r.status, r.headers, r.read()
        except HTTPError as e:
            return e.code, e.headers, e.read()

    def sso(who, return_to="http://localhost:5173/"):
        p.next_user = who
        status, _, body = get(base + "/sso_start?return_to=" + urllib.parse.quote(return_to))
        if status != 200:
            return status
        _, h, _ = get(json.loads(body)["url"])
        _, h, _ = get(h["Location"])
        return urllib.parse.unquote(h["Location"])

    assert json.loads(get(base + "/auth_status")[2])["sso"]["label"] == "SSO"
    first = sso("lenin")
    token = first.split("#mcn_token=")[1]
    me = json.loads(urlopen(Request(base + "/me", headers={"Authorization": "Bearer " + token})).read())
    assert me["user"]["role"] == "admin"                                   # first user = admin
    second = sso("priya").split("#mcn_token=")[1]
    me2 = json.loads(urlopen(Request(base + "/me", headers={"Authorization": "Bearer " + second})).read())
    assert me2["user"]["role"] == "staff"
    assert sso("eve").endswith("#mcn_error=Accounts from evil.com can't sign in to this app")
    assert sso("lenin", "https://evil.example/") == 400                    # no open redirect
    assert get(base + "/sso_callback?code=x&state=forged")[0] == 400
    httpd.shutdown()
    p.httpd.shutdown()


# ── UI output ─────────────────────────────────────────────────────────────────

def test_ui_platform_output(tmp_path, monkeypatch):
    from mcn.core_engine.ui_compiler import UICompiler
    monkeypatch.chdir(tmp_path)
    interp = MCNInterpreter()
    interp.execute(APP.split("service finance")[0] +
                   'component Expenses\n    render\n        crud_table Expense\n'
                   'app Fin\n    title "Finance"\n    layout\n        sidebar\n'
                   '            nav "Expenses" Expenses\n', quiet=True)
    UICompiler(output_dir=tmp_path / "fe").compile(interp._evaluator)
    src = tmp_path / "fe" / "src"
    models = (src / "models.ts").read_text()
    assert '"approve": "/approve_expense"' in models and '"export": "/export_expenses"' in models
    assert '"readRoles": [' in models and '"type": "file"' in models
    crud = (src / "components" / "CrudTable.tsx").read_text()
    for needle in ("function FileInput", "function ApprovalBadge", "const exportCsv",
                   "const importCsv", "const canWrite"):
        assert needle in crud
    public = tmp_path / "fe" / "public"
    manifest = json.loads((public / "manifest.webmanifest").read_text())
    assert manifest["display"] == "standalone" and manifest["name"] == "Finance"
    assert (public / "icon-192.png").read_bytes().startswith(b"\x89PNG")
    assert (public / "sw.js").exists()
    assert 'rel="manifest"' in (tmp_path / "fe" / "index.html").read_text()
    assert "serviceWorker" in (src / "main.tsx").read_text()


# ── language helpers ──────────────────────────────────────────────────────────

def test_expression_interpolation_and_dates():
    it = MCNInterpreter()
    it.execute('var v = 450000\nvar q = 3\n'
               'var a = "Total {format_currency(v)} x{q * 2} {q > 2 ? \'bulk\' : \'one\'}"\n'
               'var b = "{x: 1} {missing(1)} {nope}"\n'
               'var c = add_days("2026-11-02", 3)\n', quiet=True)
    assert it.variables["a"] == "Total ₹4,50,000 x6 bulk"
    assert it.variables["b"] == "{x: 1} {missing(1)} {nope}"
    assert it.variables["c"] == "2026-11-05"



def test_export_neutralises_formulas_and_svg_downloads(app):
    call, _ = app
    call("/create_expense", {"title": '=HYPERLINK("http://evil")', "amount": 1}, "staff")
    assert "'=HYPERLINK" in call("/export_expenses", None, "staff")[1]["content"]
    svg = base64.b64encode(b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>").decode()
    _, f = call("/upload", {"name": "x.svg", "type": "image/svg+xml", "data": svg}, "staff")
    with urlopen(call.base + f["url"]) as r:
        assert r.headers["Content-Disposition"].startswith("attachment")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
