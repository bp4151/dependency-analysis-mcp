"""HTTP clients for registries, Snyk, OpenSSF Scorecard, OSV, and OWASP dependency guidance."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, unquote, urlparse

import httpx
from cvss import CVSS3, CVSS4
from cvss.exceptions import CVSSError
from packaging.version import InvalidVersion, Version

DEFAULT_TIMEOUT = 30.0
USER_AGENT = "dependency-analysis-mcp/0.1 (+https://github.com/modelcontextprotocol)"
SCORECARD_BASE = "https://api.securityscorecards.dev/projects"
OSV_QUERY_URL = "https://api.osv.dev/v1/query"
RECENT_SECURITY_WINDOW_DAYS = 30
CRITICAL_CVSS3_MIN = 9.0
CRITICAL_CVSS4_MIN = 9.0

OWASP_VULNERABLE_DEPENDENCY_CHEATSHEET_HTML = (
    "https://cheatsheetseries.owasp.org/cheatsheets/"
    "Vulnerable_Dependency_Management_Cheat_Sheet.html"
)
OWASP_VULNERABLE_DEPENDENCY_CHEATSHEET_RAW = (
    "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/"
    "Vulnerable_Dependency_Management_Cheat_Sheet.md"
)
OWASP_TOP10_A06_VULNERABLE_COMPONENTS = (
    "https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/"
)

# Distilled from OWASP Vulnerable Dependency Management Cheat Sheet (fallback if fetch fails).
OWASP_THIRD_PARTY_DEPENDENCY_FALLBACK_BULLETS: list[str] = [
    "Automate dependency and vulnerability analysis from the start of the project; deferring it creates remediation debt.",
    "Treat third-party code as part of your security posture: know what you import and from where.",
    "For transitive vulnerabilities, prefer acting on direct dependencies; fixing transitives directly can destabilize the app.",
    "Risk acceptance for a vulnerable library needs CRO/CISO (or CISO) sign-off with solid technical analysis and CVSS context.",
    "When a patch exists: upgrade in a test environment, run automated tests, then promote.",
    "When a fix is delayed: apply vendor workarounds, harden calls to risky APIs, document CVE-scoped suppressions—not blanket ignores.",
    "When the vendor will not fix: plan replacement, contribute upstream patches for OSS, or implement defensive controls from CVE details.",
    "Prefer scanners that use multiple advisory sources so full-disclosure issues without a CVE are not missed.",
]


def _markdown_to_plain_excerpt(md: str, max_chars: int = 1400) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", md)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return text


def _owasp_cheatsheet_h2_titles(md: str) -> list[str]:
    titles: list[str] = []
    for m in re.finditer(r"^##\s+(.+)$", md, re.M):
        t = m.group(1).strip()
        if t.lower() == "tools":
            continue
        titles.append(t)
    return titles[:14]


async def fetch_owasp_third_party_dependency_guidance(
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    """
    Load OWASP third-party dependency handling guidance from the Cheat Sheet Series (raw Markdown),
    plus canonical links to the rendered cheat sheet and OWASP Top 10 A06 (outdated/vulnerable components).
    """
    out: dict[str, Any] = {
        "vulnerable_dependency_management_cheat_sheet_url": OWASP_VULNERABLE_DEPENDENCY_CHEATSHEET_HTML,
        "owasp_top_10_dependency_category_url": OWASP_TOP10_A06_VULNERABLE_COMPONENTS,
        "owasp_top_10_dependency_category_label": (
            "OWASP Top 10 (2021) A06:2021 – Vulnerable and Outdated Components"
        ),
        "source_raw_url": OWASP_VULNERABLE_DEPENDENCY_CHEATSHEET_RAW,
        "key_practices": list(OWASP_THIRD_PARTY_DEPENDENCY_FALLBACK_BULLETS),
        "cheat_sheet_section_titles": [],
        "excerpt": None,
        "fetch_ok": False,
        "fetch_error": None,
    }
    try:
        r = await client.get(
            OWASP_VULNERABLE_DEPENDENCY_CHEATSHEET_RAW, follow_redirects=True
        )
        r.raise_for_status()
        md = r.text
        out["fetch_ok"] = True
        out["cheat_sheet_section_titles"] = _owasp_cheatsheet_h2_titles(md)
        out["excerpt"] = _markdown_to_plain_excerpt(md)
    except (httpx.HTTPError, OSError, UnicodeError) as e:
        out["fetch_error"] = str(e)[:240]
    return out


def _github_headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def normalize_package_type(package_type: str) -> str:
    t = package_type.strip().lower()
    aliases = {"pip": "pypi", "python": "pypi", "dotnet": "nuget"}
    return aliases.get(t, t)


def osv_ecosystem(package_type: str) -> str:
    pt = normalize_package_type(package_type)
    m = {"npm": "npm", "pypi": "PyPI", "nuget": "NuGet"}
    if pt not in m:
        raise ValueError(f"Unsupported package_type for OSV: {package_type!r}")
    return m[pt]


def parse_osv_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def vuln_is_critical(vuln: dict[str, Any]) -> bool:
    """GitHub advisory CRITICAL label or CVSS v3/v4 base score in critical range."""
    ds = vuln.get("database_specific")
    if isinstance(ds, dict):
        ghs = ds.get("severity")
        if isinstance(ghs, str) and ghs.strip().upper() == "CRITICAL":
            return True
    for item in vuln.get("severity") or []:
        if not isinstance(item, dict):
            continue
        score_str = item.get("score")
        if not isinstance(score_str, str):
            continue
        stype = str(item.get("type", ""))
        try:
            if "CVSS_V3" in stype or "CVSS_3" in stype:
                if float(CVSS3(score_str).base_score) >= CRITICAL_CVSS3_MIN:
                    return True
            if "CVSS_V4" in stype or "CVSS_4" in stype:
                c4 = CVSS4(score_str)
                sev = (getattr(c4, "severity", None) or "").lower()
                if sev == "critical" or float(c4.base_score) >= CRITICAL_CVSS4_MIN:
                    return True
        except (CVSSError, ValueError, TypeError, ArithmeticError):
            continue
    return False


def _summarize_osv_vuln(vuln: dict[str, Any]) -> dict[str, Any]:
    ds = vuln.get("database_specific") if isinstance(vuln.get("database_specific"), dict) else {}
    return {
        "id": vuln.get("id"),
        "summary": (vuln.get("summary") or "")[:280],
        "published": vuln.get("published"),
        "modified": vuln.get("modified"),
        "aliases": (vuln.get("aliases") or [])[:6],
        "github_severity": ds.get("severity"),
    }


def github_https_from_text(text: str | None) -> str | None:
    """Normalize common npm/git/PyPI URL shapes to https://github.com/owner/repo."""
    if not text or not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    shorthand = raw.removeprefix("github:").split("#")[0].strip()
    if shorthand and "/" in shorthand and "://" not in shorthand:
        owner, _, rest = shorthand.partition("/")
        repo = rest.split("/")[0].removesuffix(".git")
        if owner and repo:
            return f"https://github.com/{owner}/{repo}"
    cleaned = raw.removeprefix("git+").strip()
    if cleaned.startswith("git@github.com:"):
        path = cleaned.split(":", 1)[1].removesuffix(".git").strip("/")
        parts = path.split("/")
        if len(parts) >= 2:
            return f"https://github.com/{parts[0]}/{parts[1]}"
    if "github.com" not in cleaned.lower():
        return None
    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
    host = parsed.netloc.lower().split("@")[-1].removeprefix("www.")
    if host != "github.com":
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if owner and repo:
        return f"https://github.com/{owner}/{repo}"
    return None


def parse_github_repo(repository_url: str) -> tuple[str, str]:
    """Return (owner, repo) for github.com URLs."""
    raw = repository_url.strip()
    if raw.startswith("git@github.com:"):
        path = raw.split(":", 1)[1]
    else:
        p = urlparse(raw)
        host = (p.netloc or "").lower().split("@")[-1]
        if host not in ("github.com", "www.github.com"):
            raise ValueError(
                "Repository URL must point to github.com (OpenSSF Scorecard API requires it)."
            )
        path = p.path.strip("/")
    path = path.removesuffix(".git")
    parts = [unquote(x) for x in path.split("/") if x]
    if len(parts) < 2:
        raise ValueError(f"Could not parse owner/repo from URL: {repository_url!r}")
    return parts[0], parts[1]


def strip_html_to_text(html: str) -> str:
    html = re.sub(
        r"<script\b[^>]*>[\s\S]*?</script>", " ", html, flags=re.I
    )
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def pick_latest_semver(versions: list[str], prefer_stable: bool = True) -> str | None:
    if not versions:
        return None
    parsed: list[tuple[Version, str]] = []
    for v in versions:
        try:
            parsed.append((Version(v), v))
        except InvalidVersion:
            continue
    if not parsed:
        return versions[-1]
    if prefer_stable:
        stable = [(pv, s) for pv, s in parsed if not pv.is_prerelease]
        if stable:
            return str(max(stable, key=lambda x: x[0])[0])
    return str(max(parsed, key=lambda x: x[0])[0])


def normalize_version_label(v: str | None) -> str:
    if not v:
        return ""
    v = v.strip()
    if v.lower().startswith("v") and len(v) > 1 and v[1].isdigit():
        return v[1:]
    return v


def versions_equivalent(a: str | None, b: str | None) -> bool | None:
    """True if equal after normalization; None if comparison is inconclusive."""
    if not a or not b:
        return None
    na, nb = normalize_version_label(a), normalize_version_label(b)
    if na == nb:
        return True
    try:
        return Version(na) == Version(nb)
    except InvalidVersion:
        return na.casefold() == nb.casefold()


async def fetch_registry_latest(
    client: httpx.AsyncClient, package_type: str, package_name: str
) -> dict[str, Any]:
    pt = normalize_package_type(package_type)
    if pt == "npm":
        path = quote(package_name, safe="@")
        r = await client.get(f"https://registry.npmjs.org/{path}", follow_redirects=True)
        r.raise_for_status()
        data = r.json()
        latest = (data.get("dist-tags") or {}).get("latest")
        if not latest:
            raise ValueError("npm registry response missing dist-tags.latest")
        return {"package_manager": "npm", "latest_version": latest, "source": "registry.npmjs.org"}

    if pt == "pypi":
        name = package_name.strip()
        r = await client.get(f"https://pypi.org/pypi/{quote(name)}/json", follow_redirects=True)
        r.raise_for_status()
        ver = r.json()["info"]["version"]
        return {"package_manager": "pypi", "latest_version": ver, "source": "pypi.org"}

    if pt == "nuget":
        pid = package_name.strip().lower()
        r = await client.get(
            f"https://api.nuget.org/v3-flatcontainer/{quote(pid, safe='')}/index.json",
            follow_redirects=True,
        )
        r.raise_for_status()
        vers = r.json().get("versions") or []
        latest = pick_latest_semver(vers)
        if not latest:
            raise ValueError("NuGet index returned no versions")
        return {"package_manager": "nuget", "latest_version": latest, "source": "api.nuget.org"}

    raise ValueError(
        f"Unsupported package_type {package_type!r}. Use npm, pypi, or nuget."
    )


async def iter_nuget_catalog_entries(
    client: httpx.AsyncClient, package_id: str
) -> list[dict[str, Any]]:
    """Load all catalogEntry dicts from NuGet v3 registration (handles paged indexes)."""
    pid = package_id.strip().lower()
    idx_url = f"https://api.nuget.org/v3/registration5-gz-semver2/{quote(pid, safe='')}/index.json"
    r = await client.get(idx_url, follow_redirects=True)
    r.raise_for_status()
    data = r.json()
    out: list[dict[str, Any]] = []
    for item in data.get("items") or []:
        if item.get("items"):
            for sub in item["items"]:
                ce = sub.get("catalogEntry")
                if isinstance(ce, dict):
                    out.append(ce)
            continue
        page_url = item.get("@id")
        if not page_url:
            continue
        pr = await client.get(page_url, follow_redirects=True)
        pr.raise_for_status()
        for sub in pr.json().get("items") or []:
            ce = sub.get("catalogEntry")
            if isinstance(ce, dict):
                out.append(ce)
    return out


def _pick_latest_catalog_entry(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not entries:
        return None
    scored: list[tuple[Version, dict[str, Any]]] = []
    for ce in entries:
        v = ce.get("version")
        if not v or not isinstance(v, str):
            continue
        try:
            scored.append((Version(v), ce))
        except InvalidVersion:
            continue
    if not scored:
        return entries[-1]
    stable = [(pv, ce) for pv, ce in scored if not pv.is_prerelease]
    pool = stable or scored
    return max(pool, key=lambda x: x[0])[1]


def _github_from_npm_registry_payload(data: dict[str, Any]) -> tuple[str | None, str | None]:
    repo = data.get("repository")
    url: str | None
    if isinstance(repo, str):
        url = repo
    elif isinstance(repo, dict):
        url = repo.get("url")
    else:
        url = None
    gh = github_https_from_text(url) if url else None
    if gh:
        return gh, "npm.package.repository"
    bugs = data.get("bugs")
    if isinstance(bugs, dict):
        bu = bugs.get("url")
        gh = github_https_from_text(bu) if isinstance(bu, str) else None
        if gh:
            return gh, "npm.package.bugs.url"
    return None, None


def _pypi_project_url_priority(label: str) -> int:
    l = label.lower()
    hints = (
        "github",
        "source",
        "repository",
        "code",
        "development",
        "homepage",
        "home",
        "url",
    )
    for i, h in enumerate(hints):
        if h in l:
            return i
    return len(hints)


def _github_from_pypi_info(info: dict[str, Any]) -> tuple[str | None, str | None]:
    urls = info.get("project_urls")
    pairs: list[tuple[str, str]] = []
    if isinstance(urls, dict):
        for k, v in urls.items():
            if isinstance(k, str) and isinstance(v, str):
                pairs.append((k, v))
    pairs.sort(key=lambda kv: _pypi_project_url_priority(kv[0]))
    for label, v in pairs:
        gh = github_https_from_text(v)
        if gh:
            return gh, f"pypi.info.project_urls[{label}]"
    for field in ("home_page", "download_url"):
        v = info.get(field)
        if isinstance(v, str):
            gh = github_https_from_text(v)
            if gh:
                return gh, f"pypi.info.{field}"
    return None, None


def _github_from_nuget_catalog_entry(ce: dict[str, Any]) -> tuple[str | None, str | None]:
    repo = ce.get("repository")
    if isinstance(repo, dict):
        u = repo.get("url")
        if isinstance(u, str):
            gh = github_https_from_text(u)
            if gh:
                return gh, "nuget.catalogEntry.repository.url"
    elif isinstance(repo, str):
        gh = github_https_from_text(repo)
        if gh:
            return gh, "nuget.catalogEntry.repository"
    pu = ce.get("projectUrl")
    if isinstance(pu, str):
        gh = github_https_from_text(pu)
        if gh:
            return gh, "nuget.catalogEntry.projectUrl"
    return None, None


async def resolve_package_github_repository(
    client: httpx.AsyncClient, package_name: str, package_type: str
) -> dict[str, Any]:
    """
    Resolve a canonical GitHub repo URL from npm / PyPI / NuGet package metadata.

    Used as input for check_package_release_sync and check_openssf_scorecard.
    """
    pt = normalize_package_type(package_type)
    out: dict[str, Any] = {
        "package_name": package_name,
        "package_type": pt,
        "github_repository_url": None,
        "owner": None,
        "repo": None,
        "source_field": None,
    }
    if pt == "npm":
        path = quote(package_name, safe="@")
        r = await client.get(f"https://registry.npmjs.org/{path}", follow_redirects=True)
        r.raise_for_status()
        data = r.json()
        gh, src = _github_from_npm_registry_payload(data)
        if gh:
            owner, repo = parse_github_repo(gh)
            out.update(
                {
                    "github_repository_url": gh,
                    "owner": owner,
                    "repo": repo,
                    "source_field": src,
                }
            )
        else:
            out["note"] = "No GitHub URL found in npm package.repository or bugs.url."
        return out

    if pt == "pypi":
        name = package_name.strip()
        r = await client.get(
            f"https://pypi.org/pypi/{quote(name)}/json", follow_redirects=True
        )
        r.raise_for_status()
        info = r.json().get("info") or {}
        gh, src = _github_from_pypi_info(info)
        if gh:
            owner, repo = parse_github_repo(gh)
            out.update(
                {
                    "github_repository_url": gh,
                    "owner": owner,
                    "repo": repo,
                    "source_field": src,
                }
            )
        else:
            out["note"] = (
                "No GitHub URL found in PyPI project_urls, home_page, or download_url."
            )
        return out

    if pt == "nuget":
        entries = await iter_nuget_catalog_entries(client, package_name)
        ce = _pick_latest_catalog_entry(entries)
        if not ce:
            out["note"] = "NuGet registration contained no catalog entries."
            return out
        gh, src = _github_from_nuget_catalog_entry(ce)
        out["nuget_catalog_version"] = ce.get("version")
        if gh:
            owner, repo = parse_github_repo(gh)
            out.update(
                {
                    "github_repository_url": gh,
                    "owner": owner,
                    "repo": repo,
                    "source_field": src,
                }
            )
        else:
            out["note"] = (
                "No GitHub URL on the latest NuGet catalog entry "
                "(repository / projectUrl may point elsewhere)."
            )
        return out

    raise ValueError(
        f"Unsupported package_type {package_type!r}. Use npm, pypi, or nuget."
    )


async def fetch_github_release_version(
    client: httpx.AsyncClient, owner: str, repo: str
) -> dict[str, Any]:
    headers = _github_headers()
    out: dict[str, Any] = {"owner": owner, "repo": repo}
    latest_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    r = await client.get(latest_url, headers=headers)
    if r.status_code == 200:
        tag = (r.json().get("tag_name") or "").strip()
        out["github_release_tag"] = tag
        out["github_version_hint"] = normalize_version_label(tag)
        out["source"] = "GitHub releases/latest"
        return out
    if r.status_code != 404:
        r.raise_for_status()

    tags_url = f"https://api.github.com/repos/{owner}/{repo}/tags"
    r2 = await client.get(tags_url, headers=headers, params={"per_page": 100})
    r2.raise_for_status()
    tags = [t.get("name", "") for t in r2.json() if t.get("name")]
    if not tags:
        out["github_release_tag"] = None
        out["note"] = "No releases and no tags found via GitHub API."
        return out
    best = pick_latest_semver(tags, prefer_stable=True)
    if not best:
        best = tags[0]
    out["github_release_tag"] = best
    out["github_version_hint"] = normalize_version_label(best)
    out["source"] = "GitHub tags (no latest release; picked best semver from first page)"
    return out


async def check_release_sync(
    client: httpx.AsyncClient,
    package_name: str,
    package_type: str,
    repository_url: str,
) -> dict[str, Any]:
    owner, repo = parse_github_repo(repository_url)
    reg = await fetch_registry_latest(client, package_type, package_name)
    gh = await fetch_github_release_version(client, owner, repo)
    reg_v = reg["latest_version"]
    gh_v = gh.get("github_version_hint") or gh.get("github_release_tag")
    eq = versions_equivalent(reg_v, gh_v)
    in_sync = eq is True
    uncertain = eq is None and bool(reg_v and gh_v)
    return {
        "package_name": package_name,
        "package_type": normalize_package_type(package_type),
        "repository": f"github.com/{owner}/{repo}",
        "registry_latest": reg_v,
        "github_tag_or_release": gh.get("github_release_tag"),
        "comparison": {
            "in_sync": in_sync,
            "uncertain_due_to_non_semver": uncertain,
            "registry_version": reg_v,
            "github_normalized": gh_v,
        },
        "details": {"registry": reg, "github": gh},
    }


def snyk_package_url(package_type: str, package_name: str) -> str:
    pt = normalize_package_type(package_type)
    segment = {"npm": "npm", "pypi": "pip", "nuget": "nuget"}.get(pt)
    if not segment:
        raise ValueError("Snyk public pages support npm, pypi, and nuget for this tool.")
    enc = quote(package_name, safe="@")
    return f"https://security.snyk.io/package/{segment}/{enc}"


async def fetch_snyk_advisor_page(
    client: httpx.AsyncClient, package_name: str, package_type: str
) -> dict[str, Any]:
    url = snyk_package_url(package_type, package_name)
    r = await client.get(url, follow_redirects=True)
    r.raise_for_status()
    text = strip_html_to_text(r.text)
    health_m = re.search(
        r"Package Health Score\D*(\d{1,3})\s*/\s*100", text, re.I
    )
    latest_m = re.search(
        r"Latest version:\s*([A-Za-z0-9._+\-]+)", text, re.I
    )
    security_issues = None
    if re.search(r"NO KNOWN SECURITY ISSUES", text, re.I):
        security_issues = False
    elif re.search(r"SECURITY ISSUES FOUND", text, re.I):
        security_issues = True
    nvuln_m = re.search(
        r"No vulnerabilities found in the latest version", text, re.I
    )
    return {
        "package_name": package_name,
        "package_type": normalize_package_type(package_type),
        "snyk_package_url": url,
        "package_health_score": int(health_m.group(1)) if health_m else None,
        "latest_version_reported": latest_m.group(1) if latest_m else None,
        "security_issues_flag": security_issues,
        "no_vulns_latest_wording_found": bool(nvuln_m),
        "note": (
            "Fields are parsed from the public security.snyk.io HTML and may be incomplete "
            "if the page layout changes."
        ),
    }


async def fetch_openssf_scorecard(
    client: httpx.AsyncClient, repository_url: str
) -> dict[str, Any]:
    owner, repo = parse_github_repo(repository_url)
    url = f"{SCORECARD_BASE}/github.com/{owner}/{repo}"
    r = await client.get(url, follow_redirects=True)
    if r.status_code == 404:
        return {
            "repository": f"github.com/{owner}/{repo}",
            "error": "No published Scorecard result for this repository (404).",
            "scorecard_api_url": url,
        }
    r.raise_for_status()
    data = r.json()
    checks = data.get("checks") or []
    summary_checks = [
        {
            "name": c.get("name"),
            "score": c.get("score"),
            "reason": (c.get("reason") or "")[:240],
        }
        for c in checks[:25]
    ]
    return {
        "repository": data.get("repo", {}).get("name", f"github.com/{owner}/{repo}"),
        "score": data.get("score"),
        "date": data.get("date"),
        "commit": (data.get("repo") or {}).get("commit"),
        "scorecard_version": (data.get("scorecard") or {}).get("version"),
        "checks_sample": summary_checks,
        "checks_total": len(checks),
        "scorecard_api_url": url,
    }


async def recent_critical_vulnerabilities_and_incidents(
    client: httpx.AsyncClient,
    package_name: str,
    package_type: str,
    days: int = RECENT_SECURITY_WINDOW_DAYS,
) -> dict[str, Any]:
    """
    Use OSV (Open Source Vulnerabilities) to find **critical** issues tied to the package.

    - **Disclosures**: ``published`` within the last ``days`` (new critical CVEs/advisories).
    - **Incident-style activity**: ``modified`` within the window but ``published`` before it
      (e.g. advisory refreshed, metadata or severity updates on existing critical issues).
    """
    ecosystem = osv_ecosystem(package_type)
    r = await client.post(
        OSV_QUERY_URL,
        json={"package": {"name": package_name, "ecosystem": ecosystem}},
        follow_redirects=True,
    )
    r.raise_for_status()
    body = r.json()
    vulns_raw = body.get("vulns") or []
    if not isinstance(vulns_raw, list):
        vulns_raw = []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    new_critical: list[dict[str, Any]] = []
    incident_updates: list[dict[str, Any]] = []

    for v in vulns_raw:
        if not isinstance(v, dict):
            continue
        if not vuln_is_critical(v):
            continue
        pub = parse_osv_datetime(v.get("published"))
        mod = parse_osv_datetime(v.get("modified")) or pub
        summ = _summarize_osv_vuln(v)
        if pub and pub >= cutoff:
            new_critical.append(summ)
        elif mod and mod >= cutoff and (pub is None or pub < cutoff):
            incident_updates.append(summ)

    cap = 25
    return {
        "package_name": package_name,
        "package_type": normalize_package_type(package_type),
        "osv_ecosystem": ecosystem,
        "source": OSV_QUERY_URL,
        "window_days": days,
        "window_start_utc": cutoff.isoformat(),
        "critical_disclosures_in_window": new_critical[:cap],
        "critical_incident_activity_in_window": incident_updates[:cap],
        "critical_disclosures_count": len(new_critical),
        "critical_incident_activity_count": len(incident_updates),
        "osv_vulnerabilities_returned": len(vulns_raw),
        "note": (
            "Critical = GitHub advisory severity CRITICAL and/or CVSS v3 base ≥ "
            f"{CRITICAL_CVSS3_MIN} / CVSS v4 labeled Critical or base ≥ {CRITICAL_CVSS4_MIN}. "
            "Data is from the public OSV API and may omit ecosystem-specific issues."
        ),
    }


async def dependency_health_summary(
    package_name: str,
    package_type: str,
    repository_url: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        sync = await check_release_sync(client, package_name, package_type, repository_url)
        snyk = await fetch_snyk_advisor_page(client, package_name, package_type)
        scorecard = await fetch_openssf_scorecard(client, repository_url)
        recent_crit = await recent_critical_vulnerabilities_and_incidents(
            client, package_name, package_type
        )
        owasp = await fetch_owasp_third_party_dependency_guidance(client)

    lines = [
        f"## Dependency health summary: {package_name} ({normalize_package_type(package_type)})",
        "",
        "### Release sync (registry vs GitHub)",
        f"- Registry latest: **{sync['registry_latest']}**",
        f"- GitHub tag/release: **{sync['github_tag_or_release']!s}**",
        f"- In sync (semver): **{sync['comparison']['in_sync']}**",
        "",
        "### Snyk (security.snyk.io)",
        f"- URL: {snyk.get('snyk_package_url')}",
        f"- Package health score: **{snyk.get('package_health_score')}**/100",
        f"- Latest version (page): **{snyk.get('latest_version_reported')}**",
        f"- Security issues flag (page): **{snyk.get('security_issues_flag')}**",
        "",
        "### Critical security (OSV, last {recent_crit['window_days']} days)",
        f"- New **critical** disclosures (by publish date): **{recent_crit['critical_disclosures_count']}**",
        f"- Critical **incident/advisory activity** (modified in window, published earlier): **{recent_crit['critical_incident_activity_count']}**",
        f"- Source: `{recent_crit['source']}` ({recent_crit['osv_ecosystem']})",
        "",
        "### OpenSSF Scorecard",
        f"- Aggregate score: **{scorecard.get('score')}**/10",
        f"- As of: {scorecard.get('date')}",
        f"- API: {scorecard.get('scorecard_api_url')}",
    ]
    if scorecard.get("error"):
        lines.append(f"- Note: {scorecard['error']}")

    lines.extend(
        [
            "",
            "### OWASP third-party dependency guidance",
            "",
            "Practices (aligned with the OWASP *Vulnerable Dependency Management* cheat sheet):",
        ]
    )
    for b in owasp["key_practices"]:
        lines.append(f"- {b}")
    lines.extend(
        [
            "",
            "**References**",
            f"- [Vulnerable Dependency Management Cheat Sheet]({owasp['vulnerable_dependency_management_cheat_sheet_url']})",
            f"- [{owasp['owasp_top_10_dependency_category_label']}]({owasp['owasp_top_10_dependency_category_url']})",
        ]
    )
    if owasp.get("fetch_ok") and owasp.get("cheat_sheet_section_titles"):
        lines.append("")
        lines.append("**Current cheat sheet section outline** (from live OWASP source):")
        for t in owasp["cheat_sheet_section_titles"][:8]:
            lines.append(f"- {t}")
    if owasp.get("excerpt"):
        lines.append("")
        lines.append(f"*Excerpt (abridged):* {owasp['excerpt']}")
    if not owasp.get("fetch_ok") and owasp.get("fetch_error"):
        lines.append("")
        lines.append(
            f"*Note: Could not refresh live cheat sheet ({owasp['fetch_error']}). "
            "Practices and reference links above still apply.*"
        )

    if recent_crit["critical_disclosures_count"] or recent_crit["critical_incident_activity_count"]:
        lines.append("")
        lines.append("#### Recent critical items (sample)")
        for row in recent_crit["critical_disclosures_in_window"][:5]:
            lines.append(
                f"- **NEW** `{row.get('id')}` — {row.get('summary', '')[:120]}"
            )
        for row in recent_crit["critical_incident_activity_in_window"][:5]:
            lines.append(
                f"- **ACTIVITY** `{row.get('id')}` — {row.get('summary', '')[:120]}"
            )

    return {
        "markdown": "\n".join(lines),
        "release_sync": sync,
        "snyk_advisor": snyk,
        "openssf_scorecard": scorecard,
        "recent_critical_security": recent_crit,
        "owasp_dependency_guidance": owasp,
    }
