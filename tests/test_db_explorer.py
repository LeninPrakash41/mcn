"""
Studio's Database page: the table tree (columns, row counts, which tables the app
creates) and the SQL console.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playground_app import load  # noqa: E402


def test_schema_and_queries():
    module, client = load()
    ws = Path(module.app.config["WORKSPACE"])
    saved = {p: p.read_bytes() for p in ws.rglob("*") if p.is_file()} if ws.exists() else {}
    shutil.rmtree(ws, ignore_errors=True)
    (ws / "backend").mkdir(parents=True)
    (ws / "backend" / "main.mcn").write_text('query("CREATE TABLE IF NOT EXISTS dbx_orders (id INTEGER PRIMARY KEY, total REAL NOT NULL, note TEXT DEFAULT \'none\')")\n')
    conn = sqlite3.connect(ws / "mcn_data.db")
    conn.execute("CREATE TABLE dbx_orders (id INTEGER PRIMARY KEY, total REAL NOT NULL, note TEXT DEFAULT 'none')")
    conn.execute("CREATE TABLE \"left over\" (x TEXT)")
    conn.executemany("INSERT INTO dbx_orders (total) VALUES (?)", [(5,), (7,)])
    conn.commit()
    conn.close()
    try:
        schema = {t["table"]: t for t in client.get("/api/db/schema").get_json()["schema"]}
        orders = schema["dbx_orders"]
        assert orders["rows"] == 2 and orders["in_app"] is True
        assert orders["columns"][0] == {"name": "id", "type": "INTEGER", "notnull": False, "default": None, "pk": True}
        assert orders["columns"][1]["notnull"] is True and orders["columns"][2]["default"] == "'none'"
        assert schema["left over"]["in_app"] is False and schema["left over"]["rows"] == 0

        res = client.post("/api/db/query", json={"sql": "SELECT id, total FROM dbx_orders ORDER BY id"}).get_json()
        assert res["success"] and res["result"]["columns"] == ["id", "total"] and res["result"]["rows"] == [[1, 5.0], [2, 7.0]]
        empty = client.post("/api/db/query", json={"sql": "SELECT * FROM dbx_orders WHERE id = 99"}).get_json()["result"]
        assert empty["columns"] == ["id", "total", "note"] and empty["rows"] == []      # headers even with no rows
        changed = client.post("/api/db/query", json={"sql": "UPDATE dbx_orders SET note = 'x'"}).get_json()["result"]
        assert changed["affected"] == 2 and changed["columns"] == []
        assert client.post("/api/db/query", json={"sql": "PRAGMA table_info(dbx_orders)"}).get_json()["result"]["rows"]
        bad = client.post("/api/db/query", json={"sql": "SELECT * FROM nope"}).get_json()
        assert bad["success"] is False and "no such table" in bad["error"]
        assert client.post("/api/db/query", json={"sql": " "}).get_json()["error"] == "Write a SQL query first"
    finally:
        shutil.rmtree(ws, ignore_errors=True)
        for path, data in saved.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
