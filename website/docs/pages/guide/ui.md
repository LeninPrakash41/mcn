# User interfaces

UI files describe screens as `component`s and arrange them with an `app` block. They're built from the **MCN UI kit**: data tables, charts, chat, agent and workflow builders, and an app frame with navigation, search and notifications. Studio previews the real app as you build, and `mcn build` turns it into a React project that uses the same components.

```mcn
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

Inside a handler, calling a function that isn't defined in the UI file, like `add_task(title)`, calls the backend endpoint of that name and returns its JSON response, so `result.success` and `list_tasks().data` work as you'd expect. When the backend is in `backend/main.mcn`, arguments are sent under the endpoint's own parameter names.

Elements that act on data take an endpoint or a handler name:

```mcn fragment
render
    chat "Support" endpoint=ask_bot              // sends {message, history} to ask_bot
    kanban group_by="stage" on_move=move_deal    // sends {id, stage, item}
    data_table on_delete=remove                  // runs `on remove` with the row as `row`
```

A handler wired to an element receives the value it's about: `row` or `item` for tables and boards, `agent` for the agent builder, `workflow` for the workflow builder, `message` for chat.

```mcn fragment
on remove
    delete_deal(row.id)
    notify("Deal deleted", "success")
    items = list_deals().data
```

## Data, charts and boards

```mcn fragment
render
    div grid_cols=4
        stat_card label="Revenue" value=stats.revenue icon="DollarSign" color="green"
        stat_card label="Open deals" value=stats.open icon="Target" color="blue"
    div grid_cols=2
        card
            card_header "Revenue by month"
            card_content
                area_chart data=monthly x_key="month" y_key=["won", "lost"] height=280
        card
            card_header "By region"
            card_content
                donut_chart data=regions name_key="region" value_key="total"
    data_table title="Deals" columns=["title", "owner", "stage", "value"] filters=["stage", "owner"] views=["table", "grid", "list"]
    kanban group_by="stage" columns=["Lead", "Qualified", "Won"] on_move=move_deal
```

- **`data_table`** has search, a filter dropdown for each column in `filters`, sortable headers, pagination, table/grid/list views and CSV export. Status-like columns become colored badges.
- **Charts** (`bar_chart`, `line_chart`, `area_chart`, `pie_chart`, `donut_chart`, `sparkline`) are responsive, with tooltips and legends. `y_key` can list several series; `stacked` stacks bars.
- **`kanban`** groups records into columns you drag cards between, with a mouse, a finger on the grip, or the arrow keys.
- **`grid_cols=N`** is one column on phones, two on tablets and N on wide screens.

## AI components

```mcn fragment
render
    chat "Support assistant" endpoint=ask_support suggestions=["Pricing?", "Reset password"]
    agent_builder agents=agents on_save=save on_test=test_agent
    workflow_builder workflows=workflows on_save=save on_run=run_workflow
```

- **`chat`** / **`chat_widget`**: a chat panel, or a floating chat button, backed by any endpoint that returns a reply.
- **`agent_builder`**: configure an agent's instructions, model, tools and knowledge, and test it live.
- **`workflow_builder`**: build automations from a trigger and steps (AI, condition, HTTP, database, notify, email, delay, approval) and run them step by step.

The **AI Agent Builder** and **Workflow Automation** templates in Studio include complete backends for these.

## Notifications

`notify(text, kind)` shows a toast and adds it to the bell in the header, where users can review recent notifications. `kind` is `info`, `success`, `warning` or `error`.

## Layouts

The `app` block names the app and arranges components inside the app frame: navigation, a header with breadcrumb, ⌘K search, notifications and a dark-mode toggle, and a footer.

```mcn fragment
app CRM
    title "CRM"
    logo "Briefcase"
    footer "Acme Inc"
    layout
        sidebar
            nav "Dashboard" Dashboard icon="LayoutDashboard"
            nav "Deals"     Deals     icon="TrendingUp" group="Sales"
            nav "Contacts"  Contacts  icon="Users"      group="Sales"
```

| Layout | Use it for |
|---|---|
| `sidebar` with `nav "Label" Component` | Business apps with many sections. Collapses to icons, becomes a drawer on phones; `group` adds headings |
| `tabs` with `tab "Label" Component` | A few screens of equal weight |
| `main` listing components | A single page that stacks components |

See the [UI element reference](#/reference/ui-elements) for every element and attribute.

## Preview and build

In Studio, **Preview** runs your actual app — compiled from `ui/app.mcn` and talking to your running backend — with nothing to install. Errors in the UI file show in the preview with the line and a hint.

To get a project you can deploy or extend:

```bash
mcn build ui/app.mcn --out frontend
cd frontend
npm install
npm run dev
```

The project uses Vite, React and Tailwind; the UI kit's source is in `src/components/ui`, so React is its only dependency. It calls the API at `http://localhost:8080` (set `VITE_API_URL` to change it).

If the backend uses `auth` (see [security](#/guide/security)), the app sends a bearer token from `localStorage` key `mcn_token`, or `VITE_API_TOKEN`. After a login endpoint returns a token, store it with the generated helper:

```ts
import { setToken } from "./services/api"
setToken(result.token)   // setToken(null) to log out
```

## Mobile apps

Studio's **App** view compiles the same `ui/app.mcn` to a Flutter project. Each `component` becomes a screen, the `app` block's `nav` items become a bottom navigation bar (a drawer when there are more than five), and state, `on_load` handlers and endpoint calls work as they do on the web. Tables become lists, and `kanban` cards move with a long press and drag.

`agent_builder` and `workflow_builder` are web-only; on mobile they show a note pointing to the web app. Projects without UI components still use `mobile/ui-manifest.json`, a JSON list of screens and widgets.

```bash
cd mobile
flutter create .                                              # first time: adds the android/ios/web folders
flutter pub get
flutter run --dart-define=MCN_API_URL=http://10.0.2.2:8080   # Android emulator; iOS and web use localhost
```

Screens live in `lib/screens/` (one file per component), shared widgets in `lib/mcn/mcn_runtime.dart`, and the API client in `lib/services/mcn_client.dart`. For a service with `auth`, add `--dart-define=MCN_API_TOKEN=...`, or set `MCNClient().token` after login. [Web and mobile](#/reference/ui-elements#web-and-mobile) lists how each element appears on a phone.
