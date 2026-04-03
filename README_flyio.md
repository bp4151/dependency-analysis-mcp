# Deploying to Fly.io

This app ships as a **Docker** image (Chainguard Python, multi-stage build). On Fly it runs the MCP server over **Streamable HTTP** on port **8080**, with a **`GET /health`** endpoint for Fly Proxy health checks.

## Prerequisites

- A [Fly.io](https://fly.io) account and billing set up as required by Fly.
- [flyctl](https://fly.io/docs/hands-on/install-flyctl/) installed and logged in:

  ```bash
  fly auth login
  ```

- Docker available locally (Fly can also build remotely; `fly deploy` uses the `Dockerfile` by default).

## First-time setup

1. **Clone or copy** this repository and open a shell at the project root (where `fly.toml` and `Dockerfile` live).

2. **Pick a unique app name.** The placeholder in `fly.toml` is `dependency-analysis-mcp`. If that name is taken globally, change it:

   ```toml
   app = "your-unique-app-name"
   ```

3. **Create the app on Fly** (if you do not already have one):

   ```bash
   fly apps create your-unique-app-name
   ```

   Alternatively, run **`fly launch`** once and align the generated `fly.toml` with this repo (or merge settings). Using the existing `fly.toml` you can deploy with:

   ```bash
   fly deploy
   ```

   If Fly warns about an existing `fly.toml`, follow the prompts or use `fly deploy --no-launch` / confirm you want to use the current file.

4. **Region** is set in `fly.toml` as `primary_region = "iad"`. Change it if you want a different [region](https://fly.io/docs/reference/regions/).

## Deploy

From the repository root:

```bash
fly deploy
```

Fly builds the image from **`Dockerfile`** (see `[build]` in `fly.toml`) and rolls out a new release.

### What Fly configures for you

| Setting | Purpose |
|--------|---------|
| **`PORT`** | Injected by Fly at runtime. The Python entrypoint detects `PORT` and starts **streamable-http** on **`0.0.0.0`**. |
| **`internal_port = 8080`** | Must match the port the process listens on (same as the image default when `PORT` is 8080). |
| **`[[http_service.checks]]`** | `GET /health` must return **2xx**; used by the proxy before sending traffic. |
| **`force_https = true`** | Public URLs use HTTPS. |

Do **not** unset `PORT` in production; without it the server would try to use **stdio**, which is wrong for Fly’s HTTP routing.

## After deploy

- **App URL:** `https://<app-name>.fly.dev`
- **MCP (Streamable HTTP) endpoint for clients:**  
  **`https://<app-name>.fly.dev/mcp`**  
  (FastMCP default path; override with `FASTMCP_STREAMABLE_HTTP_PATH` only if you change it in code/settings.)

- **Health check (browser or curl):**  
  `https://<app-name>.fly.dev/health` → `{"status":"ok"}`

### Useful commands

```bash
fly status
fly logs
fly machines list
fly scale count 1
```

## Secrets and environment variables

### Optional: GitHub API token

For higher **GitHub API** rate limits (release/tag lookups), set a token as a secret (never commit it):

```bash
fly secrets set GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

Redeploy is not always required; Fly injects secrets into new machine env. Confirm with `fly secrets list` (values are not shown).

### Stateless HTTP (multiple machines)

If you run **more than one** machine and want each request to be independent (recommended for streamable HTTP at scale), set in `fly.toml` under `[env]`:

```toml
FASTMCP_STATELESS_HTTP = "true"
```

Then deploy again. See comments in `fly.toml` for the exact line.

### Other FastMCP env vars (optional)

All use the `FASTMCP_` prefix (see [FastMCP settings](https://github.com/PrefectHQ/fastmcp)). Examples:

- `FASTMCP_TRANSPORT` — default on Fly is **streamable-http** when `PORT` is set; override only if you know the implications.
- `FASTMCP_LOG_LEVEL` — e.g. `DEBUG` for troubleshooting.

Set via `[env]` in `fly.toml` or `fly secrets set` / `fly config env` depending on sensitivity.

## Connecting MCP clients

Point your MCP client at **Streamable HTTP** with URL:

```text
https://<app-name>.fly.dev/mcp
```

Use the same URL in the [MCP Inspector](README_Inspector.md) when testing over HTTP.

**Security:** This exposes your MCP server on the public internet unless you add **authentication** (FastMCP supports auth providers; you must configure them yourself). Consider Fly’s [private networking](https://fly.io/docs/networking/private-networking/), IP allowlists, or putting an authenticated reverse proxy in front if the server is sensitive.

## Troubleshooting

| Symptom | Things to check |
|--------|------------------|
| **502 / no healthy machine** | `fly logs`; ensure **`GET /health`** returns 200 inside the VM (`fly ssh console` then you cannot easily curl without shell—check logs for bind errors). Confirm **`internal_port`** matches **`PORT`**. |
| **Cold starts** | `min_machines_running = 0` allows scale-to-zero; first request may be slow. Set `min_machines_running = 1` in `fly.toml` if you need always-on. |
| **Health check failures** | Increase `grace_period` under `[[http_service.checks]]` if the image is slow to boot. |
| **MCP client cannot connect** | URL must include **`/mcp`**, use **HTTPS**, and ensure the client supports **streamable HTTP**. |

## Files involved

- **`Dockerfile`** — Chainguard multi-stage build; runtime runs `python -m dependency_analysis_mcp.server`.
- **`fly.toml`** — App name, region, `http_service`, health check, VM size.
- **`dependency_analysis_mcp/server.py`** — Chooses **stdio** vs **HTTP** based on **`PORT`**.

## Further reading

- [Fly.io App configuration (`fly.toml`)](https://fly.io/docs/reference/configuration/)
- [Fly.io Health checks](https://fly.io/docs/reference/health-checks/)
- [FastMCP deployment / HTTP](https://gofastmcp.com/)
