# Security and trust

A one-page summary for IT and security teams reviewing an app built with MCN. Each point links to the details.

## Ownership

- **MIT licensed and open source.** There's no vendor account an MCN app depends on.
- **The app is code you keep:** `backend/main.mcn` and `ui/app.mcn` in your repository, reviewable like any other code. `mcn build` produces standard React and Flutter projects your engineers can take over.

## Where it runs and where data goes

- **In your infrastructure:** your Vercel, AWS or Cloudflare account, any Docker host, or a Raspberry Pi. MCN doesn't operate a service that apps run on.
- **No data leaves on its own.** AI calls happen only when an AI key is set, and send only the prompts the code builds. Connectors (Google Sheets, HubSpot, Salesforce, Slack, ...) send data only with the credentials you give them. Studio's feedback reports stay on the computer unless `MCN_FEEDBACK_ENDPOINT` is set.
- **Credentials are settings,** read from the environment, never written in the code. `mcn audit` flags hard-coded secrets.

## Access

- Services can require a token (`auth "token"`), signed tokens (`auth "jwt"`) or company single sign-on with any OpenID Connect provider such as Okta, Microsoft Entra ID or Google Workspace (`auth "sso"`), with roles available to every endpoint through `current_user()`. See [security](#/guide/security).
- Hosted Studio has accounts, admins and sign-up limits by email domain ([accounts](#/guide/accounts)).

## Safe by default

Every service, without extra code: only declared endpoints are reachable, security headers on every response, rate limiting, a body size limit, a per-install signing secret, and parameterized SQL (`?` placeholders).

## Accountability

- `audit` services record every call in a tamper-evident log, with secrets masked. `mcn audit-log verify` checks it hasn't been changed, and `mcn audit-log export --format ocsf` sends it to your SIEM.
- For physical devices, [control policies](#/guide/iot) limit what each device may do, require a person's approval where needed, and record refusals; `emergency_stop()` makes every output safe.

## Review and CI

| Check | Command |
|---|---|
| Security problems (SQL injection, hard-coded secrets, open services) | `mcn audit --fail-on high` |
| Types and undefined names | `mcn check --strict` |
| The app's own tests | `mcn test` |
| Formatting | `mcn fmt --check` |
| Generated web app | `npm run typecheck`, `npm run lint`, `npm test` in the React project |
| Generated phone app | `flutter analyze`, `flutter test` |

## What MCN isn't

- **Not a certified service.** SOC 2, HIPAA and similar certifications belong to whoever runs the app and its infrastructure; MCN gives you the controls (sign-in, roles, audit logs, data in your own region) to meet them.
- **Hosted Studio is for teams that trust each other.** It runs the code people write on one server and shares a preview server between its users; run it in a container, and keep company secrets out of its environment. Per-user sandboxes are planned. Installed Studio runs only on the developer's computer.

## Common questions

| Question | Answer |
|---|---|
| Can we self-host everything? | Yes. The apps, and Studio itself (`mcn studio --hosted`), run on your servers |
| Where is our data stored? | In the database you choose: SQLite by default, PostgreSQL with `DATABASE_URL`, in your account and region |
| Does MCN see our code or data? | No. Nothing is sent to MCN; AI providers and connectors receive data only when you configure them |
| Can we use our identity provider? | Yes, any OpenID Connect provider, with domains limited by `MCN_SSO_ALLOWED_DOMAINS` |
| Can we keep an audit trail? | Yes: `audit` services, verifiable and exportable as OCSF |
| What if MCN stops being maintained? | The code is MIT licensed and readable, and the generated React and Flutter projects stand on their own |
