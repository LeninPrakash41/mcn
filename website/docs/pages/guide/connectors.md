# Connectors

Connectors let an app use the systems a business already has: spreadsheets, CRMs, databases and messaging. Each is one `use` line, and its functions return plain lists of maps, ready for a `data_table`, a chart or `query()`.

```mcn
use "sheets"
use "hubspot"
use "slack"

var leads = sheets_read("https://docs.google.com/spreadsheets/d/…", "Leads")
for lead in leads
    if lead.status == "Qualified"
        hubspot_create("contacts", {firstname: lead.name, email: lead.email})
post_message("#sales", str(len(leads)) + " leads synced from the sheet")
```

| `use` | Functions | Settings |
|---|---|---|
| `"sheets"` (Google Sheets) | `sheets_read(sheet, tab?)`, `sheets_append(sheet, row, tab?)`, `sheets_write(sheet, rows, tab?)` | None to read a sheet shared with *Anyone with the link*. `GOOGLE_SERVICE_ACCOUNT` (a service account's JSON, with the sheet shared to its email) to read private sheets and write; `mcn add sheets`. Or `GOOGLE_SHEETS_API_KEY` to read shared sheets through the API |
| `"files"` | `csv_read(path)`, `csv_write(path, rows)`, `excel_read(path, sheet?)`, `excel_write(path, rows, sheet?)` | None. Excel needs `mcn add excel` |
| `"sql"` | `sql_query(url, sql, params?)`, `sql_execute(url, sql, params?)` | A database URL: `postgres://…` (`mcn add postgres`), `mysql://…` (`mcn add mysql`) or `sqlite:///file.db`. Use `?` for values |
| `"hubspot"` | `hubspot_list(type, limit?)`, `hubspot_search(type, text)`, `hubspot_create(type, fields)`, `hubspot_update(type, id, fields)`; `type` is `"contacts"`, `"companies"`, `"deals"` or `"tickets"` | `HUBSPOT_TOKEN`: a private app's access token |
| `"salesforce"` | `salesforce_query(soql)`, `salesforce_create(object, fields)`, `salesforce_update(object, id, fields)` | `SALESFORCE_INSTANCE_URL` and `SALESFORCE_TOKEN` |
| `"airtable"` | `airtable_list(base, table)`, `airtable_create(base, table, fields)`, `airtable_update(base, table, id, fields)` | `AIRTABLE_TOKEN`: a personal access token |
| `"slack"` | `post_message(channel, text)` | `SLACK_WEBHOOK_URL` (one channel) or `SLACK_BOT_TOKEN` (any channel the bot is in) |
| `"whatsapp"` | `whatsapp_send(to, text)` | `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_ID` (Meta's Cloud API), or `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and `TWILIO_WHATSAPP_FROM` |

## Before you have the accounts

Without a connector's settings, reads return a few labelled sample rows and writes aren't sent, so the app runs in Studio, in class and in tests straight away. The first call prints one line saying what to set. Add the settings and the same code uses the real system.

## Settings

Settings are environment variables. In Studio, open the **Connect** tab: each connector shows whether it's connected, takes its settings (kept as workspace secrets, never in your code), has **Test** to try them, and **Insert into code** for an example. When you deploy, set the same variables on the server (`.env`, or your host's settings). On hosted Studio, connectors use sample data; set their settings in your deployment instead, so they aren't shared with other people.

## Errors

A real problem raises an error that says what to check: `401 from api.hubapi.com: Authentication credentials not found`, `there's no file 'orders.csv'`, `the database said: no such table: orders`. Catch it with `try` where your app should carry on.

```mcn
use "sql"

try
    var orders = sql_query(env("SHOP_DATABASE_URL"), "SELECT * FROM orders WHERE status = ?", ["open"])
catch e
    log("Couldn't read the shop database: " + e.message)
```
