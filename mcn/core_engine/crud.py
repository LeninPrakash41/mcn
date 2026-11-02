"""
Contract-driven CRUD for MCN.

    contract Lead
        name:  str
        email: str unique
        stage: choice("new", "won") = "new"

    service crm
        crud Lead
            search name, email

generates list_leads / get_lead / create_lead / update_lead / delete_lead,
creates the `leads` table and adds new columns when the contract grows
(columns are never dropped or altered).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


# ── Naming ────────────────────────────────────────────────────────────────────

def snake(name: str) -> str:
    """PurchaseOrder → purchase_order."""
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    s = re.sub(r"(?<=[A-Z])([A-Z][a-z])", r"_\1", s)
    return s.lower()


def plural(word: str) -> str:
    """lead → leads, category → categories, box → boxes."""
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"


def crud_names(contract_name: str) -> Dict[str, str]:
    one  = snake(contract_name)
    many = plural(one)
    return {
        "singular": one, "plural": many, "table": many,
        "list":   f"list_{many}",  "get":    f"get_{one}",
        "create": f"create_{one}", "update": f"update_{one}",
        "delete": f"delete_{one}",
    }


# ── Field specs & validation ──────────────────────────────────────────────────

FIELD_TYPES = {"str", "string", "text", "int", "float", "number", "bool",
               "date", "datetime", "choice", "any"}

SQL_TYPES = {"int": "INTEGER", "bool": "INTEGER", "float": "REAL", "number": "REAL"}

SYSTEM_FIELDS = ("id", "created_at", "updated_at")


class FieldSpec:
    def __init__(self, name: str, type_name: str, optional: bool = False,
                 default: Any = None, has_default: bool = False,
                 unique: bool = False, choices: Optional[List[str]] = None):
        self.name        = name
        self.type        = type_name
        self.optional    = optional
        self.default     = default
        self.has_default = has_default
        self.unique      = unique
        self.choices     = list(choices or [])

    @property
    def required(self) -> bool:
        return not self.optional and not self.has_default

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": self.name, "type": self.type,
                             "required": self.required}
        if self.has_default:
            d["default"] = self.default
        if self.unique:
            d["unique"] = True
        if self.choices:
            d["choices"] = self.choices
        return d


class ValidationErrors(Exception):
    def __init__(self, errors: Dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


_INT_RE   = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?(\d+\.?\d*|\.\d+)$")


def coerce(spec: FieldSpec, value: Any) -> Any:
    """Convert/validate one value; raises ValueError with a friendly message."""
    t = spec.type
    if t in ("int",):
        if isinstance(value, bool):
            raise ValueError("must be a whole number")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and _INT_RE.match(value.strip()):
            return int(value.strip())
        raise ValueError("must be a whole number")
    if t in ("float", "number"):
        if isinstance(value, bool):
            raise ValueError("must be a number")
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str) and _FLOAT_RE.match(value.strip()):
            return float(value.strip())
        raise ValueError("must be a number")
    if t == "bool":
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.lower() in ("true", "false", "1", "0", "yes", "no"):
            return value.lower() in ("true", "1", "yes")
        raise ValueError("must be true or false")
    if t == "date":
        try:
            return date.fromisoformat(str(value)[:10]).isoformat()
        except ValueError:
            raise ValueError("must be a date like 2026-01-31")
    if t == "datetime":
        try:
            return datetime.fromisoformat(str(value)).isoformat(timespec="seconds")
        except ValueError:
            raise ValueError("must be a date and time like 2026-01-31T09:30")
    if t == "choice":
        if value not in spec.choices:
            raise ValueError("must be one of " + ", ".join(spec.choices))
        return value
    if t in ("str", "string", "text"):
        if isinstance(value, (dict, list)):
            raise ValueError("must be text")
        return str(value)
    return value    # any


def check(specs: List[FieldSpec], data: Dict[str, Any],
          partial: bool = False) -> Dict[str, Any]:
    """Validate `data` against the specs.

    partial=False (create): applies defaults and requires required fields.
    partial=True  (update): only the fields present are checked.
    Returns the cleaned values; raises ValidationErrors({field: message}).
    """
    if not isinstance(data, dict):
        raise ValidationErrors({"_": "expected an object with field values"})
    clean: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    known = {s.name for s in specs}
    for key in data:
        if key not in known and key not in SYSTEM_FIELDS:
            errors[key] = "is not a field"
    for spec in specs:
        present = spec.name in data
        value   = data.get(spec.name)
        if isinstance(value, str) and value.strip() == "" and spec.type != "choice":
            value = None
        if not present or value is None or value == "":
            if partial and not present:
                continue
            if spec.has_default and not present:
                clean[spec.name] = spec.default
            elif spec.optional:
                clean[spec.name] = None
            else:
                errors[spec.name] = "is required"
            continue
        try:
            clean[spec.name] = coerce(spec, value)
        except ValueError as exc:
            errors[spec.name] = str(exc)
    if errors:
        raise ValidationErrors(errors)
    return clean


# ── HTTP-aware errors (mcn serve maps these to status codes) ──────────────────

class MCNHttpError(Exception):
    status = 500

    def __init__(self, payload: Dict[str, Any]):
        message = payload.get("error", "")
        if payload.get("errors"):
            message += ": " + "; ".join(f"{k} {v}" for k, v in payload["errors"].items())
        super().__init__(message)
        self.payload = payload


class BadRequest(MCNHttpError):
    status = 400


class NotFound(MCNHttpError):
    status = 404


# ── CRUD resource ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CrudResource:
    """Table + endpoints for one contract."""

    def __init__(self, contract, query: Callable, search: List[str] = (),
                 sort: str = "", page_size: int = 25):
        self.contract  = contract
        self.specs: List[FieldSpec] = contract.specs
        self.query     = query
        self.names     = crud_names(contract.name)
        self.table     = self.names["table"]
        self.label     = contract.name
        self.page_size = max(1, min(int(page_size or 25), 200))
        field_names    = {s.name for s in self.specs}
        for f in search:
            if f not in field_names:
                raise ValueError(f"crud {contract.name}: cannot search unknown field '{f}'")
        self.search = list(search) or [s.name for s in self.specs
                                       if s.type in ("str", "string", "text")]
        self.default_sort = self._parse_sort(sort) if sort else ("id", "DESC")

    # ── schema ────────────────────────────────────────────────────────────────

    def ensure_table(self) -> None:
        cols = ['"id" INTEGER PRIMARY KEY AUTOINCREMENT']
        for s in self.specs:
            col = f'"{s.name}" {SQL_TYPES.get(s.type, "TEXT")}'
            if s.unique:
                col += " UNIQUE"
            cols.append(col)
        cols += ['"created_at" TEXT', '"updated_at" TEXT']
        self.query(f'CREATE TABLE IF NOT EXISTS "{self.table}" ({", ".join(cols)})')
        # Add-only migration: new contract fields become new columns.
        existing = {r["name"] for r in self.query(
            f"SELECT name FROM pragma_table_info('{self.table}')")}
        for s in self.specs:
            if s.name not in existing:
                self.query(f'ALTER TABLE "{self.table}" ADD COLUMN '
                           f'"{s.name}" {SQL_TYPES.get(s.type, "TEXT")}')
        for sys_col in ("created_at", "updated_at"):
            if sys_col not in existing:
                self.query(f'ALTER TABLE "{self.table}" ADD COLUMN "{sys_col}" TEXT')

    # ── helpers ───────────────────────────────────────────────────────────────

    def _parse_sort(self, sort: str) -> Tuple[str, str]:
        parts = str(sort).strip().split()
        field = parts[0] if parts else "id"
        desc  = field.startswith("-") or (len(parts) > 1 and parts[1].lower() == "desc")
        field = field.lstrip("-")
        allowed = {s.name for s in self.specs} | set(SYSTEM_FIELDS)
        if field not in allowed:
            raise BadRequest({"error": f"Cannot sort by '{field}'"})
        return field, "DESC" if desc else "ASC"

    def _row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        for s in self.specs:
            if s.type == "bool" and row.get(s.name) is not None:
                row[s.name] = bool(row[s.name])
        return row

    def _id(self, payload: Any) -> int:
        raw = payload.get("id") if isinstance(payload, dict) else payload
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise BadRequest({"error": "A numeric 'id' is required",
                              "errors": {"id": "is required"}})

    def _fetch(self, item_id: int) -> Dict[str, Any]:
        rows = self.query(f'SELECT * FROM "{self.table}" WHERE "id" = ?', (item_id,))
        if not rows:
            raise NotFound({"error": f"{self.label} {item_id} not found"})
        return self._row(rows[0])

    def _check_unique(self, values: Dict[str, Any], exclude_id: Optional[int] = None):
        errors = {}
        for s in self.specs:
            if s.unique and values.get(s.name) not in (None, ""):
                sql = f'SELECT "id" FROM "{self.table}" WHERE "{s.name}" = ?'
                params: tuple = (values[s.name],)
                if exclude_id is not None:
                    sql += ' AND "id" != ?'
                    params += (exclude_id,)
                if self.query(sql, params):
                    errors[s.name] = "already exists"
        if errors:
            raise ValidationErrors(errors)

    def _validated(self, data: Any, partial: bool,
                   exclude_id: Optional[int] = None) -> Dict[str, Any]:
        """Field checks + uniqueness, reporting every problem at once."""
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if k not in SYSTEM_FIELDS}
        errors: Dict[str, str] = {}
        values: Dict[str, Any] = {}
        try:
            values = check(self.specs, data, partial=partial)
        except ValidationErrors as exc:
            errors.update(exc.errors)
        if isinstance(data, dict):
            candidates = {s.name: values.get(s.name, data.get(s.name))
                          for s in self.specs if s.unique and s.name not in errors}
            try:
                self._check_unique(candidates, exclude_id=exclude_id)
            except ValidationErrors as exc:
                errors.update(exc.errors)
        if errors:
            raise BadRequest({"error": "Please fix the highlighted fields",
                              "errors": errors})
        return values

    # ── endpoints ─────────────────────────────────────────────────────────────

    def list(self, payload: Any = None) -> Dict[str, Any]:
        p = payload if isinstance(payload, dict) else {}
        try:
            page      = max(1, int(p.get("page") or 1))
            page_size = max(1, min(int(p.get("page_size") or self.page_size), 200))
        except (TypeError, ValueError):
            raise BadRequest({"error": "page and page_size must be numbers"})
        field, direction = (self._parse_sort(p["sort"]) if p.get("sort")
                            else self.default_sort)
        where, params = [], []
        term = str(p.get("search") or "").strip()
        if term and self.search:
            where.append("(" + " OR ".join(f'"{f}" LIKE ?' for f in self.search) + ")")
            params += [f"%{term}%"] * len(self.search)
        for s in self.specs:                      # ?stage=won → exact filter
            if s.name in p and p[s.name] not in (None, ""):
                try:
                    value = coerce(s, p[s.name])
                except ValueError as exc:
                    raise BadRequest({"error": f"{s.name} {exc}"})
                where.append(f'"{s.name}" = ?')
                params.append(value)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self.query(f'SELECT COUNT(*) AS n FROM "{self.table}"{clause}',
                           tuple(params) or None)[0]["n"]
        rows = self.query(
            f'SELECT * FROM "{self.table}"{clause} ORDER BY "{field}" {direction}, "id" DESC '
            f"LIMIT ? OFFSET ?", tuple(params) + (page_size, (page - 1) * page_size))
        return {"items": [self._row(r) for r in rows], "total": total,
                "page": page, "page_size": page_size}

    def get(self, payload: Any = None) -> Dict[str, Any]:
        return self._fetch(self._id(payload))

    def create(self, payload: Any = None) -> Dict[str, Any]:
        values = self._validated(payload or {}, partial=False)
        now  = _now()
        cols = list(values) + ["created_at", "updated_at"]
        vals = list(values.values()) + [now, now]
        col_sql = ", ".join(f'"{c}"' for c in cols)
        from .mcn_runtime import _SQLITE_LOCK
        with _SQLITE_LOCK:      # INSERT + last_insert_rowid() must not interleave
            self.query(f'INSERT INTO "{self.table}" ({col_sql}) '
                       f'VALUES ({", ".join("?" for _ in cols)})', tuple(vals))
            new_id = self.query("SELECT last_insert_rowid() AS id")[0]["id"]
        return self._fetch(new_id)

    def update(self, payload: Any = None) -> Dict[str, Any]:
        item_id = self._id(payload)
        self._fetch(item_id)                       # 404 if missing
        values = self._validated(payload, partial=True, exclude_id=item_id)
        values["updated_at"] = _now()
        sets = ", ".join(f'"{c}" = ?' for c in values)
        self.query(f'UPDATE "{self.table}" SET {sets} WHERE "id" = ?',
                   tuple(values.values()) + (item_id,))
        return self._fetch(item_id)

    def delete(self, payload: Any = None) -> Dict[str, Any]:
        item_id = self._id(payload)
        self._fetch(item_id)
        self.query(f'DELETE FROM "{self.table}" WHERE "id" = ?', (item_id,))
        return {"deleted": True, "id": item_id}

    def endpoints(self) -> Dict[str, Callable]:
        """name → callable taking one payload dict (or an id)."""
        out = {}
        for action in ("list", "get", "create", "update", "delete"):
            fn = getattr(self, action)

            def endpoint(payload: Any = None, _fn=fn):
                return _fn(payload)

            endpoint.__name__  = self.names[action]
            endpoint._mcn_body = True          # mcn serve passes the whole body/query
            out[self.names[action]] = endpoint
        return out
