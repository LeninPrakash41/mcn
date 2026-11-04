"""How MCN values look as text: true, false, null, [1, "a"], {name: "Ana"}."""
from __future__ import annotations

import json
import re
from typing import Any

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def to_text(value: Any) -> str:
    """A value as log() and string joining show it. Text is shown as is."""
    if isinstance(value, str):
        return value
    return literal(value)


def literal(value: Any) -> str:
    """A value written the way MCN code writes it (text in quotes)."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(literal(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            key = k if isinstance(k, str) and _KEY.match(k) else json.dumps(str(k), ensure_ascii=False)
            parts.append(f"{key}: {literal(v)}")
        return "{" + ", ".join(parts) + "}"
    return str(value)
