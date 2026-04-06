"""FastMCP server: release sync, Snyk public package pages, OpenSSF Scorecard, combined summary."""

from __future__ import annotations

import asyncio
import os

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from dependency_analysis_mcp.pinning_scan import scan_dependency_pinning
from dependency_analysis_mcp.services import (
    DEFAULT_TIMEOUT,
    USER_AGENT,
    check_release_sync,
    dependency_health_summary,
    fetch_openssf_scorecard,
    fetch_snyk_advisor_page,
    recent_critical_vulnerabilities_and_incidents,
    resolve_package_github_repository,
)

mcp = FastMCP(
    "Dependency Analysis",
    instructions=(
        "Tools compare package registry versions to GitHub releases, read Snyk Advisor-style "
        "signals from public security.snyk.io pages, query the OpenSSF Scorecard API, "
        "check OSV for critical vulnerabilities and recent advisory activity (30-day window), "
        "attach OWASP third-party dependency guidance (Vulnerable Dependency Management, NPM Security) "
        "and Top 10 links in the summary, "
        "resolve GitHub URLs from package metadata, scan local manifests for loose/unpinned "
        "dependencies, and merge results into a short summary."
    ),
)

_READ_ONLY_OPEN_WORLD = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
_READ_ONLY_LOCAL = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


@mcp.custom_route("/health", methods=["GET"])
async def _health(_request: Request) -> JSONResponse:
    """Liveness probe for Fly.io and other load balancers."""
    return JSONResponse({"status": "ok"})


@mcp.tool(annotations=_READ_ONLY_OPEN_WORLD)
async def find_package_github_repository(
    package_name: str,
    package_type: str,
) -> dict:
    """
    Look up the GitHub repository URL declared for a package on npm, PyPI, or NuGet.

    The returned ``github_repository_url`` can be passed to ``check_package_release_sync``
    and ``check_openssf_scorecard`` when the user does not already know the repo link.

    Args:
        package_name: Published package name (e.g. lodash, requests, Newtonsoft.Json).
        package_type: npm, pypi/pip, or nuget.

    Returns:
        ``github_repository_url``, ``owner``, ``repo``, ``source_field`` (where the link was found),
        or ``note`` when no GitHub URL is present in registry metadata.
    """
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        return await resolve_package_github_repository(client, package_name, package_type)


@mcp.tool(annotations=_READ_ONLY_OPEN_WORLD)
async def check_package_release_sync(
    package_name: str,
    package_type: str,
    repository_url: str,
) -> dict:
    """
    Compare the latest published version on the package manager (npm, PyPI, NuGet)
    with the latest GitHub release tag (or best-effort semver from tags).

    Args:
        package_name: Published name (e.g. lodash, requests, Newtonsoft.Json).
        package_type: One of: npm, pypi, nuget (aliases: pip -> pypi).
        repository_url: Source repository, e.g. https://github.com/owner/repo

    Returns:
        Structured comparison plus raw registry/GitHub metadata.
    """
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        return await check_release_sync(client, package_name, package_type, repository_url)


@mcp.tool(annotations=_READ_ONLY_OPEN_WORLD)
async def check_snyk_advisor_package(
    package_name: str,
    package_type: str,
) -> dict:
    """
    Load the public Snyk vulnerability / health page for a package and extract key fields.

    Data comes from security.snyk.io HTML (no API key). Supported ecosystems here: npm, pypi, nuget.

    Args:
        package_name: Registry package name.
        package_type: npm, pypi/pip, or nuget.

    Returns:
        Parsed health score, reported latest version, and coarse security flags when detectable.
    """
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        return await fetch_snyk_advisor_page(client, package_name, package_type)


@mcp.tool(annotations=_READ_ONLY_OPEN_WORLD)
async def check_recent_critical_vulnerabilities(
    package_name: str,
    package_type: str,
) -> dict:
    """
    List **critical** vulnerabilities for a package from the OSV database in the last 30 days.

    Includes: (1) advisories whose **published** date falls in the window, and
    (2) **incident-style** updates: critical issues whose **modified** date is in the window
    but were published earlier (e.g. advisory refresh).

    Critical is determined from GitHub severity labels and/or CVSS v3/v4 scores (see tool output ``note``).

    Args:
        package_name: Published package name on the registry.
        package_type: npm, pypi/pip, or nuget.

    Returns:
        Counts, capped lists of disclosures and activity rows, and OSV metadata.
    """
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        return await recent_critical_vulnerabilities_and_incidents(
            client, package_name, package_type
        )


@mcp.tool(annotations=_READ_ONLY_OPEN_WORLD)
async def check_openssf_scorecard(
    repository_url: str,
) -> dict:
    """
    Fetch OpenSSF Scorecard results for a GitHub repository via the public REST API.

    Args:
        repository_url: https://github.com/org/repo (github.com only).

    Returns:
        Aggregate score, analysis date, commit, and a sample of check results.
    """
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        return await fetch_openssf_scorecard(client, repository_url)


@mcp.tool(annotations=_READ_ONLY_LOCAL)
async def check_dependency_version_pinning(
    search_root: str = ".",
    max_depth: int = 8,
) -> dict:
    """
    Scan the given folder tree for dependency manifests across major ecosystems and flag
    unpinned or loosely pinned entries.

    Discovers (non-exhaustive): ``package.json``, ``composer.json``, ``Cargo.toml``, ``Gemfile``,
    ``go.mod``, ``pom.xml``, ``build.gradle`` / ``build.gradle.kts``, ``*.csproj``,
    ``pubspec.yaml``, ``environment.yml`` / ``conda.yml``, ``mix.exs``, ``Package.swift``,
    ``Pipfile``, ``pyproject.toml`` (PEP 621, Poetry + groups, PDM, PEP 735 dependency-groups),
    ``requirements*.txt``, ``constraints.txt``. Skips ``node_modules``, ``.venv``, ``vendor``,
    ``target`` (Rust build), ``Pods``, ``.git``, etc.

    Args:
        search_root: Directory to scan. Relative paths are resolved from the server process
            current working directory (often the workspace root when using stdio MCP).
        max_depth: Maximum directory depth below ``search_root`` (default 8).

    Returns:
        Per-file ``reports`` with ``issues`` (dependency, specifier, reason). See ``summary``
        for ``supported_manifests`` and ecosystem-specific pinning rules (e.g. Go modules,
        SwiftPM ``from:``, Cargo default compatible releases).
    """
    return await asyncio.to_thread(scan_dependency_pinning, search_root, max_depth)


@mcp.tool(annotations=_READ_ONLY_OPEN_WORLD)
async def create_dependency_analysis_summary(
    package_name: str,
    package_type: str,
    repository_url: str,
) -> dict:
    """
    Run release sync, Snyk page parsing, OpenSSF Scorecard, and OSV critical 30-day security
    checks, then return markdown plus JSON sections.

    Args:
        package_name: Published package name.
        package_type: npm, pypi, or nuget.
        repository_url: GitHub URL for the project (used for release comparison and Scorecard).

    Returns:
        ``markdown`` narrative and structured ``release_sync``, ``snyk_advisor``,
        ``openssf_scorecard``, ``recent_critical_security``, and
        ``owasp_dependency_guidance`` (practices, OWASP cheat sheet + NPM Security + Top 10 A06 links, live excerpt when available).
    """
    return await dependency_health_summary(package_name, package_type, repository_url)


def main() -> None:
    """
    - Local MCP clients: run with stdio (default when ``PORT`` is unset).
    - Fly.io / container HTTP: set ``PORT`` (Fly injects this); binds ``0.0.0.0`` and uses
      ``streamable-http`` unless ``FASTMCP_TRANSPORT`` overrides it.
    """
    port_env = os.environ.get("PORT")
    transport = os.environ.get("FASTMCP_TRANSPORT", "").strip().lower()

    if port_env:
        port = int(port_env)
        host = os.environ.get("FASTMCP_HOST", "0.0.0.0")
        http_transport = transport or "streamable-http"
        if http_transport == "stdio":
            http_transport = "streamable-http"
        mcp.run(transport=http_transport, host=host, port=port)
        return

    if transport in {"http", "sse", "streamable-http"}:
        host = os.environ.get("FASTMCP_HOST", "127.0.0.1")
        port = int(os.environ.get("FASTMCP_PORT", "8000"))
        mcp.run(transport=transport, host=host, port=port)
        return

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
