# Sales CRM — a full-stack MCN app

Leads, companies and follow-ups with search, filters, sorting, pagination,
create / edit / delete with validation, and a live dashboard.
**Under 200 lines of MCN in 4 files** (blank lines and comments included), with no hand-written React, SQL schema or API code.

![Dashboard](screenshots/dashboard.png)

| File | What it does |
|---|---|
| `models.mcn` | The data model: three `contract`s, shared by backend and UI |
| `backend.mcn` | `crud` for each contract + a custom `get_dashboard` endpoint |
| `seed.mcn` | Sample data, inserted only when the database is empty |
| `app.mcn` | Dashboard screen, three `crud_table` screens and the app shell |

## Run it

```bash
cd examples/crm_app
mcn serve --file backend.mcn --port 8080
```

In a second terminal:

```bash
cd examples/crm_app
mcn build app.mcn --out frontend
cd frontend
npm install
npx shadcn@latest add badge button card dialog input label select switch table textarea
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173).

## How it works

A contract describes the data once:

```mcn
contract Lead
    name:   str
    email:  str unique
    stage:  choice("new", "contacted", "qualified", "won", "lost") = "new"
    value:  float = 0
    notes:  text?
```

`crud Lead` in the backend creates the `leads` table and five endpoints:
`list_leads` (search, filters, sort, pages), `get_lead`, `create_lead`,
`update_lead` and `delete_lead`. Input is validated against the contract,
and errors come back per field.

`crud_table Lead` in the UI turns into a complete screen: table, search, a
stage filter, sortable columns, pagination, an add/edit form built from the
contract (dropdowns for choices, a toggle for booleans, a date picker for
dates), and a delete confirmation.

Add a field to a contract and restart. The column is added to the table and
appears in the form; existing data is kept.

| Leads | Form with validation |
|---|---|
| ![Leads](screenshots/leads.png) | ![Form](screenshots/lead-form.png) |
