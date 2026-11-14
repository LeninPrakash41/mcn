"""
`mcn mcp`: the agent interface as an MCP server (JSON-RPC 2.0 over stdio).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from test_agent_interface import BACKEND, UI, VERIFIED_ORDER  # noqa: E402

from mcn.core_engine.mcp_server import MCPServer, client_config  # noqa: E402


@pytest.fixture
def app(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "ui").mkdir()
    (tmp_path / "backend" / "main.mcn").write_text(BACKEND)
    (tmp_path / "ui" / "app.mcn").write_text(UI)
    return tmp_path


def rpc(server, method, params=None, msg_id=1):
    reply = server.handle({"jsonrpc": "2.0", "id": msg_id, "method": method, **({"params": params} if params else {})})
    return reply.get("result", reply.get("error"))


def call(server, name, **args):
    return rpc(server, "tools/call", {"name": name, "arguments": args})


def test_handshake_and_tools(app):
    server = MCPServer(str(app))
    init = rpc(server, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                      "clientInfo": {"name": "t", "version": "1"}})
    assert init["protocolVersion"] == "2025-03-26" and init["capabilities"] == {"tools": {"listChanged": False}}
    assert init["serverInfo"]["name"] == "mcn" and str(app) in init["instructions"]
    assert rpc(server, "initialize", {"protocolVersion": "1999-01-01"})["protocolVersion"] == "2025-06-18"
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    tools = {t["name"]: t for t in rpc(server, "tools/list")["tools"]}
    assert set(tools) == {"inspect", "find", "explain", "create", "modify", "remove", "validate", "test", "show",
                          "patches", "language_guide"}
    assert tools["explain"]["annotations"]["readOnlyHint"] and not tools["modify"]["annotations"]["readOnlyHint"]
    assert tools["create"]["inputSchema"]["required"] == ["kind", "source"]
    assert rpc(server, "ping") == {}
    assert rpc(server, "nope/method")["code"] == -32601


def test_tool_calls(app):
    server = MCPServer(str(app))
    explained = call(server, "explain", target="create_order")
    assert not explained["isError"] and explained["structuredContent"]["writes"] == ["ai_orders"]
    assert json.loads(explained["content"][0]["text"])["id"] == "endpoint:create_order"
    missing = call(server, "explain", target="nothing_here")
    assert missing["isError"] and "Nothing called 'nothing_here'" in missing["structuredContent"]["error"]
    assert call(server, "find", query="order", kind="endpoint")["structuredContent"]["results"][0]["id"] == \
        "endpoint:create_order"
    guide = call(server, "language_guide")
    assert "endpoint" in guide["content"][0]["text"] and not guide["isError"]
    bad = call(server, "modify", target="create_order")                          # no source
    assert bad["isError"] and "source" in bad["structuredContent"]["error"]


def test_a_patch_through_mcp_is_applied_only_with_execute_allowed(app):
    server = MCPServer(str(app))
    pid = call(server, "modify", target="create_order", source=VERIFIED_ORDER)["structuredContent"]["patch"]
    assert call(server, "validate", patch=pid)["structuredContent"]["ok"]
    assert call(server, "test", patch=pid)["structuredContent"]["ok"]
    assert "+            if len(found) == 0" in call(server, "show", patch=pid)["structuredContent"]["diff"]
    refused = call(server, "execute", patch=pid)
    assert refused["isError"] and "--allow-execute" in refused["structuredContent"]["error"]
    assert "Unknown customer" not in (app / "backend" / "main.mcn").read_text()

    allowed = MCPServer(str(app), allow_execute=True)
    tool = next(t for t in rpc(allowed, "tools/list")["tools"] if t["name"] == "execute")
    assert tool["annotations"]["destructiveHint"]
    assert call(allowed, "execute", patch=pid)["structuredContent"]["status"] == "applied"
    assert "Unknown customer" in (app / "backend" / "main.mcn").read_text()
    assert call(allowed, "patches")["structuredContent"]["patches"][0]["status"] == "applied"


def test_real_stdio_session(app):
    """The server as a client starts it: only protocol messages on stdout, even while tests run."""
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "inspect", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "modify", "arguments": {"target": "create_order", "source": VERIFIED_ORDER}}},
    ]
    code = "import sys; from mcn.core_engine.mcn_cli import main; sys.argv = ['mcn', 'mcp', '--dir', sys.argv[1]]; sys.exit(main())"
    proc = subprocess.run([sys.executable, "-c", code, str(app)], cwd=ROOT, capture_output=True, text=True, timeout=60,
                          input="\n".join(json.dumps(m) for m in messages) + "\nnot json\n")
    replies = [json.loads(line) for line in proc.stdout.splitlines()]          # every line is JSON
    assert [r.get("id") for r in replies] == [1, 2, 3, None]
    assert replies[1]["result"]["structuredContent"]["summary"]["endpoints"] == 4
    pid = replies[2]["result"]["structuredContent"]["patch"]
    assert replies[3]["error"]["code"] == -32700

    test = [messages[0], {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                          "params": {"name": "test", "arguments": {"patch": pid}}}]
    proc = subprocess.run([sys.executable, "-c", code, str(app)], cwd=ROOT, capture_output=True, text=True, timeout=60,
                          input="\n".join(json.dumps(m) for m in test) + "\n")
    replies = [json.loads(line) for line in proc.stdout.splitlines()]
    assert replies[-1]["result"]["structuredContent"]["ok"] is True


def test_client_config(app, capsys, monkeypatch):
    from mcn.core_engine.mcn_cli import main
    assert client_config(str(app)) == {"mcpServers": {"mcn": {"command": "mcn", "args": ["mcp", "--dir", str(app.resolve())]}}}
    monkeypatch.setattr(sys, "argv", ["mcn", "mcp", "--dir", str(app), "--print-config", "--allow-execute"])
    assert main() == 0
    out = capsys.readouterr()
    assert json.loads(out.out)["mcpServers"]["mcn"]["args"][-1] == "--allow-execute"
    assert "claude mcp add mcn -- mcn mcp --dir" in out.err
