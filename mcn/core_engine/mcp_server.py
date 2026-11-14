"""
The MCN agent interface as an MCP server, so any MCP client (Claude Code, Claude
Desktop, Cursor, VS Code, your own agents) can inspect and change an MCN app
through checked patches.

    mcn mcp --dir ./my-app                  # speaks MCP over stdin/stdout
    mcn mcp --dir ./my-app --print-config   # the JSON to paste into a client's settings

Tools: inspect, find, explain, create, modify, remove, validate, test, show, patches
and language_guide (MCN's syntax, for agents that haven't seen MCN). `execute`, which
writes a patch to the files, is only offered with --allow-execute; otherwise the
person applies a reviewed patch with `mcn op execute <id> --yes`.

The protocol is JSON-RPC 2.0, one message per line (MCP's stdio transport). Nothing
but protocol messages is written to stdout; anything the engine prints goes to stderr.
"""
from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

from .agent_interface import AGENT_TOOLS, InterfaceError, Workspace, call_tool

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = """This server changes an MCN app through checked patches instead of rewriting files.
Call language_guide once if you don't know MCN's syntax. Then: inspect the app, find and explain what the
request touches, make the change as one patch with create/modify/remove (pass the patch id to later calls),
add a test, validate and test the patch until both pass, and show the diff to the user.
Applying the patch is the user's decision."""

_READ_ONLY = {"inspect", "find", "explain", "validate", "test", "show", "patches", "language_guide"}

_EXTRA_TOOLS: List[Dict[str, Any]] = [
    {"name": "show", "description": "A patch's diff, operations, validation and test results.",
     "input_schema": {"type": "object", "properties": {"patch": {"type": "string"}}, "required": ["patch"]}},
    {"name": "patches", "description": "Every patch made for this app, with its status (proposed, validated, "
     "invalid, applied).", "input_schema": {"type": "object", "properties": {}}},
    {"name": "language_guide", "description": "MCN's syntax and building blocks (services, endpoints, typed "
     "parameters, modules, components, tests). Read it before writing MCN code.",
     "input_schema": {"type": "object", "properties": {}}},
]

_EXECUTE = {"name": "execute", "description": "Write a patch to the app's files. Only after the user has seen "
            "the diff and the validation and test results, and said to apply it. Refused unless the patch passed "
            "validate and test, or if the files changed since it was made.",
            "input_schema": {"type": "object", "properties": {"patch": {"type": "string"}}, "required": ["patch"]}}


def _language_guide() -> str:
    from mcn.ai.mcn_spec import MCN_SYSTEM_PROMPT
    return MCN_SYSTEM_PROMPT


class MCPServer:
    def __init__(self, app_dir: str = ".", allow_execute: bool = False):
        self.workspace = Workspace(app_dir)
        self.allow_execute = allow_execute
        from mcn import __version__
        self.version = __version__

    # ── Tools ─────────────────────────────────────────────────────────────────

    def tools(self) -> List[Dict[str, Any]]:
        defs = AGENT_TOOLS + _EXTRA_TOOLS + ([_EXECUTE] if self.allow_execute else [])
        out = []
        for d in defs:
            read_only = d["name"] in _READ_ONLY
            out.append({"name": d["name"], "description": d["description"], "inputSchema": d["input_schema"],
                        "annotations": {"readOnlyHint": read_only, "destructiveHint": d["name"] == "execute",
                                        "idempotentHint": read_only, "openWorldHint": False}})
        return out

    def call(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """An MCP tools/call result. Operation errors come back as isError so the agent can correct itself."""
        names = {t["name"] for t in self.tools()}
        if name not in names:
            hint = " (start the server with --allow-execute to offer it)" if name == "execute" else ""
            return self._result({"error": f"Unknown tool '{name}'{hint}"}, error=True)
        try:
            if name == "language_guide":
                return {"content": [{"type": "text", "text": _language_guide()}], "isError": False}
            if name == "show":
                result: Any = self.workspace.show(args["patch"])
            elif name == "patches":
                result = {"patches": self.workspace.patches()}
            elif name == "execute":
                result = self.workspace.execute(args["patch"], approved=True)
            else:
                result = call_tool(self.workspace, name, args)
        except (InterfaceError, KeyError) as exc:
            result = {"error": str(exc).strip("'\"")}
        if isinstance(result, list):
            result = {"results": result}
        return self._result(result, error=isinstance(result, dict) and "error" in result)

    @staticmethod
    def _result(data: Dict[str, Any], error: bool = False) -> Dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps(data, indent=1, default=str)}],
                "structuredContent": data, "isError": error}

    # ── JSON-RPC ──────────────────────────────────────────────────────────────

    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The reply to one message, or None for a notification."""
        method, msg_id = message.get("method"), message.get("id")
        if msg_id is None:                      # notifications (initialized, cancelled) need no reply
            return None
        params = message.get("params") or {}
        try:
            if method == "initialize":
                asked = params.get("protocolVersion")
                return self._ok(msg_id, {
                    "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "mcn", "title": "MCN agent interface", "version": self.version},
                    "instructions": INSTRUCTIONS + f"\nThe app: {self.workspace.base}",
                })
            if method == "ping":
                return self._ok(msg_id, {})
            if method == "tools/list":
                return self._ok(msg_id, {"tools": self.tools()})
            if method == "tools/call":
                if not isinstance(params.get("name"), str):
                    return self._error(msg_id, -32602, "tools/call needs a tool name")
                return self._ok(msg_id, self.call(params["name"], params.get("arguments") or {}))
            if method in ("resources/list", "prompts/list"):
                return self._ok(msg_id, {method.split("/")[0]: []})
            return self._error(msg_id, -32601, f"Method not found: {method}")
        except Exception as exc:                # a bug in an operation shouldn't kill the session
            return self._error(msg_id, -32603, f"Internal error: {exc}")

    @staticmethod
    def _ok(msg_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    def serve(self, stdin: TextIO, stdout: TextIO) -> None:
        """Read messages until stdin closes. The engine's own prints are sent to stderr."""
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                reply: Any = self._error(None, -32700, "Parse error")
            else:
                with contextlib.redirect_stdout(sys.stderr):
                    if isinstance(message, list):              # a batch (older protocol versions)
                        reply = [r for r in (self.handle(m) for m in message if isinstance(m, dict)) if r] or None
                    elif isinstance(message, dict):
                        reply = self.handle(message)
                    else:
                        reply = self._error(None, -32600, "Invalid request")
            if reply is not None:
                stdout.write(json.dumps(reply, default=str) + "\n")
                stdout.flush()


def client_config(app_dir: str, allow_execute: bool = False) -> Dict[str, Any]:
    args = ["mcp", "--dir", str(Path(app_dir).resolve())] + (["--allow-execute"] if allow_execute else [])
    return {"mcpServers": {"mcn": {"command": "mcn", "args": args}}}


def run(app_dir: str = ".", allow_execute: bool = False) -> int:
    try:
        server = MCPServer(app_dir, allow_execute=allow_execute)
    except InterfaceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    stdout = sys.stdout
    sys.stdout = sys.stderr                    # stray prints never corrupt the protocol stream
    try:
        server.serve(sys.stdin, stdout)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout = stdout
    return 0
