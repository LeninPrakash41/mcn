# Testing

Tests live in the same file as the code they check, in `test` blocks. `mcn run` skips them; `mcn test` runs them.

```mcn
function grade(score)
    if score >= 90
        return "A"
    if score >= 70
        return "B"
    return "C"

test "high scores get an A"
    assert grade(95) == "A"

test "boundaries"
    assert grade(90) == "A"
    assert grade(70) == "B"
    assert_equal(grade(10), "C")
```

```bash
mcn test grades.mcn          # one file
mcn test tests/ --verbose    # every .mcn file in a folder
```

```output
grades.mcn
  ✓ high scores get an A  (0.0 ms)
  ✓ boundaries  (0.0 ms)

  All 2 test(s) passed.
```

The exit code is non-zero when a test fails, so `mcn test` works in CI.

## Assertions

`assert condition` fails when the condition is false. The helpers give clearer failure messages:

| Helper | Passes when |
|---|---|
| `assert_equal(a, b)` / `assert_not_equal(a, b)` | `a == b` / `a != b` |
| `assert_truthy(x)` / `assert_falsy(x)` | `x` is truthy / falsy |
| `assert_null(x)` / `assert_not_null(x)` | `x` is / isn't null |
| `assert_contains(list_or_text, item)` / `assert_not_contains(...)` | The item is / isn't in it |
| `assert_gt`, `assert_gte`, `assert_lt`, `assert_lte` | Numeric comparisons |
| `assert_len(x, n)` | `len(x) == n` |
| `assert_type(x, "string")` | `x` has that type: `string`, `number`, `bool`, `list`, `object` or `null` |
| `assert_throws(fn)` | Calling `fn` raises an error |

## Testing an API

Endpoints are functions, so test them directly — no server needed:

```mcn
query("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)")

service items_api
    port 8080

    endpoint add_item(name)
        if not name
            return {success: false, error: "Name is required"}
        query("INSERT INTO items (name) VALUES (?)", (name,))
        return {success: true}

test "names are required"
    assert add_item("").success == false

test "items are saved"
    add_item("Lamp")
    assert len(query("SELECT * FROM items WHERE name = ?", ("Lamp",))) > 0
```

> **Note** Tests use the same `mcn_data.db` as the program. Write tests that don't depend on the database starting empty, or run them from a scratch folder.

## Static checks

`mcn check` finds syntax errors, misspelt names and type problems without running anything — fast enough for a pre-commit hook:

```bash
mcn check backend/main.mcn
mcn validate                # every .mcn file in the project
```
