# Services and APIs

A `service` turns functions into an HTTP API. Each `endpoint` is a normal function you can call from MCN, and a route that browsers, apps and other services can call.

```mcn
query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT)")

service users_api
    port 8080

    endpoint create_user(name, email)
        if not name or not contains(email, "@")
            return {success: false, error: "A name and a valid email are required"}
        query("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
        return {success: true, id: query("SELECT last_insert_rowid() AS id")[0].id}

    endpoint get_user(id)
        var rows = query("SELECT * FROM users WHERE id = ?", (id,))
        if len(rows) == 0
            return {success: false, error: "Not found"}
        return {success: true, data: rows[0]}

    endpoint list_users(limit = 50, offset = 0)
        return {success: true, data: query("SELECT * FROM users LIMIT ? OFFSET ?", (limit, offset))}
```

## Serve it

```bash
mcn serve backend/main.mcn
```

```output
MCN API running on http://localhost:8080
  GET/POST /create_user  (name, email)
  GET/POST /get_user  (id)
  GET/POST /list_users  (limit, offset)
Interactive docs: http://localhost:8080/docs
```

The port comes from the service's `port` line (8080 if there isn't one); `--port` overrides it. The server listens on `127.0.0.1` (this machine) unless you pass `--host 0.0.0.0`.

## Calling endpoints

Every endpoint answers both **POST** with a JSON body and **GET** with a query string:

```bash
curl -X POST localhost:8080/create_user -H 'Content-Type: application/json' \
     -d '{"name": "Ada", "email": "ada@example.com"}'
curl "localhost:8080/list_users?limit=10"      # numbers in the query string become numbers
curl localhost:8080/get_user/1                 # a path segment fills the first parameter
curl localhost:8080/                           # lists every endpoint
```

- Arguments are matched to parameters **by name**. Missing ones use the parameter's default.
- The return value is sent as JSON. Returning nothing sends `{}`.
- An error inside an endpoint returns status 500 with `{"error": "<message>"}`.
- Cross-origin requests are allowed, so a web app on another port can call the API. Set `MCN_CORS_ORIGINS` to limit which sites may call it.
- Only declared endpoints are reachable, every response carries security headers, and requests are rate-limited. See [security](#/guide/security).

> **Tip** Return a consistent shape, like `{success: true, data: ...}` or `{success: false, error: "..."}`. The UI and your tests can then check `.success` everywhere.

## Calling endpoints from MCN

Inside the same file, endpoints are ordinary functions, which is what makes them easy to test:

```mcn fragment
test "creating a user needs an email"
    assert create_user("Ada", "not-an-email").success == false
```

From a UI file (`ui/app.mcn`), calling an endpoint by name compiles to an HTTP request. See [user interfaces](#/guide/ui).

## Several files

```bash
mcn serve endpoints/       # serves the endpoints of every .mcn file in the folder
```

## Postman

`mcn serve file.mcn --postman` also writes a Postman collection and environment to `postman_exports/`. The `generate_postman(folder)` built-in does the same from code.

## Deploying

`mcn deploy --target vercel` puts the API and its web app online at one URL; [deploying](#/guide/deploy) covers Vercel, containers and a Raspberry Pi. Studio's **Build & download** gives you a zip with a `Dockerfile`, `docker-compose.yml`, an nginx config and a GitHub Actions workflow. To run the API in a container yourself:

```bash
mcn serve backend/main.mcn --host 0.0.0.0 --port 8080
```

## Authentication

Endpoints are open unless the service has an `auth` line. Add one before exposing an API to the internet:

```mcn fragment
service users_api
    auth "token"            // or "jwt"
    public list_users       // endpoints anyone may call
```

Callers then send `Authorization: Bearer <token>`. [Security](#/guide/security) explains both modes, `current_user()`, and `mcn audit`, which finds open services and other problems.
