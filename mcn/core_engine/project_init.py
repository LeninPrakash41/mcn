"""
`mcn init` and `mcn validate`.

A new project is a working full-stack app from the first command: a backend
service with tests, a UI, and a README listing the commands that run it.
"""
import json
from pathlib import Path

_BACKEND = '''// {title} — backend
// Run:   mcn serve --file backend/main.mcn
// Test:  mcn test backend/main.mcn

query("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, done INTEGER DEFAULT 0)")

service tasks_api
    port 8080

    endpoint add_task(title)
        if not title
            return {{success: false, error: "Title is required"}}
        query("INSERT INTO tasks (title) VALUES (?)", (title,))
        return {{success: true}}

    endpoint list_tasks()
        return {{success: true, data: query("SELECT * FROM tasks ORDER BY id DESC")}}

    endpoint complete_task(id)
        query("UPDATE tasks SET done = 1 WHERE id = ?", (id,))
        return {{success: true}}

test "adding a task without a title is rejected"
    assert add_task("").success == false

test "added tasks are listed"
    add_task("Write the README")
    assert list_tasks().data[0].title == "Write the README"
'''

_UI = '''// {title} — user interface
// Preview: mcn studio .        Build: mcn build ui/app.mcn --out frontend

component AddTask
    state title   = ""
    state message = ""

    on submit
        var result = add_task(title)
        message = "Added!" if result.success else result.error
        if result.success
            notify("Task added", "success")

    render
        card
            card_header "New task"
            form on_submit=submit
                input bind=title label="What needs doing?"
                button "Add" variant="default"
                div
                    text message

component TaskList
    state items = []

    on load
        items = list_tasks().data

    render
        data_table title="Tasks" columns=["title", "done"] page_size=10 views=["table", "list"]

app {app_name}
    title "{title}"
    layout
        tabs
            tab "Add"   AddTask
            tab "Tasks" TaskList
'''

_README = '''# {title}

An [MCN](https://github.com/LeninPrakash41/mcn) app.

| File | What it is |
|---|---|
| `backend/main.mcn` | Database, API endpoints and tests |
| `ui/app.mcn` | Web UI (compiles to React with `mcn build`) |
| `mcn.json` | Project settings |

## Commands

```bash
mcn studio .                                # open this project in MCN Studio (browser IDE)
mcn serve --file backend/main.mcn           # run the API on http://localhost:8080
mcn test backend/main.mcn                   # run the test blocks
mcn check backend/main.mcn                  # find errors without running
mcn validate                                # check every .mcn file in the project
mcn build ui/app.mcn --out frontend         # generate a React app in frontend/
```

Set `ANTHROPIC_API_KEY` to use `ai()`, `classify()`, `extract()` and the Studio Copilot.
'''

_GITIGNORE = '''*.db
*.log
logs/
frontend/
mobile/build/
.dart_tool/
__pycache__/
.mcn/
'''


def _app_name(name: str) -> str:
    words = [w for w in Path(name).name.replace("_", "-").split("-") if w]
    return "".join(w[:1].upper() + w[1:] for w in words) or "App"


def init_project(name: str) -> int:
    root = Path(name)
    if root.exists() and any(root.iterdir()):
        print(f"error: '{name}' already exists and isn't empty")
        return 1
    app_name = _app_name(name)
    title = " ".join(w.capitalize() for w in Path(name).name.replace("_", "-").split("-") if w) or "My App"
    files = {
        "backend/main.mcn": _BACKEND.format(title=title),
        "ui/app.mcn": _UI.format(title=title, app_name=app_name),
        "README.md": _README.format(title=title),
        ".gitignore": _GITIGNORE,
        "mcn.json": json.dumps({"name": Path(name).name, "version": "0.1.0",
                                "backend": "backend/main.mcn", "ui": "ui/app.mcn"}, indent=2) + "\n",
    }
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    print(f"Created {name}/")
    for rel in files:
        print(f"  {rel}")
    print(f"\nNext steps:\n  cd {name}\n  mcn test backend/main.mcn\n  mcn studio .")
    return 0


def validate_project(path: str = ".") -> int:
    """Check every .mcn file in a project and that mcn.json's entry files exist."""
    from .diagnostics import check, render

    root = Path(path)
    problems = 0
    config = root / "mcn.json"
    if config.exists():
        try:
            settings = json.loads(config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"mcn.json: invalid JSON ({exc})")
            return 1
        for key in ("backend", "ui"):
            entry = settings.get(key)
            if entry and not (root / entry).exists():
                print(f"mcn.json: {key} file '{entry}' doesn't exist")
                problems += 1

    skip = {"node_modules", "frontend", "build", ".git", "legacy"}
    files = sorted(p for p in root.rglob("*.mcn") if not skip & set(p.relative_to(root).parts))
    if not files:
        print(f"No .mcn files found in {root.resolve()}. Create a project with: mcn init my-app")
        return 1
    for f in files:
        source = f.read_text(encoding="utf-8")
        for d in check(source):
            problems += 1
            print(f"{f.relative_to(root)}:{d.line}:{d.col}\n{render(d, source)}\n")
    print(f"{'FAIL' if problems else 'ok'}  {len(files)} file(s), {problems} problem(s)")
    return 1 if problems else 0
