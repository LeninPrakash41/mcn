# Security

MCN is safe by default where it can be, and gives you small, explicit tools for the rest. This page covers what the runtime does for you, how to protect a service, the check functions, and `mcn audit`.

## What MCN does for you

Every MCN service gets these without any code:

- **Only endpoints are reachable.** A request can call the endpoints you declared and nothing else. Built-ins like `query` or `write_file` are never exposed over HTTP.
- **Security headers** on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` and a strict `Content-Security-Policy`.
- **Rate limiting:** 600 requests a minute per client by default (`MCN_RATE_LIMIT`). Extra requests get status 429.
- **Body size limit:** 1 MB by default (`MCN_MAX_BODY_BYTES`). Larger bodies get status 413.
- **A secret per install.** Signed tokens (`auth_create_token`, `jwt_sign`) use `MCN_AUTH_SECRET`, or a random secret MCN creates once in `~/.mcn/auth_secret`. There's no built-in default secret anyone could copy.
- **Parameterized SQL.** `query` takes `?` placeholders, so values never become part of the SQL.

## Protect a service

Add an `auth` line to require a bearer token, and list the endpoints anyone may call with `public`:

```mcn
service orders_api
    auth "token"
    public health, list_products

    endpoint health()
        return {ok: true}

    endpoint list_products()
        return query("SELECT id, name, price FROM products")

    endpoint delete_order(id)
        query("DELETE FROM orders WHERE id = ?", (id,))
        return {success: true}
```

| `auth` | Callers send | The server checks |
|---|---|---|
| `"token"` | `Authorization: Bearer <token>` | That the token equals `MCN_API_TOKEN`. If `MCN_API_TOKEN` isn't set, protected endpoints are closed |
| `"jwt"` | `Authorization: Bearer <jwt>` | The signature and expiry, using the install's secret. Make tokens with `jwt_sign` or `auth_create_token` |

Requests without a valid token get status 401. Inside an endpoint, `current_user()` returns who called: the token's payload for `"jwt"`, `{token: true}` for `"token"`, and `null` on public endpoints.

```mcn
service notes_api
    auth "jwt"
    public login

    endpoint login(email, password)
        var user = query("SELECT id, password_hash FROM users WHERE email = ?", (email,))
        if len(user) == 0 or not auth_verify_password(password, user[0].password_hash)
            return {success: false, error: "Wrong email or password"}
        return {success: true, token: jwt_sign({user_id: user[0].id})}

    endpoint my_notes()
        var me = current_user()
        return query("SELECT id, text FROM notes WHERE user_id = ?", (me.user_id,))
```

The apps MCN builds send the token for you:

- **React** (`mcn build`): from `localStorage` key `mcn_token` (store it after login), or `VITE_API_TOKEN`.
- **Flutter**: `flutter run --dart-define=MCN_API_TOKEN=...`, or set `MCNClient().token` after login.
- **Studio's preview** starts your backend with a development token and passes it to the preview, so protected services work while you build.

## Check functions

| Function | What it does |
|---|---|
| `validate(data, rules)` | Check input against rules. Returns `{valid, errors}` with one message per field |
| `escape_html(text)` | Make text safe to put inside HTML |
| `sanitize_html(html)` | Keep basic formatting tags; remove scripts, event handlers and `javascript:` links |
| `is_email(text)` / `is_url(text)` | Whether text is an email address / an http(s) URL |
| `password_strength(password)` | `{score, ok, issues}` for a new password |
| `auth_hash_password(p)` / `auth_verify_password(p, hash)` | Store and check passwords (salted and slow on purpose) |
| `rate_limit(key, limit, seconds)` | `true` while `key` is under `limit` calls in the window, for example per user or per email |
| `require(condition, message)` | Stop the endpoint with `message` unless `condition` is true |
| `secure_token(length)` | A random token for invites, resets and API keys |
| `safe_equals(a, b)` | Compare secrets without leaking timing |
| `mask(text, visible)` | `"••••••7890"`, for showing or logging secrets |
| `audit_log(action, details, actor)` | Record who did what in a tamper-evident log |
| `verify_audit_log()` | `{valid, entries, broken_at}`: whether any entry was changed or removed |

`validate` rules are joined with `|`: `required`, `text`, `number`, `integer`, `boolean`, `email`, `url`, `min:N`, `max:N` (a number's value or a text's length), `in:a,b,c` and `pattern:REGEX`.

```mcn
function sign_up(form)
    var check = validate(form, {email: "required|email", password: "required|min:10", plan: "in:free,pro"})
    if not check.valid
        return {success: false, errors: check.errors}
    if not rate_limit("signup:" + form.email, 3, 3600)
        return {success: false, error: "Too many attempts. Try again later."}
    var strength = password_strength(form.password)
    require(strength.ok, "Choose a stronger password")
    query("INSERT INTO users (email, password_hash) VALUES (?, ?)", (form.email, auth_hash_password(form.password)))
    audit_log("sign_up", {email: form.email, plan: form.plan})
    return {success: true}
```

The audit log is a hash chain: each entry includes the hash of the one before, so editing or deleting a line breaks `verify_audit_log()` from that point. It's written to `~/.mcn/audit/app_audit.jsonl`, or `MCN_APP_AUDIT_LOG`.

## mcn audit

`mcn audit` reads your code and reports security problems before you ship. Nothing is run.

```bash
mcn audit                    # every .mcn file in this folder
mcn audit backend/main.mcn
mcn audit . --json           # for CI
mcn audit . --fail-on high   # only fail the build on high-severity findings
```

```text
HIGH    backend/main.mcn:12  sql-injection
        SQL for query() is built from values, so input can change the query.
        fix: Use ? placeholders and pass values separately: query("SELECT * FROM t WHERE id = ?", (id,)).
```

| Rule | Severity | Finds |
|---|---|---|
| `sql-injection` | high | SQL built with `+` or `{name}` instead of `?` placeholders |
| `hardcoded-secret` | high | API keys, passwords and tokens written in the source |
| `path-traversal` | high | File functions opening a path that comes from the request |
| `weak-password-hash` | high | `sha256`/`md5` on passwords |
| `open-service` | medium | A service without `auth` that has endpoints which change data |
| `request-forgery` | medium | `fetch` of a URL taken from the request |
| `secret-in-logs` | medium | Secrets passed to `log` or `print` |
| `exposed-user-rows` | medium | An endpoint returning `SELECT * FROM users` (password hashes included) |
| `insecure-http` | low | `http://` URLs other than localhost |

The command exits with code 1 when there's a finding at or above `--fail-on` (default `medium`), so you can add it to CI next to `mcn test` and `mcn check`.

## Before you go live

1. Set `MCN_AUTH_SECRET` to a long random value (`openssl rand -hex 32`) so tokens stay valid across servers and restarts.
2. Add `auth` to every service that changes data, and set `MCN_API_TOKEN` if you use `"token"`.
3. Set `MCN_CORS_ORIGINS` to your web app's address instead of allowing every origin.
4. Run `mcn audit .` and fix what it finds.
5. Serve over HTTPS. The zip from Studio's **Build & download** includes an nginx config to put in front of the API.

See [configuration](#/reference/configuration) for every setting.
