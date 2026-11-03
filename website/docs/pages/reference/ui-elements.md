# UI elements

Elements available in a component's `render` block. Each line is `element "text" attribute=value ...`, and children are indented below their parent.

## Layout

| Element | Attributes | Notes |
|---|---|---|
| `div` | `grid_cols=N`, `style` | A container; `grid_cols` lays children out in N columns |
| `card` | | A bordered panel |
| `card_header "Title"` | | The card's heading |
| `card_content` | | The card's body |
| `separator` | | A horizontal rule |
| `tabs`, `accordion`, `accordion_item` | | Grouped sections inside a component |
| `modal`, `dialog`, `sheet` | `show=state_name` | Shown while the state is true |

## Text

| Element | Attributes | Notes |
|---|---|---|
| `text value` | | A value or state, e.g. `text message` |
| `h1`, `h2`, `p` | | Headings and paragraphs: `h2 "Overview"` |
| `badge "Label"` | `variant` | A small status label |
| `alert "Message"` | `variant` | A highlighted message |
| `tooltip` | | Hover help |

## Forms

| Element | Attributes | Notes |
|---|---|---|
| `form` | `on_submit=handler` | Runs `on handler` when submitted |
| `input` | `bind=state`, `label`, `type` | Two-way bound; `type="number"` gives numbers |
| `textarea` | `bind`, `label` | Multi-line input |
| `select` | `bind`, `options=[...]`, `label` | A dropdown |
| `checkbox`, `switch` | `bind`, `label` | True/false |
| `radio_group` | `bind`, `options`, `label` | One of several |
| `file_upload` | `label` | File picker |
| `button "Label"` | `variant` (`default`, `outline`, `destructive`, ...), `disabled` | Inside a `form`, submits it |

## Data

| Element | Attributes | Notes |
|---|---|---|
| `table` | `data=list` | With `table_header` → `table_row` → `table_head "column"` and an empty `table_body`, rows are generated from the list |
| `data_grid` | `data` | A data grid for larger lists |
| `pagination` | | Page controls for long lists |
| `stat_card` / `stat` | `label`, `value`, `icon`, `color`, `unit` | A KPI tile; `icon` takes a [Lucide](https://lucide.dev/icons) name |

## Charts

| Element | Attributes |
|---|---|
| `bar_chart` | `data`, `x_key`, `y_key`, `height` |
| `line_chart` | `data`, `x_key`, `y_key`, `height` |
| `pie_chart` | `data`, `x_key` (labels), `y_key` (values), `height` |
| `gantt_chart` | `data` |

## Repeating

```mcn fragment
render
    for task in items
        card
            text task.title
```

`for name in list` repeats its children for each item.

## App layout

The `app` block (outside components) takes `title`, `theme` and a `layout` with `tabs` (`tab "Label" Component`), `sidebar` (`nav "Label" Component`) or `main` (component names). See [user interfaces](#/guide/ui#layouts).
