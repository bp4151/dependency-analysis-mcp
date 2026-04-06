"""Render tool result dicts as engineer-friendly Markdown."""

from __future__ import annotations

from typing import Any


def _esc(s: Any) -> str:
    if s is None:
        return "—"
    t = str(s).replace("|", "\\|").replace("\n", " ")
    return t or "—"


def format_github_repository_lookup(data: dict[str, Any]) -> str:
    lines = [
        "## GitHub repository lookup",
        "",
        f"- **Package:** `{_esc(data.get('package_name'))}` ({_esc(data.get('package_type'))})",
    ]
    url = data.get("github_repository_url")
    if url:
        lines.append(f"- **GitHub URL:** {url}")
        lines.append(f"- **Owner / repo:** `{_esc(data.get('owner'))}` / `{_esc(data.get('repo'))}`")
        lines.append(f"- **Source field:** `{_esc(data.get('source_field'))}`")
        if data.get("nuget_catalog_version"):
            lines.append(
                f"- **NuGet catalog version (context):** `{_esc(data.get('nuget_catalog_version'))}`"
            )
    else:
        lines.append(f"- **Result:** No GitHub URL found in registry metadata.")
        if data.get("note"):
            lines.append(f"- **Note:** {data['note']}")
    return "\n".join(lines)


def format_release_sync(data: dict[str, Any]) -> str:
    comp = data.get("comparison") or {}
    lines = [
        "## Registry vs GitHub release",
        "",
        f"- **Package:** `{_esc(data.get('package_name'))}` ({_esc(data.get('package_type'))})",
        f"- **Repository:** `{_esc(data.get('repository'))}`",
        "",
        "| | |",
        "|---|---|",
        f"| Registry latest | `{_esc(data.get('registry_latest'))}` |",
        f"| GitHub tag / release | `{_esc(data.get('github_tag_or_release'))}` |",
        f"| In sync (semver) | **{_esc(comp.get('in_sync'))}** |",
        f"| Uncertain (non-semver) | **{_esc(comp.get('uncertain_due_to_non_semver'))}** |",
        "",
        "### Registry details",
    ]
    reg = (data.get("details") or {}).get("registry") or {}
    for k, v in reg.items():
        lines.append(f"- **{k}:** `{_esc(v)}`")
    lines.extend(["", "### GitHub details"])
    gh = (data.get("details") or {}).get("github") or {}
    for k, v in gh.items():
        lines.append(f"- **{k}:** `{_esc(v)}`")
    return "\n".join(lines)


def format_snyk_advisor(data: dict[str, Any]) -> str:
    def dim(label: str, key: str) -> str:
        d = data.get(key)
        if not isinstance(d, dict):
            return f"- **{label}:** —"
        a, lv = d.get("assessment"), d.get("level")
        if a and lv:
            return f"- **{label}:** {_esc(a)} (`{lv}`)"
        return f"- **{label}:** {_esc(a)}"

    lines = [
        "## Snyk Advisor (security.snyk.io)",
        "",
        f"- **Package:** `{_esc(data.get('package_name'))}` ({_esc(data.get('package_type'))})",
        f"- **Page:** {data.get('snyk_package_url', '—')}",
        f"- **Health score:** **{_esc(data.get('package_health_score'))}**/100",
        f"- **Latest version (page):** `{_esc(data.get('latest_version_reported'))}`",
        f"- **Security issues flag:** `{_esc(data.get('security_issues_flag'))}`",
        f"- **No vulns wording on latest:** `{_esc(data.get('no_vulns_latest_wording_found'))}`",
        dim("Maintenance", "maintenance"),
        dim("Community", "community"),
        dim("Popularity", "popularity"),
    ]
    if data.get("note"):
        lines.extend(["", f"*{_esc(data['note'])}*"])
    return "\n".join(lines)


def format_osv_recent_critical(data: dict[str, Any]) -> str:
    lines = [
        "## Critical vulnerabilities & activity (OSV)",
        "",
        f"- **Package:** `{_esc(data.get('package_name'))}` ({_esc(data.get('package_type'))})",
        f"- **Ecosystem:** `{_esc(data.get('osv_ecosystem'))}`",
        f"- **Window:** last **{_esc(data.get('window_days'))}** days (from `{_esc(data.get('window_start_utc'))}` UTC)",
        f"- **OSV rows returned:** {_esc(data.get('osv_vulnerabilities_returned'))}",
        "",
        "| | Count |",
        "|---|---:|",
        f"| New **critical** disclosures (by publish date) | **{_esc(data.get('critical_disclosures_count'))}** |",
        f"| Critical **activity** (modified in window, published earlier) | **{_esc(data.get('critical_incident_activity_count'))}** |",
        "",
        f"- **Source:** `{_esc(data.get('source'))}`",
    ]
    if data.get("note"):
        lines.extend(["", f"*{_esc(data['note'])}*"])

    new_rows = data.get("critical_disclosures_in_window") or []
    act_rows = data.get("critical_incident_activity_in_window") or []
    if new_rows:
        lines.extend(["", "### New critical disclosures (sample)"])
        for row in new_rows:
            lines.append(
                f"- **`{_esc(row.get('id'))}`** — {_esc(row.get('summary'))} "
                f"(published `{_esc(row.get('published'))}`)"
            )
    if act_rows:
        lines.extend(["", "### Critical incident / advisory activity (sample)"])
        for row in act_rows:
            lines.append(
                f"- **`{_esc(row.get('id'))}`** — {_esc(row.get('summary'))} "
                f"(modified `{_esc(row.get('modified'))}`)"
            )
    return "\n".join(lines)


def format_openssf_scorecard(data: dict[str, Any]) -> str:
    lines = [
        "## OpenSSF Scorecard",
        "",
        f"- **Repository:** `{_esc(data.get('repository'))}`",
        f"- **Aggregate score:** **{_esc(data.get('score'))}**/10",
        f"- **As of:** `{_esc(data.get('date'))}`",
        f"- **Commit:** `{_esc(data.get('commit'))}`",
        f"- **Scorecard version:** `{_esc(data.get('scorecard_version'))}`",
        f"- **Checks (sample / total):** {_esc(len(data.get('checks_sample') or []))} / {_esc(data.get('checks_total'))}",
        f"- **API:** `{_esc(data.get('scorecard_api_url'))}`",
    ]
    if data.get("error"):
        lines.insert(3, f"- **Error:** {data['error']}")

    checks = data.get("checks_sample") or []
    if checks:
        lines.extend(["", "### Checks (sample)", "", "| Check | Score | Reason (trimmed) |", "|---|---:|---|"])
        for c in checks:
            reason = _esc((c.get("reason") or "")[:200])
            lines.append(
                f"| `{_esc(c.get('name'))}` | {_esc(c.get('score'))} | {reason} |"
            )
    return "\n".join(lines)


def format_pinning_scan(data: dict[str, Any]) -> str:
    if data.get("error"):
        return "\n".join(
            [
                "## Dependency pinning scan",
                "",
                f"- **Search root:** `{_esc(data.get('search_root'))}`",
                f"- **Error:** {data['error']}",
            ]
        )

    summ = data.get("summary") or {}
    lines = [
        "## Dependency pinning scan",
        "",
        f"- **Search root:** `{_esc(data.get('search_root'))}`",
        f"- **Max depth:** {_esc(data.get('max_depth'))}",
        f"- **Manifest files found:** {_esc(data.get('manifests_scanned'))}",
        f"- **Loose / unpinned issue count:** **{_esc(data.get('loose_or_unpinned_issue_count'))}**",
        "",
        "### Files by manifest kind",
    ]
    for kind, n in sorted((summ.get("files_by_kind") or {}).items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- **{kind}:** {n}")
    if summ.get("note"):
        lines.extend(["", "### How to interpret issues", "", "> " + summ["note"].replace("\n", "\n> ")])

    paths = data.get("manifest_paths_found") or []
    lines.extend(["", "### Manifest paths scanned", ""])
    if not paths:
        lines.append("*No supported manifest files were found in the scanned tree.*")
    else:
        for p in paths:
            lines.append(f"- `{p}`")

    reports = data.get("reports") or []
    issue_reports = [r for r in reports if r.get("issues")]
    if issue_reports:
        lines.extend(["", "## Findings (files with issues)"])
        for rep in issue_reports:
            fp = rep.get("file", "?")
            kind = rep.get("kind", "?")
            lines.extend(["", f"### `{fp}`", "", f"- **Kind:** `{kind}`", ""])
            issues = rep.get("issues") or []
            lines.append("| Dependency | Specifier | Reason |")
            lines.append("|---|---|---|")
            for iss in issues:
                lines.append(
                    f"| `{_esc(iss.get('dependency'))}` | `{_esc(iss.get('specifier'))}` | {_esc(iss.get('reason'))} |"
                )
    elif reports:
        lines.extend(["", "*No loose or unpinned dependencies reported in scanned manifests.*"])

    for rep in reports:
        if rep.get("error") and not rep.get("issues"):
            lines.extend(["", f"### `{rep.get('file')}`", "", f"- **Parse note:** {rep['error']}"])

    return "\n".join(lines)


def format_dependency_health_summary(data: dict[str, Any]) -> str:
    """Return the narrative Markdown from ``dependency_health_summary``."""
    return (data.get("markdown") or "").strip()
