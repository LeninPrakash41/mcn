# Deploying

An MCN app can go online in several ways, all in your own accounts:

| Where | Best for | Command |
|---|---|---|
| **Vercel** | A web app and its API at one URL, in a minute | `mcn deploy --target vercel` |
| **AWS App Runner** | An always-on app that scales by itself, in the AWS region you choose | `mcn deploy --target aws` |
| **Cloudflare** | The web app on Cloudflare's edge, the API in a Cloudflare container | `mcn deploy --target cloudflare` |
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

## AWS App Runner

```bash
mcn deploy --target aws --region eu-west-1 --name hr-portal
```

MCN builds one container with the web app (at `/`) and the API (at `/api`), pushes it to Amazon ECR in your account, and creates an App Runner service (or updates it on later deploys). App Runner gives it an HTTPS address, health checks and automatic scaling. The first deploy takes a few minutes.

You need the [AWS CLI](https://aws.amazon.com/cli/), signed in (`aws configure` or `aws sso login`), and [Docker](https://www.docker.com/products/docker-desktop/) running. The region comes from `--region`, else `AWS_REGION`, else `us-east-1`, which is where your app and its data live. MCN creates an IAM role named `MCNAppRunnerECRAccess` once, so App Runner can read the image.

## Cloudflare

```bash
mcn deploy --target cloudflare --name hr-portal
```

The web app is served as static files from Cloudflare's network, and requests to `/api/*` go to your backend running in a [Cloudflare container](https://developers.cloudflare.com/containers/). You need [Node.js](https://nodejs.org), Docker running (Wrangler builds the image with it), and a Cloudflare account: set `CLOUDFLARE_API_TOKEN`, or the first deploy opens a browser to log in. The address is `https://<name>.<your-subdomain>.workers.dev`.

**Settings for both.** The keys copied to Vercel deployments are copied here too, plus the `MCN_SSO_*` settings and `MCN_AUDIT_WEBHOOK`, and the same stable `MCN_AUTH_SECRET`. On AWS they're the service's environment variables; on Cloudflare they're Worker secrets that reach the container.

**Keep data in PostgreSQL.** Containers on App Runner and Cloudflare get a fresh disk when they restart, so SQLite data doesn't last. Put a PostgreSQL `DATABASE_URL` in `.env` (Amazon RDS, Neon, Supabase…); the deploy warns you when it's missing. Send the audit log to your SIEM with `MCN_AUDIT_WEBHOOK` for the same reason.

`--stage-only` writes the project (`Dockerfile`, and for Cloudflare `wrangler.jsonc` and the Worker) to `.mcn/deploy/<name>-<target>/` without deploying, to review it or deploy from CI.

## Docker and container hosts

```bash
mcn deploy --target docker --name my-app      # writes my-app.zip
```

The zip holds your `.mcn` files, a `Dockerfile`, `docker-compose.yml`, `start.sh`, `.env.example` and `DEPLOY.md` with steps for Railway, Render and Fly.io. Studio's **Build & download** gives you the same files plus the generated React app, an nginx config and a GitHub Actions workflow.

## Before you go live

Whichever host you use:

1. Add `auth "token"`, `"jwt"` or `"sso"` to services that change data, and `audit` where you need a record of who did what ([security](#/guide/security)).
2. Run `mcn audit .` and fix what it finds.
3. Keep API keys in `.env` or the host's settings, never in `.mcn` files.
