# Student pilot kit

Everything needed to run MCN with a class or a small group of students, in `docs/pilot/` in the repository.

| File | For | What it is |
|---|---|---|
| `STARTER_GUIDE.md` | Students | Install, a tour of Studio, the language in five minutes, reading errors |
| `EXERCISES.md` | Students | Eight exercises, from a first program to a full-stack app with AI |
| `solutions/` | Facilitators | Reference solutions, each with `test` blocks |
| `FACILITATOR_GUIDE.md` | Facilitators | Two-session schedule, what to observe, metrics and follow-up |
| `FEEDBACK_FORM.md` | Students | End-of-pilot questionnaire |

## The exercises

| # | Exercise | Practises |
|---|---|---|
| 1 | Hello, decisions | Variables, `if`/`else`, functions, loops |
| 2 | Grade book | Lists, loops, return values, `avg` and `len` |
| 3 | Read the error, fix the bug | Error messages: three planted bugs, fixed one at a time |
| 4 | Library catalogue | `query()`, tables, `?` parameters, the DB Explorer |
| 5 | Expense tracker API | `service`, `endpoint`, validation, JSON responses |
| 6 | Add a user interface | `component`, `state`, `on submit`, `app`, preview, mobile |
| 7 | AI support triage | `classify()`, `ai()`, the AI & RAG inspector |
| 8 | Capstone | An app of the students' choosing, in pairs, with a rubric |

## Built to keep working

The reference solutions, exercise 3's error sequence and the starter guide's sample code are all run by MCN's test suite on every change, so the kit can't silently fall behind the language.

> **Tip** AI functions work without an API key in mock mode, so a class doesn't need keys. Mock `classify()` always picks the first label; set `ANTHROPIC_API_KEY` to see real routing.
