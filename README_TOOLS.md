# MCP tools reference

This document describes every tool exposed by the **Dependency Analysis** MCP server (`dependency_analysis_mcp.server`). Tools return JSON-serializable objects (typically `dict`).

For how to run the server and wire clients, see **[README_MCP.md](README_MCP.md)**. For deployment, see **[README_flyio.md](README_flyio.md)**. For the MCP Inspector, see **[README_Inspector.md](README_Inspector.md)**.

---

## Quick index

| Tool | Purpose |
|------|---------|
| [`find_package_github_repository`](#find_package_github_repository) | Resolve GitHub URL from npm / PyPI / NuGet metadata |
| [`check_package_release_sync`](#check_package_release_sync) | Compare registry latest vs GitHub release/tag |
| [`check_snyk_advisor_package`](#check_snyk_advisor_package) | Parse public Snyk package page (health, vuln wording) |
| [`check_recent_critical_vulnerabilities`](#check_recent_critical_vulnerabilities) | OSV: critical issues in the last 30 days |
| [`check_openssf_scorecard`](#check_openssf_scorecard) | OpenSSF Scorecard API for a GitHub repo |
| [`check_dependency_version_pinning`](#check_dependency_version_pinning) | Scan manifests for loose or missing version pins |
| [`create_dependency_analysis_summary`](#create_dependency_analysis_summary) | Single call combining sync, Snyk, Scorecard, OSV, OWASP |

**HTTP-only (not an MCP tool):** `GET /health` returns `{"status":"ok"}` when the server runs with Streamable HTTP (e.g. Fly.io).

---

## Shared concepts

### `package_type`

Used by several tools. Case-insensitive. Common values:

- **`npm`** — JavaScript / npm registry  
- **`pypi`** or **`pip`** — Python / PyPI (`pip` is normalized to `pypi`)  
- **`nuget`** — .NET / NuGet  

### `repository_url`

Must be a **github.com** repository URL (HTTPS or `git@github.com:...`) for tools that call GitHub or the OpenSSF Scorecard API (which is GitHub-oriented).

### Optional: `GITHUB_TOKEN`

If the server process has `GITHUB_TOKEN` set, GitHub REST calls (e.g. releases/tags) get higher rate limits. Never embed tokens in client configs committed to git.

---

## `find_package_github_repository`

**Purpose:** Read public registry metadata and extract a canonical **GitHub** repository URL when the package declares one.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `package_name` | `str` | Published name (e.g. `lodash`, `requests`, `Newtonsoft.Json`). |
| `package_type` | `str` | `npm`, `pypi` / `pip`, or `nuget`. |

**Returns (high level)**

- `github_repository_url`, `owner`, `repo` when found  
- `source_field` — where the URL was taken from (e.g. `npm.package.repository`, `pypi.info.project_urls[Source]`)  
- `note` — when no GitHub URL exists in metadata (common for some NuGet packages)  
- `nuget_catalog_version` — on NuGet, which catalog entry was used  

**Limits:** Only discovers links present in registry metadata; monorepos or renamed repos may not match expectations.

---

## `check_package_release_sync`

**Purpose:** Compare **latest version on the package manager** with **latest GitHub release tag** (or best-effort semver from tags if there is no `releases/latest`).

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `package_name` | `str` | Published package name. |
| `package_type` | `str` | `npm`, `pypi`, `nuget` (aliases: `pip` → `pypi`). |
| `repository_url` | `str` | GitHub repo URL for the project. |

**Returns (high level)**

- `registry_latest`, `github_tag_or_release`  
- `comparison.in_sync`, `comparison.uncertain_due_to_non_semver`, etc.  
- `details.registry`, `details.github` — raw-ish metadata from registry and GitHub APIs  

**Limits:** Compares **registry “latest”** to **GitHub tags/releases**, not necessarily the same artifact in monorepos; non-semver tags can make sync “uncertain”.

---

## `check_snyk_advisor_package`

**Purpose:** Fetch the public **security.snyk.io** HTML page for the package and extract visible signals (no Snyk API key).

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `package_name` | `str` | Registry name. |
| `package_type` | `str` | `npm`, `pypi` / `pip`, or `nuget` (mapped to Snyk URL segments). |

**Returns (high level)**

- `snyk_package_url`  
- `package_health_score` (e.g. `xx/100` when parsed)  
- `latest_version_reported`  
- `security_issues_flag`, `no_vulns_latest_wording_found`  
- `note` — HTML layout may change; fields can be incomplete  

**Limits:** Best-effort HTML parsing; not a supported Snyk JSON API.

---

## `check_recent_critical_vulnerabilities`

**Purpose:** Query **OSV** (`api.osv.dev`) for the package and list **critical**-severity activity in the **last 30 days**.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `package_name` | `str` | Published name. |
| `package_type` | `str` | `npm`, `pypi` / `pip`, or `nuget` (mapped to OSV ecosystems `npm`, `PyPI`, `NuGet`). |

**Returns (high level)**

- `critical_disclosures_in_window` — `published` in the window  
- `critical_incident_activity_in_window` — `modified` in the window but published earlier  
- Counts, capped lists (see `note` in response for CVSS / GitHub severity rules)  
- `source`, `window_start_utc`, `osv_vulnerabilities_returned`  

**Limits:** “Critical” uses GitHub advisory labels and/or CVSS v3/v4 thresholds; OSV coverage varies by ecosystem.

---

## `check_openssf_scorecard`

**Purpose:** GET published results from the **OpenSSF Scorecard** HTTP API for a GitHub repository.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `repository_url` | `str` | `https://github.com/org/repo` (github.com only). |

**Returns (high level)**

- `score`, `date`, `commit`, `checks_sample`, `checks_total`, `scorecard_api_url`  
- Or `error` (e.g. 404 if no published result)  

**Limits:** Only **github.com** repos supported by the public API path used by the server.

---

## `check_dependency_version_pinning`

**Purpose:** Walk the filesystem from **`search_root`** and report dependencies that are **not exactly pinned** or that use **ranges / wildcards / floating** constraints, across many manifest types.

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `search_root` | `str` | `"."` | Root directory; relative paths resolve from the **server process cwd**. |
| `max_depth` | `int` | `8` | Maximum recursion depth under `search_root`. |

**Returns (high level)**

- `search_root`, `manifest_paths_found`, `manifests_scanned`  
- `reports[]` — per file: `kind`, `issues[]` (name/specifier/reason/detail), optional `error` / `note`  
- `loose_or_unpinned_issue_count`  
- `summary.supported_manifests`, `summary.note` — ecosystem list and pinning philosophy  

**Limits:** Heuristic parsers (Gradle, Mix, SwiftPM, etc.); **Go** `go.mod` is mostly informational (MVS, not npm-style ranges). Skips `node_modules`, `.venv`, `vendor`, Rust `target/`, etc.

---

## `create_dependency_analysis_summary`

**Purpose:** One aggregated run: **release sync**, **Snyk page parse**, **OpenSSF Scorecard**, **OSV critical 30-day window**, and **OWASP dependency guidance** (cheat sheet fetch + Top 10 A06 link).

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `package_name` | `str` | Published package name. |
| `package_type` | `str` | `npm`, `pypi`, or `nuget`. |
| `repository_url` | `str` | GitHub URL (used for sync + Scorecard). |

**Returns (high level)**

- `markdown` — human-readable report sections  
- `release_sync` — same shape as `check_package_release_sync`  
- `snyk_advisor` — same shape as `check_snyk_advisor_package`  
- `openssf_scorecard` — same shape as `check_openssf_scorecard`  
- `recent_critical_security` — same shape as `check_recent_critical_vulnerabilities`  
- `owasp_dependency_guidance` — practices, URLs, optional live cheat sheet excerpt/outline  

**Limits:** Inherits limits of each sub-check; slower than individual tools because it runs them together.

---

## Suggested call order (example)

1. **`find_package_github_repository`** — if the GitHub URL is unknown.  
2. **`check_package_release_sync`** / **`check_openssf_scorecard`** / **`create_dependency_analysis_summary`** — pass the resolved `github_repository_url`.  
3. **`check_dependency_version_pinning`** — point `search_root` at the project tree you care about (absolute path on remote servers).

---

## Version

Tool set and behavior match the code in `dependency_analysis_mcp/server.py` for package **dependencyanalysismcp** (see `pyproject.toml` for the current version).
