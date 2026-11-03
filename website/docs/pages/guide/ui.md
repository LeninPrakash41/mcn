# User interfaces

UI files describe screens as `component`s and arrange them with an `app` block. `mcn build` compiles them to a React project that calls your backend.

```mcn
component AddTask
    state title   = ""
    state message = ""

    on submit
        var result = add_task(title)
        message = "Added!" if result.success else result.error

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
        card
            card_header "Tasks"
            table
                table_header
                    table_row
                        table_head "title"
                        table_head "done"
                table_body

app Tasks
    title "Tasks"
    layout
        tabs
            tab "Add"   AddTask
            tab "Tasks" TaskList
```

## Components

A component has three parts:

| Part | Meaning |
|---|---|
| `state name = value` | Data the screen shows and changes. Changing it re-renders the screen |
| `on event` | Code that runs on an event: `on load` when the screen opens, or a named handler like `on submit` |
| `render` | The element tree, one element per line, children indented |

## Calling the backend

Inside a handler, calling a function that isn't defined in the UI file, like `add_task(title)`, calls the backend endpoint of that name. The compiler turns it into an HTTP request and returns the JSON response, so `result.success` and `list_tasks().data` work as you'd expect.

The generated React app sends requests to `http://localhost:8080`; set `VITE_API_URL` to point it elsewhere.

## Elements and attributes

Elements take a text argument and `key=value` attributes:

```mcn fragment
render
    card
        card_header "Overview"
        div grid_cols=3
            stat_card label="Open tasks" value=items.length icon="ListTodo" color="blue"
        input bind=title label="Title" type="text"
        select bind=status options=["Open", "Done"] label="Status"
        button "Save" variant="default"
        bar_chart data=items x_key="title" y_key="hours" height=300
        table data=items
            table_header
                table_row
                    table_head "title"
            table_body
```

- `bind=name` connects an input to a state variable, both ways. Number inputs (`type="number"`) give numbers.
- `on_submit=submit` runs the `on submit` handler.
- An empty `table_body` fills itself with one row per item in the table's `data` (or the component's list state), using the `table_head` names as keys.

See the [UI element reference](#/reference/ui-elements) for every element.

## Layouts

The `app` block names the app and arranges components. Three layouts are available:

```mcn fragment
app CRM
    title "CRM"
    theme "professional"
    layout
        sidebar
            nav "Dashboard" Dashboard
            nav "Deals"     DealsTable
```

| Layout | Use it for |
|---|---|
| `tabs` with `tab "Label" Component` | A few screens of equal weight |
| `sidebar` with `nav "Label" Component` | Business apps with many sections |
| `main` listing components | A single page that stacks components |

## Build and run

```bash
mcn build ui/app.mcn --out frontend
cd frontend
npm install
npm run dev
```

The project uses Vite, React, Tailwind and shadcn/ui, and type-checks cleanly with `tsc`. In Studio, **Preview** builds and shows it for you.

## Mobile apps

Studio's **App** view generates a Flutter project from `mobile/ui-manifest.json`, a JSON list of screens and widgets (containers, text, charts, tables, buttons), with a client that calls your API and falls back to demo data offline. The mobile templates (smart home, expense tracker, field inspection) include ready-made manifests. Compiling `ui/app.mcn` components to Flutter is planned.
