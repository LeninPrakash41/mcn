# Quick start

Create a task tracker with a database, an API, tests and a web UI, then change it. This takes about ten minutes and assumes MCN is [installed](#/getting-started/installation).

## 1. Create a project

```bash
mcn init my-app
cd my-app
```

| File | What it is |
|---|---|
| `backend/main.mcn` | The database table, three endpoints and two tests |
| `ui/app.mcn` | Two screens: a form to add tasks and a list |
| `mcn.json` | Project settings |
| `README.md` | The commands for this project |

## 2. Run the tests

```bash
mcn test backend/main.mcn
```

```output
backend/main.mcn
  ✓ adding a task without a title is rejected  (0.1 ms)
  ✓ added tasks are listed  (0.3 ms)

  All 2 test(s) passed.
```

## 3. Read the backend

Open `backend/main.mcn`:

```mcn
query("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, done INTEGER DEFAULT 0)")

service tasks_api
    port 8080

    endpoint add_task(title)
        if not title
            return {success: false, error: "Title is required"}
        query("INSERT INTO tasks (title) VALUES (?)", (title,))
        return {success: true}

    endpoint list_tasks()
        return {success: true, data: query("SELECT * FROM tasks ORDER BY id DESC")}

    endpoint complete_task(id)
        query("UPDATE tasks SET done = 1 WHERE id = ?", (id,))
        return {success: true}

test "adding a task without a title is rejected"
    assert add_task("").success == false
```

- `query()` runs SQL on a SQLite database (`mcn_data.db`) that MCN creates for you. Values go in `?` placeholders, never joined into the SQL text.
- A `service` groups `endpoint`s. Each endpoint is a function and an HTTP route.
- Blocks are marked by indentation (4 spaces), not braces.

## 4. Serve the API

```bash
mcn serve backend/main.mcn
```

```bash
curl "http://localhost:8080/add_task?title=Buy%20milk"
curl http://localhost:8080/list_tasks
```

Open **http://localhost:8080/docs** for interactive API documentation. Press `Ctrl+C` to stop.

## 5. Open it in Studio

```bash
mcn studio .
```

Open **http://localhost:5003**. Press **Run** to start the backend, then **Preview** to see the web app built from `ui/app.mcn`. Add a task on the *Add* tab and find it on the *Tasks* tab. See [MCN Studio](#/getting-started/studio) for a tour.

## 6. Change something

Add a priority to tasks. In `backend/main.mcn`, add the column and a parameter with a default:

```mcn
query("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, done INTEGER DEFAULT 0, priority TEXT DEFAULT 'normal')")

service tasks_api
    port 8080

    endpoint add_task(title, priority = "normal")
        if not title
            return {success: false, error: "Title is required"}
        query("INSERT INTO tasks (title, priority) VALUES (?, ?)", (title, priority))
        return {success: true}
```

> **Note** `CREATE TABLE IF NOT EXISTS` doesn't change a table that already exists. Delete `mcn_data.db` after changing columns while you're developing.

Then add a test and run `mcn test backend/main.mcn` again:

```mcn fragment
test "priority defaults to normal"
    add_task("Write docs")
    assert list_tasks().data[0].priority == "normal"
```

## 7. Build the web app

```bash
mcn build ui/app.mcn --out frontend
cd frontend && npm install && npm run dev
```

The React app calls the API at `http://localhost:8080` (set `VITE_API_URL` to change it).

## Next steps

<!-- cards -->
- [Language basics](#/guide/language-basics) The syntax in one page.
- [Services and APIs](#/guide/services) Endpoints, parameters and responses.
- [User interfaces](#/guide/ui) Components, state, events and layouts.
- [AI functions](#/guide/ai) Add classification and summaries.
