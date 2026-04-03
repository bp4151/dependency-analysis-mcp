# Dependency Analysis MCP

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/{owner}/{repo}/badge)](https://scorecard.dev/viewer/?uri=github.com/{owner}/{repo})

A **[Model Context Protocol](https://modelcontextprotocol.io/)** server built with [FastMCP](https://github.com/PrefectHQ/fastmcp) that helps agents and developers **inspect open-source dependencies**: registry metadata, GitHub release alignment, public security signals, and version-pinning posture across many ecosystems.

**Python 3.11+** · Package name: `dependencyanalysismcp` (see `pyproject.toml`)

---

## What it does

The server exposes tools that (among other things):

- Resolve **GitHub** repository URLs from **npm**, **PyPI**, and **NuGet** registry metadata  
- Compare **registry “latest”** with **GitHub releases/tags**  
- Parse **public Snyk package advisor** pages (HTML; no Snyk API key)  
- Query **OSV** for **critical** vulnerability activity in a **30-day** window  
- Fetch **OpenSSF Scorecard** results for a GitHub repo  
- Scan a tree for **loose or unpinned** dependencies in common manifest formats  
- Produce a **single markdown summary** (sync + Snyk + Scorecard + OSV + OWASP-oriented pointers)

Analysis runs in **your** environment: the server calls public registries and APIs; it does **not** upload your local source code to a third party. You choose which paths to scan (for example with `check_dependency_version_pinning`).

---

## Quick start

```bash
pip install -e .
python -m dependency_analysis_mcp.server
```

With **`PORT` unset**, the process uses **stdio** (typical for Cursor, VS Code, and other MCP clients). With **`PORT` set**, it serves **Streamable HTTP** (for Fly.io, Docker, or other hosts) and exposes **`GET /health`**.

Console entry point (same as the module):

```bash
dependency-analysis-mcp
```

Optional: set **`GITHUB_TOKEN`** in the environment for higher GitHub API rate limits when resolving releases and tags. Do not commit tokens.

---

## Documentation

| Document | Contents |
|----------|----------|
| **[README_MCP.md](README_MCP.md)** | Local stdio setup, client JSON examples, HTTP/Fly client config, environment variables |
| **[README_TOOLS.md](README_TOOLS.md)** | Every MCP tool: parameters, return shapes, limits |
| **[README_flyio.md](README_flyio.md)** | Docker image, Fly.io deploy, secrets, operations |
| **[README_Inspector.md](README_Inspector.md)** | Debugging with MCP Inspector (stdio and HTTP) |
| **[README_GITHUB.md](README_GITHUB.md)** | GitHub and OpenSSF-oriented practices for open source repos |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | How to contribute: setup, PRs, docs, security reporting |
| **[SECURITY.md](SECURITY.md)** | How to report vulnerabilities privately (coordinated disclosure) |

---

## Repository layout

| Path | Role |
|------|------|
| `dependency_analysis_mcp/` | Server (`server.py`), services, pinning scanner |
| `Dockerfile`, `fly.toml`, `.dockerignore` | Container and Fly.io deployment |
| `pyproject.toml` | Package metadata and dependencies |

---

## Requirements

Install-time dependencies are listed in **`pyproject.toml`** (`fastmcp`, `httpx`, `packaging`, `cvss`, `pyyaml`, and their transitive deps).

For **remote HTTP** deployments, read **[README_flyio.md](README_flyio.md)** for security and networking considerations (public endpoints, authentication, and `search_root` behavior in containers).

---

## License

This project is licensed under the [MIT License](LICENSE).
