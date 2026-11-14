"""
The MCN Semantic Graph (MSG): versioned JSON with the semantic graph plus every file's
complete syntax tree and source. Checked on every template: it matches its JSON
Schema, the trees rebuild exactly what the parser produces, and the sources come back
byte for byte.
"""
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcn.core_engine.lexer import Lexer  # noqa: E402
from mcn.core_engine.msg import (MSG_VERSION, ast_types, build_msg, from_msg, resolve_ref, schema,  # noqa: E402
                                 source_files)
from mcn.core_engine.parser import Parser  # noqa: E402

TEMPLATES = ROOT / "mcn" / "web-playground" / "playground_server" / "templates"
APPS = sorted(p for p in TEMPLATES.iterdir() if (p / "backend").is_dir() or (p / "ui").is_dir())
KIND_TO_AST = {"endpoint": "EndpointDecl", "function": "FunctionDecl", "service": "ServiceDecl",
               "contract": "ContractDecl", "test": "TestDecl", "workflow": "WorkflowDecl", "schedule": "ScheduleDecl",
               "component": "ComponentDecl", "app": "AppDecl", "module": "ModuleDecl"}


@pytest.mark.parametrize("app", APPS, ids=[p.name for p in APPS])
def test_every_template_round_trips(app):
    msg = build_msg(app)
    jsonschema.validate(msg, schema())
    assert msg["msg_version"] == MSG_VERSION and msg["errors"] == []
    trees, sources = from_msg(msg), source_files(msg)
    for rel, text in sources.items():
        assert text == (app / rel).read_text(encoding="utf-8")                     # byte for byte
        assert trees[rel] == Parser(Lexer(text).tokenize()).parse()                # the same AST the parser builds
    for node in msg["nodes"]:
        if node["kind"] in KIND_TO_AST:
            assert resolve_ref(msg, node["ast_ref"])["$type"] == KIND_TO_AST[node["kind"]], node["id"]
    json.dumps(msg)                                                                 # plain JSON throughout


def test_the_graph_layer_alone_is_small_and_typed():
    msg = build_msg(TEMPLATES / "voice_agent_builder", include_ast=False)
    jsonschema.validate(msg, schema())
    assert all("ast" not in f and "source" not in f for f in msg["files"].values())
    turn = next(n for n in msg["nodes"] if n["id"] == "endpoint:voice_turn")
    assert turn["signature"] == {"params": [{"name": "CallSid", "type": "str"}, {"name": "SpeechResult", "type": "str"}]}
    assert turn["ast_ref"].startswith("backend/main.mcn#/body/") and "/endpoints/" in turn["ast_ref"]
    assert {"from": "endpoint:create_agent", "to": "table:voice_agents", "kind": "writes"} in msg["edges"]


def test_schema_lists_every_ast_node_type():
    assert schema()["$defs"]["ast_node"]["properties"]["$type"]["enum"] == ast_types()


def test_other_major_versions_are_refused():
    msg = build_msg(TEMPLATES / "crm", include_ast=False)
    msg["msg_version"] = "2.0"
    with pytest.raises(ValueError, match="MSG version 2.0"):
        from_msg(msg)


def test_cli_and_agent_tool(capsys, monkeypatch):
    from mcn.core_engine.agent_interface import Workspace, call_tool
    from mcn.core_engine.mcn_cli import main
    monkeypatch.setattr(sys, "argv", ["mcn", "describe", str(TEMPLATES / "crm"), "--msg"])
    assert main() == 0
    msg = json.loads(capsys.readouterr().out)
    assert msg["files"]["backend/main.mcn"]["ast"]["$type"] == "Program"
    monkeypatch.setattr(sys, "argv", ["mcn", "describe", "--msg-schema"])
    assert main() == 0 and json.loads(capsys.readouterr().out)["title"] == "MCN Semantic Graph (MSG)"
    graph = call_tool(Workspace(TEMPLATES / "crm"), "semantic_graph", {})
    assert graph["msg_version"] == MSG_VERSION and "ast" not in graph["files"]["backend/main.mcn"]
