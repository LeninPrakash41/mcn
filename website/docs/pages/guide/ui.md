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

The **AI Agent Builder**, **Voice Agent Builder** and **Workflow Automation** templates in Studio include complete backends for these.

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
| `page` listing components | A landing page: the components fill the screen without the app frame |

`brand "violet"` (or a hex color such as `"#7c3aed"`) in the `app` block colors buttons, links, rings, charts and accents in light and dark mode, on the web and on phones.

### Design: colour, font, corners, buttons, mode

Five optional lines in the `app` block set an app's design, on the web and on phones:

```mcn fragment
app Shop
    title "Shop"
    brand "teal"          // a colour name or a hex such as "#0d9488"
    font "Poppins"        // any Google Font, or "system"
    corners "round"       // sharp | soft | round | extra
    buttons "pill"        // rounded | pill | square
    mode "auto"           // auto (follows the device) | light | dark
```

| Line | Values | Default |
|---|---|---|
| `brand` | `blue`, `indigo`, `violet`, `purple`, `pink`, `rose`, `red`, `orange`, `amber`, `green`, `emerald`, `teal`, `cyan`, `sky`, `slate`, `black`, or a hex colour | violet |
| `font` | Any [Google Font](https://fonts.google.com) name, or `system` | Inter |
| `corners` | `sharp`, `soft`, `round`, `extra`: cards, inputs and banners follow it | `round` |
| `buttons` | `rounded`, `pill`, `square` | `rounded` |
| `mode` | `auto`, `light`, `dark`. People can still switch with the moon icon | `auto` |

#### The phone app

Four more lines style the Flutter app (the web app ignores them):

```mcn fragment
app Pulse
    navbar "floating"     // bar | floating | icons | drawer
    header "large"        // standard | large | centered
    cards "elevated"      // outlined | elevated | flat
    toasts "top"          // bottom | top
```

| Line | Values |
|---|---|
| `navbar` | `bar` (default): a bottom navigation bar with labels. `floating`: a rounded bar floating above the content. `icons`: icons only, with the current section's label. `drawer`: a menu that slides in from the side |
| `header` | `standard` (default): the title in the top bar. `large`: a big title that opens each screen and scrolls away. `centered`: the title in the middle of the top bar |
| `cards` | `outlined` (default): a hairline border. `elevated`: a soft shadow, no border. `flat`: a lightly tinted panel |
| `toasts` | `bottom` (default) or `top`: where `notify()` messages appear, with an icon for success, warning and error |

**In Studio**, the **Design** button above the Preview opens swatches, a custom colour picker, fonts and toggles for the rest. Each choice writes its line into `ui/app.mcn` and the preview reloads at once, so the code always says what the app looks like. Its **Phone app** section sets the four phone lines; the phone preview is compiled, so it rebuilds (in about half a minute) when one is showing.

### The default look

Every app gets a modern look without any styling: MCN's violet brand color (unless you set `brand`), a softly tinted background, rounded cards with gentle depth, bold headings, large KPI numbers, rounded inputs and buttons, charts in the brand color, and comfortable spacing between whatever a `div` stacks. `theme` picks a variant: `"professional"` (indigo), `"minimal"` (slate, square-ish corners), `"glassmorphism"` or `"luxury_dark"`. Start a screen with a `hero` banner for a welcome area, as the templates do.

See the [UI element reference](#/reference/ui-elements) for every element and attribute.

## Consumer-style screens

For apps that should feel like a consumer product rather than a dashboard: a `hero` banner, `avatar`s, `list_item` rows, `progress_ring`s and sideways `carousel`s. They're native widgets on phones.

```mcn fragment
render
    hero {t.greeting} eyebrow={t.streak} subtitle={t.subtitle} primary="Start workout" on_primary=start variant="dark"
        div grid_cols=3
            progress_ring value=t.move label="Move" color="rose"
            progress_ring value=t.goal label="Goal"
            progress_ring value=t.water label="Water" color="sky"
    carousel "Up next" width=230
        for w in upcoming
            list_item {w.title} subtitle={w.detail} icon="Dumbbell" item=w on_click=open_workout
    list_item "Coach" subtitle="Keep today's run easy" icon="Bot" badge="New"
```

`item=w` hands the row to the handler, which reads it as `item` (`on open_workout` → `notify(item.title)`).

## Landing pages

The `page` layout and the landing-page sections build a marketing site from the same file as the app, with the same brand color:

```mcn
component Landing
    render
        navbar "Pulse" logo="Activity" links=["Features", "Pricing", "FAQ"] cta="Get the app" cta_link="#join"
        hero "Train smarter. Recover better." eyebrow="New" subtitle="A plan that adapts every day." primary="Get the app" primary_link="#join" secondary="See pricing" secondary_link="#pricing"
        feature_grid "Everything you need" id="features"
            feature "Adaptive plans" icon="Sparkles" description="Your week rebuilds itself around your sleep."
            feature "An AI coach" icon="Bot" description="Answers based on your own data."
        pricing "Simple pricing" id="pricing"
            plan "Free" price="$0" period="/month" features=["Tracking", "Weekly summaries"] cta="Start free"
            plan "Plus" price="$8" period="/month" features=["Adaptive plans", "The AI coach"] cta="Try Plus" highlight
        testimonials "Loved by people who move"
            testimonial "It noticed I was overtraining before I did." author="Priya Shah" role="Marathoner"
        faq "Questions" id="faq"
            question "Can I cancel any time?" answer="Yes, month to month."
        cta_band "Ready to start?" id="join" cta="Get the app"
        site_footer "Pulse" text="© 2026 Pulse Labs" links=["Features", "Pricing"]

app Site
    title "Pulse"
    brand "violet"
    layout
        page
            Landing
```

Navbar and footer links scroll to the section with the matching `id`, on the web and in the phone app. A form nested in `cta_band` (a waitlist, say) shows on a card inside it. See [landing pages](#/reference/ui-elements#landing-pages) for every attribute.

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

### What the generated code looks like

The output is code you'd be comfortable committing and extending, not a black box:

- **Typed data.** State is typed from its starting value (`state stats = {revenue: 0}` becomes an `interface` with `revenue: number`). A list filled from an endpoint that returns a table's rows unchanged (`SELECT * FROM orders`) is typed from that table's columns, so `items` is an `Order[]`. Values MCN can't know the type of are `BackendValue`, defined once in `src/types.ts`.
- **Loading and errors.** Each screen with `on load` shows a loading bar, and if loading fails, the error with a **Retry** button. When an action such as a save or delete fails, the user sees an error notification.
- **Parallel calls.** Backend calls in a row that don't depend on each other run at the same time (`Promise.all`).
- **Kit components.** KPIs are `<Stat … />`, tables are `<DataTable … />`, and so on, so the screens stay short.
- **Tooling.** ESLint, Prettier and Vitest are set up, with a generated smoke test for every screen in `src/test/screens.test.tsx`:

```bash
npm run typecheck    # TypeScript
npm run lint         # ESLint (TypeScript and React hooks rules)
npm run format       # Prettier
npm test             # Vitest
```

Edit `ui/app.mcn`, not the generated screens: `mcn build` rewrites them, formatted with the project's Prettier once `npm install` has run. Your own tests go in other files, and MCN leaves them alone.

If the backend uses `auth` (see [security](#/guide/security)), the app sends a bearer token from `localStorage` key `mcn_token`, or `VITE_API_TOKEN`. After a login endpoint returns a token, store it with the generated helper:

```ts
import { setToken } from "./services/api"
setToken(result.token)   // setToken(null) to log out
```

## Mobile apps

Studio's **App** view compiles the same `ui/app.mcn` to a native Flutter app built from Material 3 widgets that adapt to the platform, with the web kit's Lucide icons and [fl_chart](https://pub.dev/packages/fl_chart) charts. It behaves like a native app:

- **Navigation:** a bottom navigation bar on phones (a drawer beyond five sections) and a navigation rail on tablets. Each section keeps its own page history and scroll position, so the Android back button, the iOS swipe-back gesture and tapping the current tab all work as expected.
- **Screens:** large titles that collapse as you scroll, and pull to refresh (it runs the screen's `on load` again).
- **Lists:** a search bar and filter chips. Tap a row to open its details on a new page; swipe left to delete, after a confirmation.
- **Boards:** `kanban` columns snap one per screen on phones. Tap a card to pick its new column, or long-press to drag it.
- **Details:** platform page transitions, switches and dialogs, snackbars, and haptic feedback.

Each `component` becomes a screen, the `app` block's `nav` items become a bottom navigation bar (a drawer when there are more than five), and state, `on_load` handlers and endpoint calls work as they do on the web. Tables become lists, and `kanban` cards move with a long press and drag.

Press **App Preview** in the App view to generate `mobile/` and run it in the phone frame. With [Flutter](https://docs.flutter.dev/get-started/install) installed, that's the real Flutter app, built for the web and talking to your backend (the first build takes about 30 seconds). Without Flutter, the frame shows the same components at phone size. **Export Flutter Package** downloads the Flutter project, the backend, `ui/app.mcn` and the files to deploy the backend, with a README for running it on Android and iOS.

`agent_builder` and `workflow_builder` are web-only; on mobile they show a note pointing to the web app. Projects without UI components still use `mobile/ui-manifest.json`, a JSON list of screens and widgets.

```bash
cd mobile
flutter create .                                              # first time: adds the android/ios/web folders
flutter pub get
flutter run --dart-define=MCN_API_URL=http://10.0.2.2:8080   # Android emulator; iOS and web use localhost
```

Screens live in `lib/screens/` (one file per component), shared widgets in `lib/mcn/mcn_runtime.dart`, and the API client in `lib/services/mcn_client.dart`. As on the web, state is typed from its starting value (`List<dynamic>`, `Map<String, dynamic>`, `String`, `num`, `bool`), each screen shows a loading bar and load errors with **Retry**, independent backend calls run together (`Future.wait`), and failed actions show an error snackbar. The project uses the standard [flutter_lints](https://pub.dev/packages/flutter_lints) rules, the generated code is formatted with `dart format`, and `test/screens_test.dart` has a smoke test for every screen (`flutter analyze`, `flutter test`). For a service with `auth`, add `--dart-define=MCN_API_TOKEN=...`, or set `MCNClient().token` after login. [Web and mobile](#/reference/ui-elements#web-and-mobile) lists how each element appears on a phone.
