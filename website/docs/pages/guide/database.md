# Database

Every MCN program has a SQLite database. The first `query()` creates `mcn_data.db` in the folder you run from; there's nothing to install or configure.

## Create, insert, select

```mcn
query("CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, year INTEGER)")

query("INSERT INTO books (title, year) VALUES (?, ?)", ("Dune", 1965))
query("INSERT INTO books (title, year) VALUES (?, ?)", ("Neuromancer", 1984))

var old = query("SELECT * FROM books WHERE year < ? ORDER BY title", (1980,))
for book in old
    log(book.title + " (" + str(book.year) + ")")

var count = query("SELECT COUNT(*) AS n FROM books")[0].n
```

- `SELECT` returns a **list of objects**, one per row, keyed by column name.
- Other statements return `[{affected_rows: N}]`.

## Always use `?` placeholders

Pass values as the second argument, never by joining text into the SQL:

```mcn
query("CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, year INTEGER)")
var title = "Dune"
query("SELECT * FROM books WHERE title = ?", (title,))      // safe
query("SELECT * FROM books WHERE title = ?", title)         // one value can be passed on its own
```

Joining user input into SQL lets someone change your query (SQL injection). Placeholders are also faster and handle quotes for you.

> **Note** `(title,)` with a trailing comma is a one-item tuple. A single value without brackets also works. Objects and lists passed as values are stored as JSON text.

## Changing a table

`CREATE TABLE IF NOT EXISTS` does nothing when the table already exists, so adding a column to it won't change an existing database. While developing, delete `mcn_data.db`; in production, run an `ALTER TABLE` once.

## Inspecting data

In Studio, the **DB Explorer** shows your tables and runs SQL against the same database. From a terminal, `sqlite3 mcn_data.db` works too.

## PostgreSQL and MongoDB

```mcn fragment
var conn = connect_postgresql("localhost", "shop", "app", env("DB_PASSWORD"))
if conn.success
    var rows = query("SELECT * FROM orders LIMIT 10")
```

After `connect_postgresql(host, database, user, password, port?)` succeeds, `query()` runs against PostgreSQL. It also takes one connection URL, as hosted databases give you: `connect_postgresql(env("DATABASE_URL"))`. Keep using `?` placeholders; write table definitions in PostgreSQL SQL (`SERIAL` instead of `AUTOINCREMENT`). `connect_mongodb(connection_string, database)` works the same way. Both are optional features: add them once with `mcn add postgres` or `mcn add mongodb`. Keep passwords in environment variables and read them with `env()`.
