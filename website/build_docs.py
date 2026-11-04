#!/usr/bin/env python3
"""
Build the docs site data: website/docs/pages/**/*.md → website/docs/pages.js.

The built-in function reference (reference/builtins.md) is generated from the
running interpreter, so its names and signatures can't drift from the code.

    python website/build_docs.py          # rebuild
    python website/build_docs.py --check  # exit 1 if pages.js is out of date (used by tests)
"""
import contextlib
import inspect
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = HERE / "docs" / "pages"
OUT = HERE / "docs" / "pages.js"
sys.path.insert(0, str(HERE.parent))

# Built-ins grouped for the reference page; anything unlisted lands in "More".
CATEGORIES = [
    ("Output and values", "log echo str int float bool type len count"),
    ("Text", "upper lower trim split join replace contains starts_with ends_with substr pad_left pad_right "
             "format_str regex_match regex_find regex_extract regex_replace"),
    ("Lists", "push pop shift unshift first last slice reverse sort unique flatten zip range "
              "map filter find reduce group_by sum avg min max array_contains"),
    ("Objects and JSON", "keys values has_key merge pick omit to_json json_str json_parse parse_json parse_csv"),
    ("Math", "abs round floor ceil sqrt pow clamp random random_int random_float"),
    ("Time", "now now_ms format_date sleep"),
    ("Database", "query connect_postgresql connect_mongodb datasource"),
    ("HTTP, files and environment", "fetch http_get http_post trigger read_file write_file append_file env env_get send_email"),
    ("AI", "ai llm agent_run classify extract embed rag checkpoint vector_upsert vector_search vector_add vector_delete vector_clear "
           "memory_store memory_add memory_get memory_search memory_all memory_clear translate"),
    ("Tasks, events and IoT", "task await on trigger_event workflow pipeline device"),
    ("Sessions, cache and queues", "session_set session_get session_delete session_all session_clear "
                                   "cache_set cache_get cache_delete cache_clear queue_push queue_pop queue_peek queue_size queue_len queue_clear"),
    ("Security", "validate escape_html sanitize_html is_email is_url password_strength rate_limit require "
                 "secure_token safe_equals mask audit_log verify_audit_log current_user auth_hash_password auth_verify_password auth_create_token auth_verify_token jwt_sign jwt_verify "
                 "sha256 md5 uuid base64_encode base64_decode hash_data"),
    ("Machine learning", "load_dataset preprocess train predict batch_predict compare_models export_model "
                         "deploy_model fine_tune get_training_status"),
    ("Packages", "use generate_postman"),
]

# One-line descriptions for built-ins whose Python docstring is missing or unclear
DESCRIPTIONS = {
    "log": "Print values with a timestamp.", "echo": "Print a value without a timestamp.",
    "str": "Convert to text.", "int": "Convert to a whole number.", "float": "Convert to a decimal number.",
    "bool": "Convert to true/false.", "type": "Declare a type hint for a variable: type(\"age\", \"number\").", "len": "Length of text, a list or an object.",
    "upper": "Text in capitals.", "lower": "Text in lower case.", "trim": "Remove surrounding spaces.",
    "split": "Split text into a list.", "join": "Join a list into text.", "replace": "Replace every occurrence.",
    "contains": "Whether text contains a substring.", "starts_with": "Whether text starts with a prefix.",
    "ends_with": "Whether text ends with a suffix.", "substr": "Part of a text by position.",
    "push": "Add to the end of a list (returns the list).", "pop": "Remove and return the last item.",
    "first": "First item.", "last": "Last item.", "slice": "Part of a list by position.",
    "reverse": "Reversed copy.", "sort": "Sorted copy; optional key name for lists of objects.",
    "unique": "Items with duplicates removed.", "range": "List of numbers: range(5), range(2, 8) or range(0, 10, 2).",
    "map": "Apply a function to every item: map(nums, x => x * 2).",
    "filter": "Items for which a function is true.", "find": "First item for which a function is true.",
    "reduce": "Combine items: reduce(nums, (a, b) => a + b, 0).", "sum": "Total of a list.",
    "avg": "Average of a list.", "min": "Smallest value.", "max": "Largest value.",
    "keys": "An object's keys.", "values": "An object's values.", "has_key": "Whether an object has a key.",
    "merge": "Combine objects (later keys win).", "to_json": "Value as JSON text.",
    "abs": "Absolute value.", "round": "Round to N decimal places.", "floor": "Round down.", "ceil": "Round up.",
    "sqrt": "Square root.", "pow": "Power.", "random": "Random number from 0 to 1, or between lo and hi.",
    "now": "Current local time as ISO text.", "now_ms": "Milliseconds since 1970, for timing.",
    "sleep": "Pause for N seconds (fractions allowed, max 60).",
    "query": "Run SQL on the built-in SQLite database. SELECT returns a list of objects; use ? placeholders.",
    "trigger": "HTTP request (default POST); returns {success, status_code, data}.",
    "read_file": "Read a text file.", "write_file": "Write a text file.", "append_file": "Append to a text file.",
    "env": "Read an environment variable (null if unset).",
    "rag": "Answer a question from documents: rag(question, docs).",
    "agent_run": "Let Claude call your functions as tools: agent_run(prompt, {tools: [\"name\"], system}). Returns {reply, tool_calls, steps}.",
    "validate": "Check input against rules: validate(data, {email: \"required|email\"}). Returns {valid, errors}.",
    "require": "Stop with a message unless a condition holds: require(user.admin, \"Admins only\").",
    "current_user": "Who called this endpoint: the JWT payload, {token: true}, or null.",
    "task": "Run a function in the background: task \"name\" function args.",
    "await": "Wait for tasks; results by name (r.name) or position (r[0]).",
    "on": "Register an event handler.", "device": "Sensors and outputs: device(\"register\" | \"read\" | \"on\" | \"off\" | \"write\" | \"watch\" | \"list\", id, ...). Simulated in Studio; real on a Raspberry Pi, Arduino or MQTT.",
    "use": "Load a package's functions: use \"stripe\".", "uuid": "Random unique id.",
    "train": "Train a model on a loaded dataset (add it with `mcn add ml`).",
    "load_dataset": "Load a CSV file as a dataset for training.",
}

ALIASES = {"abs_val", "average", "ceil_val", "floor_val", "max_val", "min_val", "round_val", "reverse_list",
           "slice_list", "sort_list", "sum_list", "str_len", "str_replace", "substring", "to_upper", "to_lower",
           "to_str", "to_int", "to_float", "to_bool", "decode_base64", "encode_base64", "flat", "hash_md5",
           "hash_sha256", "auth_hash", "auth_verify_hash", "zip_lists", "queue_len"}


def _signature(fn) -> str:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return "(…)"
    parts = []
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.kind == p.VAR_POSITIONAL:
            parts.append(f"...{p.name}")
        elif p.kind == p.VAR_KEYWORD:
            continue
        elif p.default is not p.empty:
            parts.append(f"{p.name}?")
        else:
            parts.append(p.name)
    return "(" + ", ".join(parts) + ")"


def builtins_page() -> str:
    from mcn.core_engine.mcn_interpreter import MCNInterpreter
    with contextlib.redirect_stdout(io.StringIO()):
        fns = MCNInterpreter()._evaluator.functions
    public = {n: f for n, f in fns.items() if not n.startswith("_") and callable(f)}
    placed, sections = set(), []
    for title, names in CATEGORIES:
        rows = []
        for name in names.split():
            if name in public and name not in placed:
                placed.add(name)
                doc = DESCRIPTIONS.get(name) or (inspect.getdoc(public[name]) or "").split("\n")[0]
                doc = doc.replace("|", "\\|")      # outside the f-string: Python < 3.12
                rows.append(f"| `{name}{_signature(public[name])}` | {doc} |")
        if rows:
            sections.append(f"## {title}\n\n| Function | Description |\n|---|---|\n" + "\n".join(rows))
    rest = sorted(n for n in public if n not in placed and n not in ALIASES)
    if rest:
        sections.append("## More\n\n" + ", ".join(f"`{n}`" for n in rest))
    aliases = sorted(n for n in ALIASES if n in public)
    return (
        "# Built-in functions\n\n"
        f"Every function available without `use`: {len(public)} in total, generated from the interpreter. "
        "Parameters marked `?` are optional.\n\n"
        "> **Tip** Built-ins also work as methods on their first argument: `text.contains(\"a\")` is "
        "`contains(text, \"a\")`, and `items.sum()` is `sum(items)`.\n\n"
        + "\n\n".join(sections)
        + "\n\n## Aliases\n\nThese names work too, for people coming from other languages: "
        + ", ".join(f"`{n}`" for n in aliases) + ".\n"
    )


def build() -> str:
    nav = json.loads((PAGES / "_nav.json").read_text(encoding="utf-8"))
    pages = {}
    for group in nav:
        for slug in group["pages"]:
            if slug == "reference/builtins":
                md, file = builtins_page(), "../../build_docs.py"
            else:
                path = PAGES / f"{slug}.md"
                md, file = path.read_text(encoding="utf-8"), f"{slug}.md"
            title = re.search(r"^# (.+)$", md, re.M).group(1).strip()
            pages[slug] = {"title": title, "file": file, "md": md}
    data = json.dumps({"nav": nav, "pages": pages}, ensure_ascii=False, indent=1)
    return "/* Generated by website/build_docs.py from docs/pages/*.md — do not edit. */\nwindow.MCN_DOCS = " + data + ";\n"


INDEX = HERE / "docs" / "index.html"


def stamp_index(pages_js: str) -> str:
    """index.html with ?v=<content hash> on the docs' own files, so browsers
    fetch new pages after a rebuild instead of a cached copy."""
    import hashlib
    html = INDEX.read_text(encoding="utf-8")
    for name in ("pages.js", "docs.js", "docs.css"):
        body = pages_js if name == "pages.js" else (HERE / "docs" / name).read_text(encoding="utf-8")
        digest = hashlib.sha256(body.encode()).hexdigest()[:10]
        html = re.sub(rf'(["\']){re.escape(name)}(\?v=[0-9a-f]+)?\1', rf"\g<1>{name}?v={digest}\g<1>", html)
    return html


if __name__ == "__main__":
    output = build()
    index = stamp_index(output)
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != output or INDEX.read_text(encoding="utf-8") != index:
            print("website/docs/pages.js is out of date: run python website/build_docs.py")
            sys.exit(1)
        print("pages.js is up to date")
    else:
        OUT.write_text(output, encoding="utf-8")
        INDEX.write_text(index, encoding="utf-8")
        print(f"wrote {OUT.relative_to(HERE.parent)} ({len(output) // 1024} KB) and stamped index.html")
