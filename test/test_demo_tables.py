#!/usr/bin/env python3
"""
The runtime must not seed demo tables (users, tasks, ai_content,
weather_logs) into user databases unless explicitly asked to.
"""

import json
import sqlite3

import pytest

from mcn.core_engine.mcn_interpreter import MCNInterpreter
from mcn.core_engine.mcn_runtime import MCNRuntime

DEMO_TABLES = {"users", "tasks", "ai_content", "weather_logs"}


@pytest.fixture
def fresh_dir(tmp_path, monkeypatch):
    """Empty working directory and HOME, with no demo-table opt-in."""
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.delenv("MCN_DEMO_TABLES", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(work)
    return work


def _tables(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {r[0] for r in rows}
    finally:
        conn.close()


def test_app_defined_tasks_table_on_fresh_database(fresh_dir):
    """An app's own `tasks` schema is used, not the demo one."""
    interp = MCNInterpreter()
    interp.execute(
        'query("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY '
        'AUTOINCREMENT, title TEXT, done INTEGER DEFAULT 0)")',
        quiet=True,
    )
    interp.execute(
        'query("INSERT INTO tasks (title, done) VALUES (?, ?)", ("Ship it", 1))',
        quiet=True,
    )
    interp.execute(
        'var rows = query("SELECT title, done FROM tasks")', quiet=True
    )
    interp.runtime.close_database()

    assert interp.variables["rows"] == [{"title": "Ship it", "done": 1}]
    db = fresh_dir / "mcn_data.db"
    assert not ((DEMO_TABLES - {"tasks"}) & _tables(db))
    conn = sqlite3.connect(db)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)")]
    finally:
        conn.close()
    assert cols == ["id", "title", "done"]


def test_demo_tables_opt_in_via_env(fresh_dir, monkeypatch):
    monkeypatch.setenv("MCN_DEMO_TABLES", "1")
    runtime = MCNRuntime()
    runtime.query("SELECT 1 AS one")
    runtime.close_database()
    assert DEMO_TABLES <= _tables(fresh_dir / "mcn_data.db")


def test_demo_tables_opt_in_via_config(fresh_dir, tmp_path):
    cfg = tmp_path / "home" / ".mcn" / "config.json"
    cfg.parent.mkdir()
    cfg.write_text(json.dumps({"demo_tables": "1"}))
    runtime = MCNRuntime()
    runtime.query("SELECT 1 AS one")
    runtime.close_database()
    assert DEMO_TABLES <= _tables(fresh_dir / "mcn_data.db")


def test_env_overrides_config(fresh_dir, tmp_path, monkeypatch):
    cfg = tmp_path / "home" / ".mcn" / "config.json"
    cfg.parent.mkdir()
    cfg.write_text(json.dumps({"demo_tables": "1"}))
    monkeypatch.setenv("MCN_DEMO_TABLES", "0")
    runtime = MCNRuntime()
    runtime.query("SELECT 1 AS one")
    runtime.close_database()
    assert not (DEMO_TABLES & _tables(fresh_dir / "mcn_data.db"))
