# UI compiler

`mcn/core_engine/ui_compiler.py` turns MCN `component` and `app` declarations into a complete React project. `mcn build ui/app.mcn --out frontend` and Studio's **Preview** both use it.

## Output

```text
frontend/
├── package.json, vite.config.ts, tsconfig.json, tailwind.config.ts, postcss.config.js
├── components.json             # shadcn/ui config
├── index.html
└── src/
    ├── main.tsx, App.tsx       # App.tsx renders the app layout (tabs, sidebar or routes)
    ├── globals.css             # theme tokens
    ├── components/<Name>.tsx   # one file per MCN component
    ├── components/ui/*.tsx     # the shadcn/ui primitives that are used
    └── services/api.ts         # fetch wrapper; base URL from VITE_API_URL
```

The project type-checks with `tsc --noEmit` and builds with Vite. CI compiles every template and runs `tsc` on the result.

## How a component compiles

| MCN | React |
|---|---|
| `state items = []` | `const [items, setItems] = useState<any[]>([])` |
| `on load` | A `useEffect` that runs once and calls an async loader |
| `on submit` | `const submit = async () => { ... }`, wired to `<form onSubmit>` |
| `items = list_tasks().data` | `setItems((await api.post("/list_tasks", {})).data)` |
| `bind=title` | `value={title}` and an `onChange` that calls `setTitle` (with `Number()` for number inputs) |
| `card`, `table`, `button`, ... | The matching shadcn/ui components |
| `bar_chart`, `line_chart`, `pie_chart` | Recharts |
| `stat_card icon="Users"` | A tile with the `lucide-react` icon |

## Expressions and statements

`_expr_to_ts` translates expressions:

- `and`/`or`/`not` → `&&`/`||`/`!`; `==`/`!=` → `===`/`!==`; `null` → `null`; `?.` stays.
- Built-ins with a direct equivalent are inlined: `len(x)` → `x.length`, `str(x)` → `String(x)`, `upper`, `join`, `round`, `min`, `max` and others (`_TS_BUILTINS`).
- `a + b` on lists becomes `[...a, ...b]`; numeric addition is parenthesised so it isn't mistaken for string concatenation.
- Calls to names that aren't local functions or built-ins become backend calls through `api.post`.

`_stmts_to_ts` handles `var`, assignment (to state via its setter), `if`/`else`, `for` (including `for i, x in list`), `while`, `return`, `break` and `continue`.

## Tables and CRUD

An empty `table_body` generates rows by mapping over the table's `data` (or the component's list state), with one cell per `table_head`. Components whose state follows the `items` / `edit_<field>` / `show_edit_modal` pattern get edit and delete actions and an edit modal (`handleEdit`, `handleSave`, `handleDelete`).

## Extending the compiler

- **A new element:** add a branch in `_element_to_jsx`, list its shadcn import in `_collect_imports`, and add the primitive's source to `_write_ui_components` if it's new.
- **A new built-in:** add it to `_TS_BUILTINS`.
- Add the case to `tests/test_regressions.py` and make sure `MCN_E2E_REACT=1 pytest tests/test_templates_e2e.py` still type-checks every template.

## Flutter

The Flutter app comes from a different path: `mcn/fullstack/flutter_generator.py` reads `mobile/ui-manifest.json` (a JSON tree of screens and widgets) and writes a Flutter project with a client for the MCN API. Generating Flutter from MCN components is planned.
