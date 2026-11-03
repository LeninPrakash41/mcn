# MCN Pilot Exercises

Eight exercises, from first program to your own full-stack app. Each takes
20–45 minutes. Work in MCN Studio (`mcn studio`) or
with `mcn run file.mcn`.

Every exercise lists what "done" means. Exercises 1–7 have checks you can run
yourself: add the `test` blocks shown and run `mcn test yourfile.mcn`.
Reference solutions are in [`solutions/`](solutions/); try first, then compare.

---

## 1. Hello, decisions (20 min)

**Goal:** greet people differently in the morning and the afternoon.
**You'll practise:** variables, text, `if … else`, functions, `for` loops.

1. Make a list of three names.
2. Write `function greeting(name, hour)` that returns `"Good morning, Ada!"` before
   12:00 and `"Good afternoon, Ada!"` otherwise.
3. Loop over the names and `log` a greeting for each.

**Done when:**
```mcn
test "morning greeting"
    assert greeting("Ada", 9) == "Good morning, Ada!"
test "afternoon greeting"
    assert greeting("Grace", 15) == "Good afternoon, Grace!"
```
**Stretch:** add "evening" after 18:00 using the one-line form `"a" if cond else "b"`.

---

## 2. Grade book (30 min)

**Goal:** turn a list of scores into averages and letter grades.
**You'll practise:** lists, loops, returning values, built-ins (`avg`, `len`).

1. `var scores = [72, 88, 95, 64, 81]`
2. `function letter(score)`: 90+ → `"A"`, 80+ → `"B"`, 70+ → `"C"`, else `"F"`.
3. `function highest(values)`: find the largest value **with a loop** (no built-in `max`).
4. Log the average and the highest score with its letter.

**Done when:** `letter(95) == "A"`, `letter(70) == "C"`, `highest(scores) == 95`.

---

## 3. Read the error, fix the bug (25 min)

**Goal:** get comfortable with MCN's error messages.
**You'll practise:** reading errors, validation with `throw`.

Paste this into Studio and press **Run**. Fix one error at a time, reading the
message and hint each time. There are three bugs.

```mcn
function to_fahrenheit(celsius)
return celsius * 9 / 5 + 32

var readings = [0, 21.5, 100]
for c in readings
    log(str(c) + "°C = " + str(to_farenheit(c) + "°F")
```

Then make `to_fahrenheit` `throw "Below absolute zero"` for values below -273.15.

**Done when:** it prints three conversions, and `to_fahrenheit(100) == 212`.

---

## 4. Library catalogue (30 min)

**Goal:** store and search data with the built-in database.
**You'll practise:** `query()` with `CREATE TABLE`, `INSERT` and `SELECT`, `?` parameters.

1. Create a `books` table with `title`, `author` and `year`.
2. Write `function add_book(title, author, year)` and add three books.
   Always pass values with `?` placeholders, never by joining strings.
3. Log the titles of books published before 2000, sorted by title.
4. Open the **DB Explorer** panel in Studio and look at your table.

**Done when:** `query("SELECT COUNT(*) as n FROM books")[0].n == 3`.

---

## 5. Expense tracker API (40 min)

**Goal:** build a real backend with three API endpoints.
**You'll practise:** `service`, `endpoint`, validation, returning JSON.

1. Create an `expenses` table (`title`, `amount`, `category`).
2. In `service expenses_api` (port 8080) add:
   - `add_expense(title, amount, category)`: reject amounts ≤ 0 with
     `{success: false, error: "Amount must be positive"}`.
   - `list_expenses()`: newest first.
   - `total_by_category()`: `SUM(amount)` grouped by category.
3. Call your endpoints at the bottom of the file to try them.

**Done when:** `add_expense("Refund", -5, "food").success == false`, and the
food total is 16 after adding 12.5 and 3.5.
**Stretch:** in Studio, open **Tools → API Docs** to see your endpoints in Swagger.

---

## 6. Add a user interface (45 min)

**Goal:** turn exercise 5 into a web and mobile app.
**You'll practise:** `component`, `state`, `on submit` / `on load`, `render`, `app`.

1. Put your exercise 5 service in `backend/main.mcn`.
2. In `ui/app.mcn` create:
   - `AddExpense`: a form with inputs bound to `title`, `amount` and `category`
     that calls `add_expense` on submit and shows "Saved!" or the error.
   - `ExpenseList`: loads `list_expenses()` on load and shows a table.
   - `app ExpenseTracker` with two tabs.
3. Press **Preview**. Add an expense, then check the History tab.
4. Switch to **App** (mobile) in the left bar to see the Flutter version.

**Done when:** you can add an expense in the preview and see it in the list.

---

## 7. AI support triage (30 min)

**Goal:** route support tickets to the right team with one line of AI.
**You'll practise:** `classify()`, `ai()`, the AI & RAG inspector.

1. Make a list of three support tickets (billing, a bug, an account question).
2. Write `function triage(text)` returning `{text: text, team: classify(text, ["billing", "bug", "account"])}`.
3. Log the team for each ticket, then open the **AI & RAG** panel.
4. Add a one-line summary of each ticket with `ai("Summarise in 8 words: " + text)`.

> **No API key?** Mock mode always picks the first label and returns placeholder
> text, so every ticket goes to "billing". Your code is still correct. Set
> `ANTHROPIC_API_KEY` to see real routing.

**Done when:** every ticket's team is one of the three labels.

---

## 8. Capstone: your own app (2–4 hours)

Build something you'd actually use, in pairs. Ideas: a study planner, a
club event sign-up, a recipe box, an inventory for a small shop.

| Requirement | Points |
|---|---|
| At least one table and three endpoints | 25 |
| Input validation with clear error responses | 15 |
| A UI with a form and a list, working in Preview | 25 |
| One AI feature (summarise, classify, extract or rag) | 15 |
| Tests for at least three endpoints (`test` blocks) | 10 |
| Short demo: what it does and one thing that was hard | 10 |

Start from a template (**Templates** menu) or from scratch.
