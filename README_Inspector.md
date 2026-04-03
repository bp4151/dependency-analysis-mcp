# Testing with the MCP Inspector

This project’s server is implemented with [FastMCP](https://github.com/PrefectHQ/fastmcp). You can exercise it from the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) in two ways: **stdio** (Inspector spawns Python) or **Streamable HTTP** (Inspector connects to a URL, e.g. Docker or Fly.io).

## Requirements

| Component | Version / notes |
|-----------|------------------|
| **MCP Inspector** | Node.js **^22.7.5** (see [inspector README](https://github.com/modelcontextprotocol/inspector)) |
| **This server (stdio)** | Python **3.11+** with dependencies installed (`pip install -e .` or your venv) |
| **This server (HTTP)** | Process or container with `PORT` set (see [server `main()`](dependency_analysis_mcp/server.py)) |

Run the Inspector via:

```bash
npx @modelcontextprotocol/inspector
```

The UI defaults to **http://localhost:6274**; the proxy listens on **6277**. The console prints a **session token** and a link that includes `MCP_PROXY_AUTH_TOKEN`—use that link or paste the token under **Configuration → Proxy Session Token**.

---

## Option A: STDIO (local Python)

The server uses **stdio** when the **`PORT`** environment variable is **not** set.

1. Open a terminal at the **repository root** (where `dependency_analysis_mcp` is importable).
2. Activate your virtualenv if you use one.
3. Run:

```bash
npx @modelcontextprotocol/inspector python -m dependency_analysis_mcp.server
```

**Windows (same idea):**

```powershell
npx @modelcontextprotocol/inspector .\.venv\Scripts\python.exe -m dependency_analysis_mcp.server
```

**Optional environment variables** (GitHub API rate limits):

```bash
npx @modelcontextprotocol/inspector -e GITHUB_TOKEN=ghp_your_token_here -- python -m dependency_analysis_mcp.server
```

In the Inspector UI, choose transport **STDIO** if it is not already selected, connect, then open **Tools** and run the tools below.

**Deep link (after Inspector is running):** you can pre-fill stdio command/args (encode spaces in `serverArgs` as needed):

```
http://localhost:6274/?transport=stdio&serverCommand=python&serverArgs=-m%20dependency_analysis_mcp.server
```

---

## Option B: Streamable HTTP (Docker or local HTTP)

FastMCP exposes MCP on **`/mcp`** by default when using HTTP transports.

### 1. Start the HTTP server

**Docker:**

```bash
docker build -t dependency-analysis-mcp .
docker run --rm -p 8080:8080 -e PORT=8080 dependency-analysis-mcp
```

**Local Python:**

```bash
# Linux/macOS
PORT=8080 FASTMCP_HOST=0.0.0.0 python -m dependency_analysis_mcp.server

# Windows PowerShell
$env:PORT=8080; $env:FASTMCP_HOST="0.0.0.0"; python -m dependency_analysis_mcp.server
```

When `PORT` is set, the app binds **`0.0.0.0`** and uses **`streamable-http`** unless you override with `FASTMCP_TRANSPORT`.

**Sanity check:** `GET http://localhost:8080/health` should return `{"status":"ok"}`.

### 2. Connect from the Inspector

1. Open `http://localhost:6274` (use the tokenized URL from the console if prompted).
2. Set transport to **Streamable HTTP** (or **HTTP**, depending on Inspector wording).
3. **Server URL:** `http://localhost:8080/mcp`

**Deep link:**

```
http://localhost:6274/?transport=streamable-http&serverUrl=http://localhost:8080/mcp
```

### 3. Fly.io (or other HTTPS host)

Use your public URL with the same path:

```
https://<your-app>.fly.dev/mcp
```

Ensure the machine is running and the Fly proxy can reach your app. If the Inspector times out, increase the client timeout (next section).

---

## Inspector timeouts (important)

These tools call **npm**, **PyPI**, **NuGet**, **GitHub**, **security.snyk.io**, and **OpenSSF Scorecard** over the network. The default Inspector client timeout may be too low.

In the Inspector UI: **Configuration** → raise **MCP_SERVER_REQUEST_TIMEOUT** (milliseconds), e.g. **120000** (2 minutes) or higher for slow networks.

You can also open:

```
http://localhost:6274/?MCP_SERVER_REQUEST_TIMEOUT=120000
```

---

## Tools and example parameters

All `package_type` values are case-insensitive; supported values include **`npm`**, **`pypi`** / **`pip`**, and **`nuget`**.

### `find_package_github_repository`

| Parameter | Example | Notes |
|-----------|---------|--------|
| `package_name` | `lodash` | Published name on the registry |
| `package_type` | `npm` | `npm`, `pypi`, `nuget` |

### `check_package_release_sync`

| Parameter | Example | Notes |
|-----------|---------|--------|
| `package_name` | `lodash` | |
| `package_type` | `npm` | |
| `repository_url` | `https://github.com/lodash/lodash` | Must be **github.com** |

### `check_snyk_advisor_package`

| Parameter | Example | Notes |
|-----------|---------|--------|
| `package_name` | `requests` | |
| `package_type` | `pypi` | Snyk path uses `pip` internally |

### `check_openssf_scorecard`

| Parameter | Example | Notes |
|-----------|---------|--------|
| `repository_url` | `https://github.com/psf/requests` | **github.com** only |

### `check_dependency_version_pinning`

| Parameter | Example | Notes |
|-----------|---------|--------|
| `search_root` | `.` | Folder to walk; relative paths are from the **MCP server cwd** (often the workspace). Use an absolute path if needed. |
| `max_depth` | `8` | How deep to recurse below `search_root`. |

Scans **npm** (`package.json`), **Composer**, **Rust** (`Cargo.toml`, including `target.*` tables), **Ruby** (`Gemfile`), **Go** (`go.mod` — informational note; uses MVS, not npm-style ranges), **Maven** (`pom.xml`), **Gradle** (Groovy/Kotlin DSL coordinates), **NuGet** (`*.csproj`), **Dart/Flutter** (`pubspec.yaml`), **Conda** (`environment.yml` / `conda.yml`, including embedded `pip:` lists), **Elixir** (`mix.exs` heuristics), **SwiftPM** (`Package.swift` `from:` / branch hints), **Python** (`Pipfile`, `pyproject.toml` with Poetry groups / PDM / PEP 735 groups, `requirements*.txt`, `constraints.txt`). Skips `node_modules`, `.venv`, `vendor`, Rust `target/`, `Pods`, `.git`, etc.

### `check_recent_critical_vulnerabilities`

| Parameter | Example | Notes |
|-----------|---------|--------|
| `package_name` | `requests` | |
| `package_type` | `pypi` | Uses [OSV](https://osv.dev/) (`npm` / `PyPI` / `NuGet`); last **30 days** |

Returns **critical** advisories (GitHub **CRITICAL** label and/or high CVSS v3/v4 scores). Distinguishes **new disclosures** (`published` in window) from **incident-style activity** (`modified` in window, published earlier).

### `create_dependency_analysis_summary`

| Parameter | Example | Notes |
|-----------|---------|--------|
| `package_name` | `requests` | |
| `package_type` | `pypi` | |
| `repository_url` | `https://github.com/psf/requests` | Used for sync + Scorecard + same OSV critical check as above |

The summary JSON includes **`recent_critical_security`**, **`owasp_dependency_guidance`** (OWASP cheat sheet excerpt/outline + links), and the markdown adds **Critical security (OSV)** and **OWASP third-party dependency guidance** sections.

**Suggested end-to-end flow in the Inspector**

1. Call **`find_package_github_repository`** with `package_name` + `package_type`.
2. Copy `github_repository_url` from the result (if present).
3. Call **`check_package_release_sync`** and **`create_dependency_analysis_summary`** with that URL.

---

## Optional: CLI quick checks (no browser)

List tools (stdio):

```bash
npx @modelcontextprotocol/inspector --cli python -m dependency_analysis_mcp.server --method tools/list
```

Call a tool (stdio):

```bash
npx @modelcontextprotocol/inspector --cli python -m dependency_analysis_mcp.server ^
  --method tools/call ^
  --tool-name find_package_github_repository ^
  --tool-arg package_name=lodash ^
  --tool-arg package_type=npm
```

Streamable HTTP (URL must include the MCP path; `--transport http` matches Inspector CLI for streamable HTTP):

```bash
npx @modelcontextprotocol/inspector --cli http://localhost:8080/mcp --transport http --method tools/list
```

(On Unix shells, use `\` line continuations instead of `^`.)

---

## Security notes

- Treat the Inspector **proxy** as **local-only**: do not expose ports **6274** / **6277** to untrusted networks.
- Keep **Inspector packages updated**; older versions had serious auth bypass issues (e.g. CVE-2025-49596). Do not set `DANGEROUSLY_OMIT_AUTH` unless you fully understand the risk.

---

## Reference links

- [MCP Inspector repository](https://github.com/modelcontextprotocol/inspector)
- [MCP Inspector docs](https://modelcontextprotocol.io/docs/tools/inspector)
- [FastMCP HTTP / deployment](https://gofastmcp.com/)
