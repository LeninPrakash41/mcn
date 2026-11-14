"""
Typed endpoint parameters, checked when the endpoint is called.

    endpoint add_invoice(customer: str, amount: float, due: Invoice)

Requests send JSON or form text, so values that clearly mean the declared type
are accepted ("42" for an int, "true" for a bool). Anything else is refused
before the endpoint runs, and the HTTP server answers 400 with the message.
Parameters without a type are passed through unchanged.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

BASE_TYPES = {
    "any", "int", "integer", "float", "number", "num", "str", "string", "text",
    "bool", "boolean", "list", "array", "dict", "map", "object",
}

_INT = re.compile(r"[+-]?\d+")
_NUMBER = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")


class InvalidInput(ValueError):
    """A request value that doesn't match the endpoint's declared type."""

    def __init__(self, endpoint: str, param: str, message: str):
        super().__init__(message)
        self.endpoint = endpoint
        self.param = param


def is_known_type(name: str, contracts: Optional[set] = None) -> bool:
    return name.lower() in BASE_TYPES or name in (contracts or set())


def _convert(value: Any, type_name: str, contract: Any) -> Any:
    """The value as the declared type, or raise ValueError."""
    t = type_name.lower()
    if t == "any":
        return value
    if t in ("int", "integer"):
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and _INT.fullmatch(value.strip()):
            return int(value.strip())
        raise ValueError
    if t in ("float", "number", "num"):
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, (int, float)):
            return float(value) if t == "float" else value
        if isinstance(value, str) and _NUMBER.fullmatch(value.strip()):
            number = float(value.strip())
            return int(number) if t != "float" and number.is_integer() and "." not in value else number
        raise ValueError
    if t in ("str", "string", "text"):
        if isinstance(value, str):
            return value
        raise ValueError
    if t in ("bool", "boolean"):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower() == "true"
        raise ValueError
    if t in ("list", "array"):
        if isinstance(value, (list, tuple)):
            return list(value)
        raise ValueError
    if t in ("dict", "map", "object"):
        if isinstance(value, dict):
            return value
        raise ValueError
    if contract is not None:
        if not isinstance(value, dict):
            raise ValueError
        result = contract.validate(value)
        if not result["valid"]:
            raise ValueError("; ".join(result["errors"]))
        missing = [w for w in result.get("warnings", []) if w.startswith("Missing field")]
        if missing:
            raise ValueError("; ".join(missing))
        return value
    raise ValueError(f"unknown type '{type_name}'")


def _describe(value: Any) -> str:
    if value is None:
        return "nothing"
    if isinstance(value, str):
        return f'"{value}"' if len(value) <= 40 else "text"
    return {bool: "a true/false value", int: "a number", float: "a number", list: "a list",
            dict: "an object"}.get(type(value), type(value).__name__)


def check_args(endpoint: str, params: List[str], types: Dict[str, str], required: set,
               args: List[Any], find_contract: Callable[[str], Any]) -> List[Any]:
    """Arguments converted to their declared types. Raises InvalidInput.

    `required` holds the parameters without a default value.
    """
    out = list(args)
    for i, param in enumerate(params):
        type_name = types.get(param)
        if not type_name:
            continue
        given = i < len(out) and out[i] is not None
        if not given:
            if param in required:
                raise InvalidInput(endpoint, param, f"'{param}' is required ({type_name})")
            continue
        contract = None if type_name.lower() in BASE_TYPES else find_contract(type_name)
        try:
            out[i] = _convert(out[i], type_name, contract)
        except ValueError as exc:
            detail = f": {exc}" if str(exc) else ""
            raise InvalidInput(endpoint, param,
                               f"'{param}' must be {type_name}, got {_describe(out[i])}{detail}") from None
    return out
