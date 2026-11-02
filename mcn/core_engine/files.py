"""
Files, PDFs and email for MCN apps.

    receipt: file?                                   # contract field (upload in forms)
    var pdf = make_pdf("Invoice #42", ["Line one", [["Item", "Qty"], ["Pen", 2]]])
    send_email("a@x.in", "Your invoice", "Attached.", [pdf])

Files live in $MCN_UPLOAD_DIR (default ./uploads) with metadata in the
`mcn_files` table; download links are signed so <a href> works without a
bearer token.  Email goes through SMTP when $MCN_SMTP_HOST is set, otherwise
into the `mcn_outbox` table (development mode) — every message is recorded
there with its status either way.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

MAX_UPLOAD_MB = float(os.environ.get("MCN_MAX_UPLOAD_MB", "10"))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_name(name: str) -> str:
    name = os.path.basename(str(name or "file")).strip() or "file"
    return re.sub(r"[^\w.\- ()]+", "_", name)[:120]


class FileStore:
    TABLE = "mcn_files"

    def __init__(self, query: Callable, secret: str, base_url: Callable[[], str] = lambda: ""):
        self.query = query
        self.secret = secret.encode()
        self.base_url = base_url
        self.dir = Path(os.environ.get("MCN_UPLOAD_DIR") or "uploads")
        self.query(f'CREATE TABLE IF NOT EXISTS "{self.TABLE}" ("id" INTEGER PRIMARY KEY '
                   'AUTOINCREMENT, "name" TEXT, "type" TEXT, "size" INTEGER, "path" TEXT, '
                   '"created_at" TEXT, "created_by" TEXT)')

    # ── signed links ──────────────────────────────────────────────────────────

    def _sig(self, file_id: int, exp: int) -> str:
        return hmac.new(self.secret, f"{file_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]

    def url(self, file_id: int, hours: int = 24) -> str:
        exp = int(time.time()) + hours * 3600
        return f"{self.base_url()}/files/{file_id}?exp={exp}&sig={self._sig(file_id, exp)}"

    def check_signature(self, file_id: int, exp: str, sig: str) -> bool:
        try:
            exp_i = int(exp)
        except (TypeError, ValueError):
            return False
        return exp_i >= time.time() and hmac.compare_digest(self._sig(file_id, exp_i), str(sig))

    # ── storage ───────────────────────────────────────────────────────────────

    def save(self, data: bytes, name: str, mime: Optional[str] = None,
             user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            raise ValueError(f"File is larger than {MAX_UPLOAD_MB:g} MB")
        name = _safe_name(name)
        mime = mime or mimetypes.guess_type(name)[0] or "application/octet-stream"
        self.dir.mkdir(parents=True, exist_ok=True)
        stored = self.dir / f"{secrets.token_hex(8)}_{name}"
        stored.write_bytes(data)
        from .mcn_runtime import _SQLITE_LOCK
        with _SQLITE_LOCK:
            self.query(f'INSERT INTO "{self.TABLE}" ("name", "type", "size", "path", '
                       '"created_at", "created_by") VALUES (?, ?, ?, ?, ?, ?)',
                       (name, mime, len(data), str(stored), _now(), (user or {}).get("email")))
            file_id = self.query("SELECT last_insert_rowid() AS id")[0]["id"]
        return self.info(file_id)

    def record(self, file_id: Any) -> Optional[Dict[str, Any]]:
        try:
            rows = self.query(f'SELECT * FROM "{self.TABLE}" WHERE "id" = ?', (int(file_id),))
        except (TypeError, ValueError):
            return None
        return rows[0] if rows else None

    def info(self, file_id: Any) -> Optional[Dict[str, Any]]:
        r = self.record(file_id)
        if r is None:
            return None
        return {"id": r["id"], "name": r["name"], "type": r["type"], "size": r["size"],
                "url": self.url(r["id"])}

    def read(self, file_id: Any) -> Tuple[Dict[str, Any], bytes]:
        r = self.record(file_id)
        if r is None or not Path(r["path"]).exists():
            raise FileNotFoundError(f"File {file_id} not found")
        return r, Path(r["path"]).read_bytes()

    def upload(self, payload: Any = None, user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST /upload {name, type?, data: base64}"""
        from .crud import BadRequest
        p = payload if isinstance(payload, dict) else {}
        raw = str(p.get("data") or "")
        if "," in raw[:100] and raw.startswith("data:"):
            raw = raw.split(",", 1)[1]            # data:<mime>;base64,<...>
        try:
            data = base64.b64decode(raw, validate=True)
        except (ValueError, TypeError):
            raise BadRequest({"error": "data must be base64-encoded file contents"})
        if not data:
            raise BadRequest({"error": "The file is empty"})
        try:
            return self.save(data, p.get("name") or "file", p.get("type"), user)
        except ValueError as exc:
            raise BadRequest({"error": str(exc)})


# ── PDF ───────────────────────────────────────────────────────────────────────

_PAGE_W, _PAGE_H, _MARGIN = 595.28, 841.89, 50      # A4 portrait, points


def _pdf_text(s: Any) -> str:
    text = str(s).replace("₹", "Rs ").replace("—", "-").replace("–", "-")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _width(s: str, size: float) -> float:
    return len(str(s)) * size * 0.5                  # Helvetica average glyph width


def _wrap(text: str, size: float, max_w: float) -> List[str]:
    lines: List[str] = []
    for para in str(text).split("\n"):
        words, cur = para.split(" "), ""
        for w in words:
            trial = (cur + " " + w).strip()
            if _width(trial, size) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def build_pdf(title: str, content: Any) -> bytes:
    """A simple, dependency-free PDF: a title, paragraphs and tables.

    content: a string (paragraphs separated by newlines) or a list whose items
    are strings (paragraphs), lists of rows (tables — first row is the
    header), lists of dicts (tables, keys as header) or {"heading": "…"}.
    """
    items = content if isinstance(content, list) and not _is_rows(content) else [content]
    pages: List[List[str]] = [[]]
    y = _PAGE_H - _MARGIN

    def emit(op: str):
        pages[-1].append(op)

    def need(h: float):
        nonlocal y
        if y - h < _MARGIN:
            pages.append([])
            y = _PAGE_H - _MARGIN

    def text_line(s: str, size: float, bold: bool = False, x: float = _MARGIN):
        nonlocal y
        need(size * 1.5)
        y -= size * 1.4
        emit(f"BT /F{2 if bold else 1} {size} Tf {x:.1f} {y:.1f} Td ({_pdf_text(s)}) Tj ET")

    usable = _PAGE_W - 2 * _MARGIN
    for line in _wrap(title, 20, usable):
        text_line(line, 20, bold=True)
    text_line(datetime.now().strftime("%d %b %Y, %H:%M"), 9)
    y -= 10

    for item in items:
        if item is None:
            continue
        if isinstance(item, dict) and "heading" in item:
            y -= 6
            for line in _wrap(item["heading"], 14, usable):
                text_line(line, 14, bold=True)
        elif _is_rows(item):
            rows = _rows(item)
            cols = max(len(r) for r in rows)
            col_w = usable / cols
            for i, row in enumerate(rows):
                need(18)
                y -= 16
                if i == 0:
                    emit(f"0.93 g {_MARGIN:.1f} {y - 4:.1f} {usable:.1f} 18 re f 0 g")
                for c in range(cols):
                    cell = str(row[c]) if c < len(row) and row[c] is not None else ""
                    max_chars = max(1, int(col_w / (10 * 0.5)) - 1)
                    if len(cell) > max_chars:
                        cell = cell[:max(1, max_chars - 3)] + "..."
                    emit(f"BT /F{2 if i == 0 else 1} 10 Tf {_MARGIN + c * col_w + 4:.1f} "
                         f"{y:.1f} Td ({_pdf_text(cell)}) Tj ET")
                emit(f"0.85 G {_MARGIN:.1f} {y - 5:.1f} m {_MARGIN + usable:.1f} {y - 5:.1f} l S 0 G")
            y -= 10
        else:
            for line in _wrap(str(item), 11, usable):
                text_line(line, 11)
            y -= 6

    objects: List[bytes] = []
    def obj(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font1 = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font2 = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    pages_id = len(objects) + 1 + 2 * len(pages)
    page_ids = []
    for i, ops in enumerate(pages):
        footer = f"BT /F1 8 Tf {_PAGE_W - _MARGIN - 40:.1f} 25 Td (Page {i + 1} of {len(pages)}) Tj ET"
        stream = "\n".join(ops + [footer]).encode("latin-1", "replace")
        content_id = obj(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(obj(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {_PAGE_W} {_PAGE_H}] "
            f"/Resources << /Font << /F1 {font1} 0 R /F2 {font2} 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode()))
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    assert obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()) == pages_id
    catalog = obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
    info = obj(f"<< /Title ({_pdf_text(title)}) /Producer (MCN) >>".encode())

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def _is_rows(x: Any) -> bool:
    return isinstance(x, list) and len(x) > 0 and all(isinstance(r, (list, tuple, dict)) for r in x) \
        and not (len(x) == 1 and isinstance(x[0], dict) and "heading" in x[0])


def _rows(x: List[Any]) -> List[List[Any]]:
    if all(isinstance(r, dict) for r in x):
        keys = list(dict.fromkeys(k for r in x for k in r))
        return [[k.replace("_", " ").capitalize() for k in keys]] + [[r.get(k) for k in keys] for r in x]
    return [list(r) for r in x]


# ── Email ─────────────────────────────────────────────────────────────────────

class Mailer:
    TABLE = "mcn_outbox"

    def __init__(self, query: Callable, files: Optional[FileStore] = None):
        self.query = query
        self.files = files
        self.query(f'CREATE TABLE IF NOT EXISTS "{self.TABLE}" ("id" INTEGER PRIMARY KEY '
                   'AUTOINCREMENT, "at" TEXT, "to_addr" TEXT, "subject" TEXT, "body" TEXT, '
                   '"attachments" TEXT, "status" TEXT, "error" TEXT)')

    @staticmethod
    def configured() -> bool:
        return bool(os.environ.get("MCN_SMTP_HOST"))

    def send(self, to: Any, subject: str, body: str = "", attachments: Any = None) -> Dict[str, Any]:
        recipients = [t.strip() for t in (to if isinstance(to, list) else str(to).split(","))
                      if str(t).strip()]
        if not recipients:
            raise ValueError("send_email needs at least one recipient")
        for r in recipients:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", r):
                raise ValueError(f"'{r}' is not an email address")
        files = []
        for a in (attachments or []):
            fid = a.get("id") if isinstance(a, dict) else a
            if self.files is None:
                raise ValueError("Attachments need a service (file storage)")
            files.append(self.files.read(fid))
        status, error = "outbox", None
        if self.configured():
            try:
                self._smtp(recipients, subject, body, files)
                status = "sent"
            except Exception as exc:          # recorded, then reported to the caller
                status, error = "failed", str(exc)
        self.query(f'INSERT INTO "{self.TABLE}" ("at", "to_addr", "subject", "body", '
                   '"attachments", "status", "error") VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (_now(), ", ".join(recipients), subject, body,
                    json.dumps([r["name"] for r, _ in files]), status, error))
        if status == "outbox":
            print(f"[mcn] email (not sent — set MCN_SMTP_HOST): to {', '.join(recipients)} | {subject}")
        if status == "failed":
            raise RuntimeError(f"Email to {', '.join(recipients)} failed: {error}")
        return {"status": status, "to": recipients}

    @staticmethod
    def _smtp(recipients: List[str], subject: str, body: str, files) -> None:
        msg = EmailMessage()
        sender = os.environ.get("MCN_SMTP_FROM") or os.environ.get("MCN_SMTP_USER") or "mcn@localhost"
        msg["From"], msg["To"], msg["Subject"] = sender, ", ".join(recipients), subject
        if body.lstrip().startswith("<"):
            msg.set_content(re.sub(r"<[^>]+>", "", body))
            msg.add_alternative(body, subtype="html")
        else:
            msg.set_content(body)
        for rec, data in files:
            main, _, sub = (rec["type"] or "application/octet-stream").partition("/")
            msg.add_attachment(data, maintype=main, subtype=sub or "octet-stream", filename=rec["name"])
        host = os.environ["MCN_SMTP_HOST"]
        port = int(os.environ.get("MCN_SMTP_PORT", "587"))
        use_ssl = port == 465
        with (smtplib.SMTP_SSL(host, port, timeout=20) if use_ssl
              else smtplib.SMTP(host, port, timeout=20)) as smtp:
            if not use_ssl and os.environ.get("MCN_SMTP_TLS", "true").lower() != "false":
                smtp.starttls()
            if os.environ.get("MCN_SMTP_USER"):
                smtp.login(os.environ["MCN_SMTP_USER"], os.environ.get("MCN_SMTP_PASSWORD", ""))
            smtp.send_message(msg)

    def list(self, payload: Any = None) -> Dict[str, Any]:
        p = payload if isinstance(payload, dict) else {}
        page = max(1, int(p.get("page") or 1))
        rows = self.query(f'SELECT * FROM "{self.TABLE}" ORDER BY "id" DESC LIMIT 50 OFFSET ?',
                          ((page - 1) * 50,))
        total = self.query(f'SELECT COUNT(*) AS n FROM "{self.TABLE}"')[0]["n"]
        return {"items": rows, "total": total, "page": page, "page_size": 50}
