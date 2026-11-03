# Packages

Packages add domain functions with one line. `use` loads a package's functions into your program.

```mcn
use "slack"
use "auth"

var user = create_user("ada@example.com", "s3cret-pass", {name: "Ada"})
post_message("#signups", "New user: " + user.email)
```

## Bundled packages

| Area | Packages |
|---|---|
| Payments and messaging | `stripe`, `payments`, `twilio`, `resend`, `slack`, `notifications` |
| Accounts and security | `auth`, `compliance` |
| Data | `analytics`, `report`, `storage`, `realtime`, `integrations`, `workflows` |
| AI | `ai`, `openai`, `ollama`, `rag`, `vector`, `memory`, `agent`, `mcp` |
| Industry | `healthcare`, `finance` |

```bash
mcn packages list              # every package
mcn packages info analytics    # its functions, with descriptions
```

> **Warning** Some industry functions are demos: `finance` KYC/AML checks and the `healthcare` drug-interaction checker return results marked `demo: true`. Connect a real provider before relying on them. Packages that call external services (Stripe, Twilio, Slack) need their API keys in environment variables and return results marked `mock: true` without them.

## Writing a package

```bash
mcn new-package myorg/retail --path .
```

This creates `myorg_retail/` with `mcn_package.json`, `index.mcn` for functions written in MCN, `index.py` for native extensions, and a README. Install it into a project and use it:

```bash
mcn install --path ./myorg_retail
```

```mcn fragment
use "myorg/retail"
var price = apply_discount(100, 0.1)
```

Local packages live in the project's `mcn_packages/` folder, so they travel with the project.
