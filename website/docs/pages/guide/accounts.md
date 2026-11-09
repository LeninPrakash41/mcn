# Accounts and hosted Studio

Studio runs in two ways, and accounts work differently in each.

| | Installed Studio (`mcn studio`) | Hosted Studio (`mcn studio --hosted`) |
|---|---|---|
| Who uses it | One person, on their own Mac, Windows or Linux computer | Many people, in the browser, on a server you run |
| Accounts | None of its own. **Sign in** connects your MCN account | Everyone signs in or creates an account |
| Files | Stay on your computer | Each person gets their own workspace on the server |
| Admin | Nothing to manage | `/admin`: users, roles, signed-in computers |

One hosted Studio is also the **account server** for every installed copy: people sign in to it from their laptops, and its admin panel shows each user's signed-in computers.

## Installed Studio

Studio on your computer works fully without an account. Signing in is optional and connects it to your MCN account server:

1. Press **Sign In** in Studio's top bar, then **Sign in with your browser**.
2. A browser tab opens on the account server with a code such as `KXRT-49HM`. Sign in there and press **Allow**.
3. Studio shows your email. The terminal is signed in too.

The same flow works in a terminal:

```bash
mcn login          # shows a code and opens the browser
mcn whoami         # ana@example.com on https://studio.example.com
mcn logout         # signs this computer out, on the server too
```

The token is kept in `~/.mcn/credentials.json`, readable only by you, and never reaches the web page. It lasts 30 days. If an admin signs your computer out, Studio and `mcn whoami` notice the next time they check.

Set the account server once per computer:

```bash
mcn config set account_url https://studio.example.com
```

or with the `MCN_ACCOUNT_URL` environment variable. It must use `https://`; `http://localhost` is allowed for testing.

## Hosted Studio

Run Studio as a shared, multi-user server:

```bash
export MCN_STUDIO_MODE=hosted
export MCN_AUTH_SECRET="$(openssl rand -hex 32)"     # keep it the same across restarts
export MCN_ADMIN_EMAILS=you@example.com              # these accounts become admins
export MCN_PUBLIC_URL=https://studio.example.com     # the address people open
mcn studio --hosted --host 0.0.0.0 --port 5003
```

- Every page asks people to sign in or create an account. Each account gets its own workspace in `~/.mcn/workspaces/<user id>`.
- Accounts listed in `MCN_ADMIN_EMAILS` get the admin role when they register or sign in. Admins can make other users admins at `/admin`.
- `MCN_STUDIO_SIGNUP_DOMAINS=college.edu,company.com` limits who can create an account.
- `/device` is where people approve sign-ins from installed Studio and `mcn login`.

### Admin

`/admin` on hosted Studio lists every user with their role, when they joined, and the **computers signed in** to their account (for example *MCN on ana-mac (Darwin)*, last seen 5 min ago). **Sign out** next to a computer ends that session at once: its next request is refused, and the person has to sign in again.

Installed Studio has no `/admin`. It shows a page pointing to your account server instead.

### Running it safely

Hosted Studio runs the code people write on your server. Before you open it to others:

- **Run it in a container** (or a VM), with limits on CPU, memory and disk. Signed-in users can read files and environment variables the Studio process can read, so don't put secrets there that users shouldn't see.
- **Serve it over HTTPS**, behind a reverse proxy such as Caddy or nginx, and set `MCN_PUBLIC_URL` to that address.
- **Keep `~/.mcn` on a persistent volume.** It holds the account database (`auth.db`), the sign-in sessions and everyone's workspaces.
- **Back up `auth.db`** and keep `MCN_AUTH_SECRET` the same, or everyone is signed out.

Today one hosted Studio shares one dev server, backend preview and Flutter build between its users, so it suits a class or a small team that trusts each other. Per-user containers are planned.

## Settings

| Variable | Where | What it does |
|---|---|---|
| `MCN_STUDIO_MODE` | Server | `hosted` for a shared Studio. Anything else, or unset, is installed Studio |
| `MCN_AUTH_SECRET` | Server | Signs tokens. Set it, and keep it the same, on hosted Studio |
| `MCN_ADMIN_EMAILS` | Server | Comma-separated emails that become admins |
| `MCN_STUDIO_SIGNUP_DOMAINS` | Server | Comma-separated email domains allowed to sign up (default: anyone) |
| `MCN_PUBLIC_URL` | Server | The public address, used in sign-in links behind a proxy |
| `MCN_ACCOUNT_URL` | Computer | The account server for `mcn login` and Studio's Sign in (also `mcn config set account_url`) |
