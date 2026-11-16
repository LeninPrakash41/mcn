# UI elements

Every element available in a component's `render` block. Each line is `element "text" attribute=value ...`, and children are indented under their parent. All of them come from the **MCN UI kit**: the same components render in Studio's preview and in the React app `mcn build` generates. Studio's **App** view compiles the same file to Flutter; [web and mobile](#/reference/ui-elements#web-and-mobile) lists how each element appears there.

## App frame

The `app` block renders inside a shell with navigation, a header (breadcrumb, ⌘K search, notifications, dark-mode toggle) and a footer. See [layouts](#/guide/ui#layouts).

| App line | Meaning |
|---|---|
| `title "Name"` | App name in the header and browser tab |
| `logo "Rocket"` | Icon next to the title |
| `footer "Acme Inc"` | Footer text |
| `brand "violet"` | Brand color for buttons, links, rings and accents, in light and dark mode: a hex color (`"#7c3aed"`) or `blue`, `indigo`, `violet`, `purple`, `pink`, `rose`, `red`, `orange`, `amber`, `green`, `emerald`, `teal`, `cyan`, `sky`, `slate`, `black` |
| `font "Poppins"` | Any Google Font, or `system` (default Inter) |
| `corners "round"` | `sharp`, `soft`, `round` (default) or `extra` |
| `buttons "pill"` | `rounded` (default), `pill` or `square` |
| `mode "dark"` | `auto` (default, follows the device), `light` or `dark` |
| `navbar "floating"` | Phone app: `bar` (default), `floating`, `icons` or `drawer` |
| `header "large"` | Phone app: `standard` (default), `large` or `centered` |
| `cards "elevated"` | Phone app: `outlined` (default), `elevated` or `flat` |
| `toasts "top"` | Phone app: `bottom` (default) or `top` |
| `layout` → `sidebar` / `tabs` / `main` / `page` | How sections are arranged; `page` is a landing page without the app frame |
| `nav "Label" Component icon="Users" group="Sales"` | A sidebar item; `group` adds a section heading |

The sidebar collapses to icons (button or `Ctrl+\`), becomes a drawer on phones, and remembers its state. The active section is in the URL, so links and the back button work.

## Data

| Element | Attributes | What it does |
|---|---|---|
| `data_table` | `data`, `columns`, `title`, `description`, `filters`, `page_size`, `views`, `searchable`, `exportable`, `title_key`, `empty`, `add_label`, `on_add`, `on_row`, `on_edit`, `on_delete` | Search, a filter dropdown per column in `filters`, click-to-sort headers, pagination, `views=["table", "grid", "list"]`, CSV export, row actions. Status-like columns (`status`, `stage`, `priority`…) render as colored badges; money and dates are formatted. Without `data`, it shows the component's first list state |
| `kanban` | `data`, `group_by`, `columns`, `title_key`, `fields`, `on_move`, `on_click` | A board with a column per value of `group_by`. Move cards by dragging with a mouse, dragging the grip with a finger, or with ← → when a card has focus. `on_move` gets `{id, <group_by>: new value, item}` |
| `table` | `data` | A table with search and pages: `table_header` → `table_row` → `table_head "column"` and an empty `table_body`. It gets **New**, **Edit** and **Delete** buttons for the backend's `create_<item>`, `update_<item>` and `delete_<item>` endpoints (for `OrdersTable`: `create_order` …), each only when that endpoint exists and the table's columns (plus `id`) supply all its parameters |
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
| `tabs`, `accordion`, `accordion_item "Title"` | | Grouped sections inside a component; each `accordion_item` is titled by its text (or `title=`) |
| `modal`, `dialog`, `sheet` | `show=state_name` | Shown while the state is true |
| `h1`, `h2`, `p`, `text value` | | Headings, paragraphs and values |

## App design

Elements for consumer-style screens. Each has a native widget on phones.

| Element | Attributes | Notes |
|---|---|---|
| `avatar "Name"` | `src`, `size`, `color`, `online` | A round photo, or initials on a tinted circle; `online` adds a green dot |
| `list_item "Title"` | `subtitle`, `icon`, `color`, `avatar`, `person`, `trailing`, `badge`, `on_click`, `item`, `link` | A row with an icon or avatar, a title and subtitle, and a value or badge at the end. `on_click=open item=w` runs `on open` with `w` as `item` |
| `progress_ring` | `value` (0–100), `label`, `center`, `color`, `size`, `thickness` | A circular progress ring, like activity rings |
| `carousel "Title"` | `width` | Its children in a row that scrolls sideways and snaps (each `width` pixels wide, 260 by default) |

`color` takes a name (`rose`, `sky`, `green`, `amber`, `violet`…), a hex color, or `primary` (the brand color, the default).

## Landing pages

Sections for a marketing page, used with the `page` layout. They follow the app's `brand` color.

| Element | Attributes | Notes |
|---|---|---|
| `navbar "Brand"` | `logo`, `links`, `cta`, `cta_link`, `on_cta` | A sticky top bar. Each link scrolls to the section whose `id` is the link in lower case (`"Pricing"` → `id="pricing"`); a menu on phones |
| `hero "Headline"` | `eyebrow`, `subtitle`, `primary`, `secondary`, `primary_link`, `secondary_link`, `on_primary`, `on_secondary`, `image`, `note`, `variant`, `id` | The opening section. Children (cards, rings, list rows) or `image` show beside the headline. `variant`: `gradient` (default), `dark` or `plain`. Inside an app screen it's a rounded banner |
| `logo_cloud "Trusted by"` | `names` | A row of company names |
| `feature_grid "Title"` → `feature "Name"` | grid: `eyebrow`, `subtitle`, `columns`, `id`; feature: `icon`, `description` | Feature cards in a grid |
| `pricing "Title"` → `plan "Name"` | pricing: `eyebrow`, `subtitle`, `id`; plan: `price`, `period`, `description`, `features`, `cta`, `link`, `on_click`, `highlight`, `badge` | Plans side by side; `highlight` marks one with a ring and a "Most popular" badge (or `badge=`) |
| `testimonials "Title"` → `testimonial "Quote"` | `author`, `role`, `avatar`, `rating` | Quotes with stars and the person's initials or photo |
| `faq "Title"` → `question "Question?"` | `answer` | Questions that open when tapped |
| `cta_band "Title"` | `subtitle`, `cta`, `link`, `on_click`, `secondary`, `secondary_link`, `on_secondary`, `id` | A colored call-to-action band; children (a sign-up form) show on a card inside it |
| `site_footer "Brand"` | `logo`, `text`, `links` | The page footer |

`*_link` attributes take `"#id"` to scroll to a section, or a web address. `on_*` attributes name an `on` handler or a backend endpoint. Section titles can also take `eyebrow` (a small label above) and `subtitle`.

## Forms

| Element | Attributes | Notes |
|---|---|---|
| `form` | `on_submit=handler` | Runs `on handler` when submitted |
| `input` | `bind=state`, `label`, `type`, `placeholder` | Two-way bound; `type="number"` gives numbers |
| `textarea` | `bind`, `label` | Multi-line input |
| `select` | `bind`, `options=[...]`, `label` | A dropdown |
| `checkbox`, `switch` | `bind`, `label` | True/false |
| `radio_group` | `bind`, `options`, `label` | One of several |
| `button "Label"` | `variant` (`default`, `outline`, `destructive`…), `icon`, `disabled` | Inside a `form`, submits it; `icon="Plus"` shows an icon before the label |

## Icons

Any `icon=` attribute takes a [Lucide](https://lucide.dev/icons) icon name such as `Users`, `TrendingUp`, `ShoppingCart`, `Bot` or `Workflow` (case doesn't matter). MCN includes about 220 common icons, including sensors and devices for IoT apps and fitness and health icons such as `HeartPulse`, `Footprints` and `Dumbbell`; an unknown name shows a circle.

## Web and mobile

The React app supports every element on this page. The Flutter app maps them to native widgets:

| On mobile | Elements |
|---|---|
| Native equivalent | the [app design](#/reference/ui-elements#app-design) and [landing page](#/reference/ui-elements#landing-pages) elements, `app` and `nav` (bottom navigation bar, or a drawer beyond five items), `card`, `stat_card`, `data_table` / `table` (a list of rows), `kanban` (long-press a card and drag it to a column), all five charts, `chat` / `chat_widget` (with tool calls), `form`, `input`, `textarea`, `select`, `checkbox`, `switch`, `button`, `badge`, `alert`, `empty_state`, `progress`, `img`, headings and text, `div` with `grid_cols` (columns on wide screens, one on phones) |
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
