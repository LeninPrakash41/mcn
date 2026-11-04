# UI elements

Every element available in a component's `render` block. Each line is `element "text" attribute=value ...`, and children are indented under their parent. All of them come from the **MCN UI kit**: the same components render in Studio's preview and in the React app `mcn build` generates. Studio's **App** view compiles the same file to Flutter; [web and mobile](#/reference/ui-elements#web-and-mobile) lists how each element appears there.

## App frame

The `app` block renders inside a shell with navigation, a header (breadcrumb, ⌘K search, notifications, dark-mode toggle) and a footer. See [layouts](#/guide/ui#layouts).

| App line | Meaning |
|---|---|
| `title "Name"` | App name in the header and browser tab |
| `logo "Rocket"` | Icon next to the title |
| `footer "Acme Inc"` | Footer text |
| `layout` → `sidebar` / `tabs` / `main` | How sections are arranged |
| `nav "Label" Component icon="Users" group="Sales"` | A sidebar item; `group` adds a section heading |

The sidebar collapses to icons (button or `Ctrl+\`), becomes a drawer on phones, and remembers its state. The active section is in the URL, so links and the back button work.

## Data

| Element | Attributes | What it does |
|---|---|---|
| `data_table` | `data`, `columns`, `title`, `description`, `filters`, `page_size`, `views`, `searchable`, `exportable`, `title_key`, `empty`, `add_label`, `on_add`, `on_row`, `on_edit`, `on_delete` | Search, a filter dropdown per column in `filters`, click-to-sort headers, pagination, `views=["table", "grid", "list"]`, CSV export, row actions. Status-like columns (`status`, `stage`, `priority`…) render as colored badges; money and dates are formatted. Without `data`, it shows the component's first list state |
| `kanban` | `data`, `group_by`, `columns`, `title_key`, `fields`, `on_move`, `on_click` | A board with a column per value of `group_by`. Move cards by dragging with a mouse, dragging the grip with a finger, or with ← → when a card has focus. `on_move` gets `{id, <group_by>: new value, item}` |
| `table` | `data` | A plain table: `table_header` → `table_row` → `table_head "column"` and an empty `table_body` |
| `stat_card` | `label`, `value`, `icon`, `color`, `unit`, `trend` | A KPI tile. `color`: blue, green, red, amber, purple |
| `pagination` | `page`, `total`, `page_size` | Page controls for your own lists |

## Charts

All charts are responsive, show a tooltip on hover, draw a legend for several series and show an empty state when there's no data (`empty="No sales yet"`).

| Element | Attributes |
|---|---|
| `bar_chart` | `data`, `x_key`, `y_key` (one key or a list), `stacked`, `height`, `colors` |
| `line_chart` | `data`, `x_key`, `y_key`, `height`, `colors` |
| `area_chart` | `data`, `x_key`, `y_key`, `height`, `colors` |
| `pie_chart` | `data`, `name_key`, `value_key`, `height` |
| `donut_chart` | `data`, `name_key`, `value_key`, `height` — the total shows in the middle |
| `sparkline` | `data` (numbers, or objects with `y_key`), `height`, `width` |

```mcn fragment
render
    bar_chart data=sales x_key="month" y_key=["won", "lost"] stacked height=280
    donut_chart data=regions name_key="region" value_key="total"
```

## AI

| Element | Attributes | What it does |
|---|---|---|
| `chat "Title"` | `endpoint`, `welcome`, `suggestions`, `placeholder`, `height`, `avatar` | A chat panel. Sends `{message, history}` to the endpoint and shows the reply (a string, or `reply`/`answer`/`message` from an object). Markdown, typing indicator, retry, copy. If the reply has `tool_calls` (from `agent_run`), shows each tool used with its input and output |
| `chat_widget` | same as `chat` | The chat as a floating button in the corner |
| `agent_builder` | `agents`, `tools`, `models`, `on_save`, `on_test`, `on_delete` | Configure an agent (instructions, model, creativity, tools, knowledge, memory) and test it in a live chat. Sends `{agent}` to `on_save` and `{agent, message, history}` to `on_test` |
| `workflow_builder` | `workflows`, `step_types`, `on_save`, `on_run` | A visual automation editor: a trigger (manual, schedule, webhook, new record) and steps (AI, condition, HTTP, database, notify, email, delay, transform, approval) with validation. Sends `{workflow}`; `on_run` returns `{steps: [{id, status, output, error}]}` |

## Navigation and feedback

| Element | Attributes | What it does |
|---|---|---|
| `breadcrumb` | `items` | `Home / Deals / Acme` — the last item is the current page |
| `empty_state "Title"` | `description`, `icon` | A friendly placeholder for empty screens |
| `alert "Message"` | `variant` | A highlighted message |
| `badge "Label"` | `variant` | A small label |

Notifications are a function, not an element: `notify("Saved", "success")` in any handler shows a toast and adds it to the bell in the header. Kinds: `info`, `success`, `warning`, `error`.

## Layout

| Element | Attributes | Notes |
|---|---|---|
| `div` | `grid_cols=N`, `style` | `grid_cols` is responsive: one column on phones, two on tablets, N on wide screens |
| `card`, `card_header "Title"`, `card_content` | | A bordered panel |
| `separator` | | A horizontal rule |
| `tabs`, `accordion`, `accordion_item` | | Grouped sections inside a component |
| `modal`, `dialog`, `sheet` | `show=state_name` | Shown while the state is true |
| `h1`, `h2`, `p`, `text value` | | Headings, paragraphs and values |

## Forms

| Element | Attributes | Notes |
|---|---|---|
| `form` | `on_submit=handler` | Runs `on handler` when submitted |
| `input` | `bind=state`, `label`, `type`, `placeholder` | Two-way bound; `type="number"` gives numbers |
| `textarea` | `bind`, `label` | Multi-line input |
| `select` | `bind`, `options=[...]`, `label` | A dropdown |
| `checkbox`, `switch` | `bind`, `label` | True/false |
| `radio_group` | `bind`, `options`, `label` | One of several |
| `button "Label"` | `variant` (`default`, `outline`, `destructive`…), `disabled` | Inside a `form`, submits it |

## Icons

Any `icon=` attribute takes a [Lucide](https://lucide.dev/icons) icon name such as `Users`, `TrendingUp`, `ShoppingCart`, `Bot` or `Workflow` (case doesn't matter). MCN includes about 200 common icons, including sensors and devices for IoT apps; an unknown name shows a circle.

## Web and mobile

The React app supports every element on this page. The Flutter app maps them to native widgets:

| On mobile | Elements |
|---|---|
| Native equivalent | `app` and `nav` (bottom navigation bar, or a drawer beyond five items), `card`, `stat_card`, `data_table` / `table` (a list of rows), `kanban` (long-press a card and drag it to a column), all five charts, `chat` / `chat_widget` (with tool calls), `form`, `input`, `textarea`, `select`, `checkbox`, `switch`, `button`, `badge`, `alert`, `empty_state`, `progress`, `img`, headings and text, `div` with `grid_cols` (columns on wide screens, one on phones) |
| Shown one after another | `tabs`, `accordion` and their sections |
| A note pointing to the web app | `agent_builder`, `workflow_builder` |
| Left out | `sparkline`, `pagination`, `radio_group`, `breadcrumb`, `tooltip`, and `modal` / `dialog` / `sheet` with their contents |

State, `on_load`, handlers, `if`/`for`, `notify()` and endpoint calls behave the same on both. Keep anything a phone user needs out of modals, or show it with `show=` on a normal element.

## Repeating

```mcn fragment
render
    for task in items
        card
            text task.title
```

`for name in list` repeats its children for each item.
