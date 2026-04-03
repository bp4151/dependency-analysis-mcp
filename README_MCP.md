# MCP server configuration

This repository exposes a **Dependency Analysis** MCP server built with [FastMCP](https://github.com/PrefectHQ/fastmcp). The same process can run in two modes:

| Mode | Transport | Typical use |
|------|-----------|-------------|
| **Local** | **stdio** | Cursor, VS Code, Claude Desktop, CLI tools that spawn a subprocess |
| **Fly.io** (or any host) | **Streamable HTTP** | Remote URL (`https://…/mcp`) |

The server chooses the mode from the environment: if **`PORT`** is set (as on Fly.io), it listens for HTTP; otherwise it uses **stdio**.

---

## Prerequisites

- **Python 3.11+**
- Dependencies from this repo:

  ```bash
  pip install -e .
  ```

  Or use a virtual environment and point your MCP config at that interpreter’s `python`.

Optional:

- **`GITHUB_TOKEN`** — higher GitHub API rate limits for release/tag lookups (do not commit the token).

---

## Running and configuring locally (stdio)

### 1. Run from a shell (smoke test)

From the repository root, with the venv activated:

```bash
python -m dependency_analysis_mcp.server
```

With no `PORT` set, the process waits on **stdin/stdout** for MCP messages (you will not see an HTTP port). This is normal for IDE integration.

### 2. Cursor / VS Code MCP settings

Add a server entry that runs the module with your Python. Paths must match **your** machine.

**macOS / Linux** (example venv):

```json
{
  "mcpServers": {
    "dependency-analysis": {
      "command": "/path/to/DependencyAnalysisMcp/.venv/bin/python",
      "args": ["-m", "dependency_analysis_mcp.server"],
      "env": {
        "GITHUB_TOKEN": ""
      }
    }
  }
}
```

**Windows** (example):

```json
{
  "mcpServers": {
    "dependency-analysis": {
      "command": "C:\\Users\\YOU\\PycharmProjects\\DependencyAnalysisMcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "dependency_analysis_mcp.server"],
      "env": {}
    }
  }
}
```

Set `GITHUB_TOKEN` in `env` if you use a token; omit the key or leave it empty if not.

**Working directory:** Many clients run the command with cwd = workspace root. That matters for **`check_dependency_version_pinning`** (default `search_root` is `.` resolved from the server process cwd). If pinning should target another tree, pass an absolute `search_root` in the tool call.

### 3. Optional: local HTTP (Streamable HTTP)

Useful for the [MCP Inspector](README_Inspector.md) or clients that speak HTTP MCP:

```bash
# PowerShell
$env:PORT = "8080"
$env:FASTMCP_HOST = "0.0.0.0"
python -m dependency_analysis_mcp.server

# bash
PORT=8080 FASTMCP_HOST=0.0.0.0 python -m dependency_analysis_mcp.server
```

MCP endpoint: **`http://localhost:8080/mcp`**  
Health: **`http://localhost:8080/health`**

---

## Connecting to the server on Fly.io (Streamable HTTP)

After you deploy (see **[README_flyio.md](README_flyio.md)**), the public MCP URL is:

```text
https://<your-app-name>.fly.dev/mcp
```

Replace `<your-app-name>` with the `app` value in `fly.toml` (e.g. `dependency-analysis-mcp`).

Health check:

```text
https://<your-app-name>.fly.dev/health
```

### Client configuration (streamable HTTP)

MCP clients that support **Streamable HTTP** should use a URL-style entry. The exact JSON shape depends on the client; a common pattern (also used by the Inspector export) is:

```json
{
  "mcpServers": {
    "dependency-analysis-fly": {
      "type": "streamable-http",
      "url": "https://<your-app-name>.fly.dev/mcp"
    }
  }
}
```

If your client uses a different key (`transport`, `serverUrl`, etc.), map the same URL and choose the HTTP / streamable transport your client documents.

### Security and operations

- The default Fly setup exposes the MCP endpoint on the **public internet** unless you add **authentication**, **private networking**, or a reverse proxy. Treat deployment as sensitive if tools can trigger outbound calls or read paths you pass in.
- **`check_dependency_version_pinning`** on Fly uses the **container cwd** (usually `/app`). Pass an absolute **`search_root`** only if you mount or copy project files into the image and need a specific path.
- For deploy, scaling, secrets (`GITHUB_TOKEN`), and troubleshooting, use **[README_flyio.md](README_flyio.md)**.

---

## Environment variables (reference)

| Variable | Effect |
|----------|--------|
| `PORT` | If set, enables **Streamable HTTP** on `FASTMCP_HOST`:`PORT` (default transport `streamable-http`). |
| `FASTMCP_HOST` | Bind address (Fly/Docker: `0.0.0.0`). |
| `FASTMCP_TRANSPORT` | Override HTTP mode: `streamable-http`, `http`, or `sse` (never `stdio` when `PORT` is set). |
| `GITHUB_TOKEN` | Optional Bearer token for GitHub REST API (rate limits). |
| `FASTMCP_STATELESS_HTTP` | `true` can help with multiple Fly Machines (see `fly.toml` comments). |

---

## Related docs

- **[README_TOOLS.md](README_TOOLS.md)** — full list of MCP tools, parameters, and return shapes  
- **[README_flyio.md](README_flyio.md)** — build, deploy, health checks, secrets  
- **[README_Inspector.md](README_Inspector.md)** — debugging with MCP Inspector (stdio and HTTP)  
- **Entrypoint:** `python -m dependency_analysis_mcp.server` or console script `dependency-analysis-mcp`
