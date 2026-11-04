# Deploying

An MCN app can go online three ways:

| Where | Best for | Command |
|---|---|---|
| **Vercel** | A web app and its API at one URL, in a minute | `mcn deploy --target vercel` |
| **Any container host** (Railway, Render, Fly.io, a VPS) | Long-running APIs, schedules, lasting SQLite data | `mcn deploy --target docker` |
| **A Raspberry Pi** | Apps that read sensors and drive hardware | `mcn iot service` ([IoT and hardware](#/guide/iot)) |

## Vercel

From a project with `backend/main.mcn` (with a `service`) and `ui/app.mcn`:

```bash
mcn deploy --target vercel            # a preview URL
mcn deploy --target vercel --prod     # your production URL
```

MCN compiles the UI to a React app, and Vercel serves it with your backend running at `/api` on the same address. The first time, the Vercel CLI asks you to log in and creates a project named after `--name` (default `mcn-app`); later deploys update the same project. You need [Node.js](https://nodejs.org) for the Vercel CLI; MCN runs it for you.

In Studio, open **Build → Deploy (Vercel, Docker)…**, choose **Vercel** and press **Deploy to Vercel**. Studio needs a Vercel token: create one at vercel.com/account/tokens and add it as `VERCEL_TOKEN` under **Secrets**. When the deployment finishes, the dialog shows the live link.

**Settings.** These keys are copied from the project's `.env` file to the deployment: `ANTHROPIC_API_KEY`, `MCN_AI_MODEL`, `MCN_API_TOKEN`, `MCN_CORS_ORIGINS`, `MCN_RATE_LIMIT`, `OPENAI_API_KEY`, `DATABASE_URL` and the `MCN_MQTT_*` settings. MCN also creates an `MCN_AUTH_SECRET` for the project, kept in `.mcn/deploy/auth_secret` and reused every deploy, so signed tokens stay valid.

**What changes on Vercel.** Vercel runs your backend on demand instead of as a server that's always on:

- SQLite data is **temporary**: it lives as long as one server instance. Seed data is recreated on start, but anything users add can disappear. For data that must last, use PostgreSQL, for example Vercel Postgres, Neon or Supabase: put its connection URL in `.env` as `DATABASE_URL` and connect at the top of the backend:

  ```mcn fragment
  if env("DATABASE_URL")
      connect_postgresql(env("DATABASE_URL"))
  ```

  `?` placeholders work the same, but table definitions must be PostgreSQL SQL (`id SERIAL PRIMARY KEY` instead of `INTEGER PRIMARY KEY AUTOINCREMENT`). See [database](#/guide/database).
- `device("watch", ...)`, `schedule` blocks and background `task`s stop when a request ends. Use a container host or a Pi for those.
- Devices are always simulated: there's no hardware on Vercel.
- Each request can take up to 30 seconds.

**Other ways to ship it.** `mcn deploy --target vercel --stage-only` writes the Vercel project to `.mcn/deploy/<name>/` without uploading it. Push that folder to a Git repository connected to Vercel, or run `vercel deploy` there yourself.

## Docker and container hosts

```bash
mcn deploy --target docker --name my-app      # writes my-app.zip
```

The zip holds your `.mcn` files, a `Dockerfile`, `docker-compose.yml`, `start.sh`, `.env.example` and `DEPLOY.md` with steps for Railway, Render and Fly.io. Studio's **Build & download** gives you the same files plus the generated React app, an nginx config and a GitHub Actions workflow.

## Before you go live

Whichever host you use:

1. Add `auth "token"` or `auth "jwt"` to services that change data ([security](#/guide/security)).
2. Run `mcn audit .` and fix what it finds.
3. Keep API keys in `.env` or the host's settings, never in `.mcn` files.
