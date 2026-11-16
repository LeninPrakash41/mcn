# Your first business tool

From an idea to a working tool your team can open in a browser, in about 15 minutes once MCN is installed. The example is an order tracker on top of a Google Sheet the team already keeps; swap in your own spreadsheet, CRM or database.

## 1. Open Studio

```bash
mcn studio
```

## 2. Describe the tool, or start from a template

Open the **Agent** tab, choose **New app**, and describe what you need in plain words:

> An order tracker for our sales team. Orders come from our Google Sheet (customer, product, amount, status). Show open orders, totals by status, and let people mark an order shipped.

The agent team plans the app, writes the backend and screens, and tests them. Or start from a template that's close (**Templates → Customer CRM**, **Inventory & Item Manager**, **Operations Dashboard**) and change it with the Agent's **Change** mode.

## 3. Connect your data

Open the **Connect** tab, pick **Google Sheets** (or HubSpot, Salesforce, Airtable, a SQL database), add its settings and press **Test**. Until you do, the app runs on sample data, so nothing blocks you. In code it's one line:

```mcn
use "sheets"

var ORDERS = "https://docs.google.com/spreadsheets/d/your-sheet-id"

service orders_api
    endpoint list_orders()
        return {success: true, data: sheets_read(ORDERS, "Orders")}

    endpoint add_order(customer: str, product: str, amount: float)
        sheets_append(ORDERS, {customer: customer, product: product, amount: amount, status: "Open"}, "Orders")
        return {success: true}
```

See [connectors](#/guide/connectors) for every system and its settings.

## 4. Make it yours

The **Design** button above the Preview sets your brand colour, font, corners and buttons; each choice becomes one line in `ui/app.mcn`. Press **Preview** to use the real app, then **Mobile** to see the phone version.

## 5. Check it

Press **Verify** (or run `mcn check`), and run the tests the agent wrote with `mcn test backend/main.mcn`. `mcn audit` looks for security problems before anyone else uses it.

## 6. Share it

**Build → Deploy** puts the web app and its API on Vercel and gives you a link (or `mcn deploy --target vercel`); `--target aws` and `--target cloudflare` run it in your own AWS or Cloudflare account. Add the same connector settings to the deployment's environment. Before people outside your team use it, protect the service with `auth "token"` or company sign-in (`auth "sso"`), as in [security](#/guide/security).

## What you end up with

Two readable files you own (`backend/main.mcn` and `ui/app.mcn`), a web app, a phone app, and an API, running in your cloud. No seats, and no platform between you and your tool.
