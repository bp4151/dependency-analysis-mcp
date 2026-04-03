"""Scan common manifest files for unpinned or loosely pinned dependencies."""

from __future__ import annotations

import json
import os
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml
from packaging.requirements import InvalidRequirement, Requirement

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        ".nox",
        ".tox",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        "vendor",
        "Pods",
        ".bundle",
        "target",
        "bin",
        "obj",
        ".build",
    }
)

MANIFEST_FILENAMES = frozenset(
    {
        "package.json",
        "composer.json",
        "Cargo.toml",
        "Gemfile",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "pubspec.yaml",
        "mix.exs",
        "Package.swift",
        "environment.yml",
        "conda.yml",
        "Pipfile",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-prod.txt",
        "constraints.txt",
    }
)

# Extra basename pattern: requirements-*.txt
_REQ_RE = re.compile(r"^requirements[-.].*\.txt$", re.I)


def _should_skip_dir(name: str) -> bool:
    if name in SKIP_DIR_NAMES:
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def _is_manifest_file(path: Path) -> bool:
    name = path.name
    if name in MANIFEST_FILENAMES:
        return True
    if _REQ_RE.match(name):
        return True
    if name.endswith(".csproj"):
        return True
    return False


def _xml_local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def iter_manifest_files(root: Path, max_depth: int) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        return []
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        pdir = Path(dirpath)
        try:
            rel = pdir.relative_to(root)
            depth = len(rel.parts)
        except ValueError:
            depth = 0
        if depth > max_depth:
            dirnames[:] = []
            continue
        for fn in filenames:
            fp = pdir / fn
            if _is_manifest_file(fp):
                found.append(fp)
    return sorted(found)


def _npm_spec_issue(spec: str) -> tuple[bool, str]:
    s = (spec or "").strip()
    if not s:
        return True, "empty_version"
    low = s.lower()
    if low in ("*", "latest", "next", "preview", "canary"):
        return True, "floating_or_wildcard"
    if s.startswith(("file:", "link:", "git+", "git:", "http:", "https:", "workspace:")):
        return False, "non_semver_reference"
    if "*" in s or "x" in s.lower() and re.search(r"\d+\.[xX]", s):
        return True, "wildcard_version"
    if s.startswith("^") or s.startswith("~"):
        return True, "caret_or_tilde_allows_updates"
    if any(
        op in s
        for op in (
            ">",
            "<",
            "||",
            " - ",
            " ",
        )
    ):
        if re.match(r"^\d+\.\d+\.\d+$", s):
            return False, "exact_triple"
        if s[0] in "><=" or "||" in s or " - " in s:
            return True, "range_or_compound"
    if re.match(r"^\d+\.\d+\.\d+(-[\w.]+)?$", s):
        return False, "exact_version"
    return True, "unclassified_loose"


def analyze_package_json(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError) as e:
        return {
            "file": str(path),
            "kind": "package.json",
            "error": str(e)[:200],
            "issues": [],
        }
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            if not isinstance(spec, str):
                issues.append(
                    {
                        "name": name,
                        "section": section,
                        "specifier": str(spec),
                        "reason": "non_string_spec",
                        "detail": "Expected string version/range; object form not classified as pinned.",
                    }
                )
                continue
            loose, code = _npm_spec_issue(spec)
            if loose:
                issues.append(
                    {
                        "name": name,
                        "section": section,
                        "specifier": spec,
                        "reason": code,
                        "detail": _npm_detail(code),
                    }
                )
    return {"file": str(path), "kind": "package.json", "issues": issues, "error": None}


def _npm_detail(code: str) -> str:
    return {
        "caret_or_tilde_allows_updates": "^ and ~ permit newer compatible releases.",
        "range_or_compound": "Comparator or compound range allows multiple versions.",
        "floating_or_wildcard": "Tag or * accepts moving targets.",
        "wildcard_version": "x/* style allows broader matches.",
        "empty_version": "No version constraint.",
        "unclassified_loose": "Specifier not recognized as a single pinned version.",
    }.get(code, "")


def _pep508_loose(line: str) -> tuple[bool, str, str]:
    raw = line.split("#", 1)[0].strip()
    if not raw or raw.startswith("-"):
        return False, "", "skip"
    raw = re.sub(r"\s+", " ", raw)
    try:
        req = Requirement(raw)
    except InvalidRequirement:
        return True, raw, "unparseable_requirement"
    name = req.name
    spec = str(req.specifier).strip()
    if not spec:
        return True, raw, "no_version_specifier"
    specs = list(req.specifier)
    if len(specs) == 1 and specs[0].operator in ("==", "==="):
        return False, raw, "pinned_exact"
    return True, raw, "range_or_multi_specifier"


def analyze_requirements_txt(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {
            "file": str(path),
            "kind": "requirements.txt",
            "error": str(e)[:200],
            "issues": [],
        }
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(
            ("-r ", "-c ", "-e ", "--editable ", "-f ", "--find-links ", "--")
        ):
            continue
        loose, display, code = _pep508_loose(stripped)
        if not loose:
            continue
        if code == "skip":
            continue
        issues.append(
            {
                "line": i,
                "raw": display[:200],
                "reason": code,
                "detail": {
                    "no_version_specifier": "No == or compatible pin; pip may install latest.",
                    "range_or_multi_specifier": "Range or multiple clauses allow version drift.",
                    "unparseable_requirement": "Could not parse as PEP 508; verify manually.",
                }.get(code, ""),
            }
        )
    return {"file": str(path), "kind": "requirements.txt", "issues": issues, "error": None}


def _pipfile_package_loose(spec: Any) -> tuple[bool, str, str]:
    if spec is True:
        return True, "*", "unpinned_boolean"
    if isinstance(spec, str):
        s = spec.strip()
        if not s or s == "*":
            return True, s, "wildcard"
        if s.startswith("=="):
            return False, s, "pinned"
        return True, s, "pipenv_range_or_tag"
    if isinstance(spec, dict):
        ver = spec.get("version")
        if isinstance(ver, str):
            return _pipfile_package_loose(ver)
        return True, str(spec)[:120], "editable_or_complex"
    return True, str(type(spec).__name__), "unknown_spec_shape"


def analyze_pipfile(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        return {
            "file": str(path),
            "kind": "Pipfile",
            "error": str(e)[:200],
            "issues": [],
        }
    for section in ("packages", "dev-packages"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            loose, disp, code = _pipfile_package_loose(spec)
            if loose:
                issues.append(
                    {
                        "name": name,
                        "section": section,
                        "specifier": disp,
                        "reason": code,
                        "detail": "Pipfile allows ranges unless version is ==-pinned.",
                    }
                )
    return {"file": str(path), "kind": "Pipfile", "issues": issues, "error": None}


def _poetry_dep_loose(version_value: Any) -> tuple[bool, str, str]:
    if isinstance(version_value, dict):
        if "path" in version_value or "git" in version_value:
            return False, str(version_value)[:80], "path_or_git"
        v = version_value.get("version")
        if isinstance(v, str):
            return _poetry_version_str_loose(v)
        return True, str(version_value)[:120], "complex_table"
    if isinstance(version_value, str):
        return _poetry_version_str_loose(version_value)
    if isinstance(version_value, list):
        return True, str(version_value)[:120], "multi_constraint"
    return True, str(version_value), "unknown"


def _poetry_version_str_loose(s: str) -> tuple[bool, str, str]:
    s = s.strip()
    if not s:
        return True, s, "empty"
    if s.startswith("=="):
        return False, s, "pinned"
    if s.startswith(("^", "~", ">=", ">", "<", "!=")) or "*" in s:
        return True, s, "poetry_range"
    if re.match(r"^\d", s):
        return True, s, "poetry_bare_version_is_compatible"
    return True, s, "other"


def analyze_pyproject_toml(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        return {
            "file": str(path),
            "kind": "pyproject.toml",
            "error": str(e)[:200],
            "issues": [],
        }

    proj = data.get("project")
    if isinstance(proj, dict):
        block = proj.get("dependencies")
        if isinstance(block, list):
            for raw in block:
                if not isinstance(raw, str):
                    continue
                loose, _, code = _pep508_loose(raw)
                if loose and code != "skip":
                    issues.append(
                        {
                            "section": "project.dependencies",
                            "raw": raw[:200],
                            "reason": code,
                            "detail": "PEP 621 dependency string.",
                        }
                    )
        opt = proj.get("optional-dependencies")
        if isinstance(opt, dict):
            for group, deps in opt.items():
                if not isinstance(deps, list):
                    continue
                for raw in deps:
                    if not isinstance(raw, str):
                        continue
                    loose, _, code = _pep508_loose(raw)
                    if loose and code != "skip":
                        issues.append(
                            {
                                "section": f"project.optional-dependencies.{group}",
                                "raw": raw[:200],
                                "reason": code,
                                "detail": "PEP 621 optional dependency string.",
                            }
                        )

    poetry = (data.get("tool") or {}).get("poetry")
    if isinstance(poetry, dict):
        deps = poetry.get("dependencies")
        if isinstance(deps, dict):
            for name, spec in deps.items():
                if name.lower() == "python":
                    continue
                loose, disp, code = _poetry_dep_loose(spec)
                if loose:
                    issues.append(
                        {
                            "name": name,
                            "section": "tool.poetry.dependencies",
                            "specifier": disp[:200],
                            "reason": code,
                            "detail": "Poetry: bare X.Y.Z is a compatible range (^), not ==.",
                        }
                    )
        pgroups = poetry.get("group")
        if isinstance(pgroups, dict):
            for gname, gdata in pgroups.items():
                if not isinstance(gdata, dict):
                    continue
                gdeps = gdata.get("dependencies")
                if isinstance(gdeps, dict):
                    for name, spec in gdeps.items():
                        loose, disp, code = _poetry_dep_loose(spec)
                        if loose:
                            issues.append(
                                {
                                    "name": name,
                                    "section": f"tool.poetry.group.{gname}.dependencies",
                                    "specifier": disp[:200],
                                    "reason": code,
                                    "detail": "Poetry group dependency.",
                                }
                            )

    dg = data.get("dependency-groups")
    if isinstance(dg, dict):
        for group, deps in dg.items():
            if not isinstance(deps, list):
                continue
            for raw in deps:
                if not isinstance(raw, str):
                    continue
                loose, _, code = _pep508_loose(raw)
                if loose and code != "skip":
                    issues.append(
                        {
                            "section": f"dependency-groups.{group}",
                            "raw": raw[:200],
                            "reason": code,
                            "detail": "PEP 735 dependency group entry.",
                        }
                    )

    pdm = (data.get("tool") or {}).get("pdm")
    if isinstance(pdm, dict):
        for pkey in ("dependencies", "dev-dependencies", "optional-dependencies"):
            block = pdm.get(pkey)
            if not isinstance(block, dict):
                continue
            for name, spec in block.items():
                loose, disp, code = _pipfile_package_loose(spec)
                if loose:
                    issues.append(
                        {
                            "name": name,
                            "section": f"tool.pdm.{pkey}",
                            "specifier": disp,
                            "reason": code,
                            "detail": "PDM dependency (same loose rules as Pipfile strings).",
                        }
                    )

    return {"file": str(path), "kind": "pyproject.toml", "issues": issues, "error": None}


def analyze_composer_json(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError) as e:
        return {
            "file": str(path),
            "kind": "composer.json",
            "error": str(e)[:200],
            "issues": [],
        }
    for section in ("require", "require-dev"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            if name == "php" or name.startswith("ext-") or name.startswith("lib-"):
                continue
            if not isinstance(spec, str):
                issues.append(
                    {
                        "name": name,
                        "section": section,
                        "specifier": str(spec)[:200],
                        "reason": "non_string_spec",
                        "detail": "Composer version should be a string constraint.",
                    }
                )
                continue
            loose, code = _npm_spec_issue(spec)
            if loose:
                issues.append(
                    {
                        "name": name,
                        "section": section,
                        "specifier": spec,
                        "reason": code,
                        "detail": _npm_detail(code),
                    }
                )
    return {"file": str(path), "kind": "composer.json", "issues": issues, "error": None}


def _cargo_version_loose(s: str) -> tuple[bool, str]:
    s = (s or "").strip().strip('"').strip("'")
    if not s or s == "*":
        return True, "empty_or_star"
    if s.startswith("=") and len(s) > 1:
        return False, "exact_eq_prefix"
    if any(x in s for x in ("^", "~", "*", ",", ">", "<")):
        return True, "cargo_range_or_wildcard"
    if re.match(r"^[\d.]+$", s):
        return True, "cargo_default_compatible_release"
    return True, "other"


def _cargo_dep_entry_loose(name: str, value: Any) -> tuple[bool, str, str]:
    if isinstance(value, str):
        loose, code = _cargo_version_loose(value)
        return loose, value, code
    if isinstance(value, dict):
        if "path" in value or "git" in value:
            ref = value.get("branch") or value.get("tag") or value.get("rev")
            if value.get("git") and ref in (None, "main", "master", "HEAD"):
                return True, str(value)[:160], "git_floating_ref"
            return False, str(value)[:120], "path_or_git_pinned"
        ver = value.get("version")
        if isinstance(ver, str):
            loose, code = _cargo_version_loose(ver)
            return loose, ver, code
        return True, str(value)[:120], "complex_table"
    return True, str(type(value).__name__), "unknown"


def _scan_cargo_dep_blocks(
    data: dict[str, Any],
    issues: list[dict[str, Any]],
    section_prefix: str,
) -> None:
    for sec in ("dependencies", "dev-dependencies", "build-dependencies"):
        block = data.get(sec)
        if not isinstance(block, dict):
            continue
        full_sec = f"{section_prefix}.{sec}" if section_prefix else sec
        for name, val in block.items():
            if name in ("workspace",) or name.replace("-", "_") == "cfg":
                continue
            loose, disp, code = _cargo_dep_entry_loose(name, val)
            if loose:
                issues.append(
                    {
                        "name": name,
                        "section": full_sec,
                        "specifier": disp[:200],
                        "reason": code,
                        "detail": "Cargo treats bare versions as compatible ranges unless prefixed with =.",
                    }
                )


def analyze_cargo_toml(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        return {
            "file": str(path),
            "kind": "Cargo.toml",
            "error": str(e)[:200],
            "issues": [],
        }
    _scan_cargo_dep_blocks(data, issues, "")
    targets = data.get("target")
    if isinstance(targets, dict):
        for tname, tdata in targets.items():
            if isinstance(tdata, dict):
                _scan_cargo_dep_blocks(tdata, issues, f"target.{tname}")
    return {"file": str(path), "kind": "Cargo.toml", "issues": issues, "error": None}


def _gem_args_loose(args_raw: str | None) -> tuple[bool, str, str]:
    if not args_raw or not args_raw.strip():
        return True, "", "no_version_constraint"
    s = args_raw.strip()
    if "~>" in s or ">=" in s or "<=" in s or ">" in s or "<" in s:
        if re.search(r"['\"]\s*(\d+\.\d+\.\d+)\s*['\"]", s) and "~>" not in s and ">=" not in s:
            pass
        return True, s[:200], "bundler_range"
    if ":github" in s or ":git" in s or ":branch" in s:
        return True, s[:200], "git_source"
    m = re.search(r"['\"]([\d.]+[^'\"]*)['\"]", s)
    if m and re.match(r"^[\d.]+$", m.group(1).split()[0]):
        return False, s[:200], "exact_gem_version"
    return True, s[:200], "complex_or_loose"


def analyze_gemfile(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return {
            "file": str(path),
            "kind": "Gemfile",
            "error": str(e)[:200],
            "issues": [],
        }
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.lower().startswith("gem "):
            continue
        m = re.match(
            r'^\s*gem\s+([\'"])([^\'"]+)\1(?:\s*,\s*(.+))?',
            stripped,
            re.I,
        )
        if not m:
            continue
        name, rest = m.group(2), m.group(3)
        loose, disp, code = _gem_args_loose(rest)
        if loose:
            issues.append(
                {
                    "line": i,
                    "name": name,
                    "specifier": disp,
                    "reason": code,
                    "detail": "Bundler/Gemfile: ranges, git, or missing second arg allow drift.",
                }
            )
    return {"file": str(path), "kind": "Gemfile", "issues": issues, "error": None}


def analyze_go_mod(path: Path) -> dict[str, Any]:
    """Go records chosen module versions (minimum version selection), not npm-style ranges."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {
            "file": str(path),
            "kind": "go.mod",
            "error": str(e)[:200],
            "issues": [],
        }
    issues: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.lower().startswith("replace "):
            if "=>" in s and ("*" in s or " latest" in s.lower()):
                issues.append(
                    {
                        "line": i,
                        "raw": s[:200],
                        "reason": "replace_wildcard",
                        "detail": "Unusual replace directive; verify pinned replacement.",
                    }
                )
    return {
        "file": str(path),
        "kind": "go.mod",
        "issues": issues,
        "error": None,
        "note": (
            "Go modules list resolved minimum versions, not semver ranges like npm. "
            "Use this file with `go.sum` for reproducibility; `go get -u` changes selections."
        ),
    }


def _maven_version_loose(ver: str) -> tuple[bool, str]:
    v = (ver or "").strip()
    if not v:
        return True, "missing_version"
    if v.startswith("${") and v.endswith("}"):
        return True, "property_reference"
    up = v.upper()
    if up in ("LATEST", "RELEASE"):
        return True, "floating_meta_version"
    if "[" in v or "(" in v:
        return True, "version_range"
    if re.match(r"^\d", v) or v.startswith("["):
        return False, "literal_version"
    return True, "unclassified"


def analyze_pom_xml(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError) as e:
        return {
            "file": str(path),
            "kind": "pom.xml",
            "error": str(e)[:200],
            "issues": [],
        }
    for dep in root.iter():
        if _xml_local(dep.tag) != "dependency":
            continue
        gid = art = ver = None
        for child in dep:
            ln = _xml_local(child.tag)
            t = (child.text or "").strip()
            if ln == "groupId":
                gid = t
            elif ln == "artifactId":
                art = t
            elif ln == "version":
                ver = t
        if not art:
            continue
        loose, code = _maven_version_loose(ver or "")
        if loose:
            issues.append(
                {
                    "name": f"{gid or '?'}:{art}",
                    "specifier": ver or "",
                    "reason": code,
                    "detail": "Maven: prefer explicit release versions or BOM-managed pins you control.",
                }
            )
    return {"file": str(path), "kind": "pom.xml", "issues": issues, "error": None}


_GRADLE_DEPS_GROOVY = re.compile(
    r"(?:implementation|api|compileOnly|runtimeOnly|testImplementation|"
    r"androidTestImplementation|compile)\s+['\"]([^'\"]+):([^'\"]+):([^'\"]+)['\"]"
)
_GRADLE_DEPS_KOTLIN = re.compile(
    r"(?:implementation|api|compileOnly|runtimeOnly|testImplementation)\s*\(\s*"
    r"\"([^\"]+):([^\"]+):([^\"]+)\"\s*\)"
)


def _gradle_version_loose(ver: str) -> tuple[bool, str]:
    v = ver.strip()
    if not v or v in ("+", "*", "latest.release"):
        return True, "dynamic_or_empty"
    if v.endswith("+") or ".+" in v:
        return True, "plus_suffix_latest_minor"
    if "[" in v or "(" in v:
        return True, "range"
    return False, "fixed"


def analyze_gradle(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {
            "file": str(path),
            "kind": path.name,
            "error": str(e)[:200],
            "issues": [],
        }
    for m in _GRADLE_DEPS_GROOVY.finditer(text):
        g, a, v = m.group(1), m.group(2), m.group(3)
        loose, code = _gradle_version_loose(v)
        if loose:
            issues.append(
                {
                    "name": f"{g}:{a}",
                    "specifier": v,
                    "reason": code,
                    "detail": "Gradle dynamic or ranged coordinates allow newer artifacts.",
                }
            )
    for m in _GRADLE_DEPS_KOTLIN.finditer(text):
        g, a, v = m.group(1), m.group(2), m.group(3)
        loose, code = _gradle_version_loose(v)
        if loose:
            issues.append(
                {
                    "name": f"{g}:{a}",
                    "specifier": v,
                    "reason": code,
                    "detail": "Gradle Kotlin DSL: dynamic or ranged coordinates.",
                }
            )
    return {"file": str(path), "kind": path.name, "issues": issues, "error": None}


def analyze_csproj(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError) as e:
        return {
            "file": str(path),
            "kind": "csproj",
            "error": str(e)[:200],
            "issues": [],
        }
    for elem in root.iter():
        if _xml_local(elem.tag) != "PackageReference":
            continue
        pkg = elem.attrib.get("Include") or elem.attrib.get("Update")
        ver = elem.attrib.get("Version") or elem.attrib.get("VersionOverride")
        if not pkg:
            continue
        if not ver or not ver.strip():
            issues.append(
                {
                    "name": pkg,
                    "specifier": "",
                    "reason": "missing_version",
                    "detail": "Central package management or SDK may supply version; confirm explicitly for pinning.",
                }
            )
            continue
        v = ver.strip()
        if v in ("*", "latest", "floating"):
            issues.append(
                {
                    "name": pkg,
                    "specifier": v,
                    "reason": "floating_version",
                    "detail": "NuGet floating or wildcard version.",
                }
            )
            continue
        if "*" in v:
            issues.append(
                {
                    "name": pkg,
                    "specifier": v,
                    "reason": "wildcard",
                    "detail": "Wildcard allows multiple matching versions.",
                }
            )
    return {"file": str(path), "kind": "csproj", "issues": issues, "error": None}


def _conda_spec_loose(spec: str) -> tuple[bool, str]:
    s = spec.strip()
    if not s or s.startswith("#"):
        return False, "skip"
    if any(op in s for op in (">=", "<=", ">", "<", "~")):
        return True, "conda_range"
    if "=" in s:
        return False, "conda_eq_pin"
    return True, "conda_unpinned_name_only"


def analyze_pubspec_yaml(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except (yaml.YAMLError, OSError) as e:
        return {
            "file": str(path),
            "kind": "pubspec.yaml",
            "error": str(e)[:200],
            "issues": [],
        }
    if not isinstance(data, dict):
        return {"file": str(path), "kind": "pubspec.yaml", "issues": [], "error": None}
    for section in ("dependencies", "dev_dependencies"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            if name == "flutter" and isinstance(spec, dict) and "sdk" in spec:
                continue
            if isinstance(spec, dict):
                ver = spec.get("version")
                if isinstance(ver, str):
                    loose, code = _npm_spec_issue(ver)
                    if loose:
                        issues.append(
                            {
                                "name": name,
                                "section": section,
                                "specifier": ver,
                                "reason": code,
                                "detail": "Pub dependency map with loose version.",
                            }
                        )
                else:
                    issues.append(
                        {
                            "name": name,
                            "section": section,
                            "specifier": str(spec)[:200],
                            "reason": "complex_spec",
                            "detail": "Path/git/sdk-style entry; verify pin or lockfile.",
                        }
                    )
            elif isinstance(spec, str):
                loose, code = _npm_spec_issue(spec)
                if loose:
                    issues.append(
                        {
                            "name": name,
                            "section": section,
                            "specifier": spec,
                            "reason": code,
                            "detail": "Pub uses similar constraints to npm for semver.",
                        }
                    )
    return {"file": str(path), "kind": "pubspec.yaml", "issues": issues, "error": None}


def analyze_conda_environment_yml(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except (yaml.YAMLError, OSError) as e:
        return {
            "file": str(path),
            "kind": path.name,
            "error": str(e)[:200],
            "issues": [],
        }
    if not isinstance(data, dict):
        return {"file": str(path), "kind": path.name, "issues": [], "error": None}
    deps = data.get("dependencies")
    if isinstance(deps, list):
        for i, entry in enumerate(deps):
            if isinstance(entry, str):
                loose, code = _conda_spec_loose(entry)
                if loose and code != "skip":
                    issues.append(
                        {
                            "line_hint": i,
                            "raw": entry[:200],
                            "reason": code,
                            "detail": "Conda env package spec.",
                        }
                    )
            elif isinstance(entry, dict) and "pip" in entry:
                pip_list = entry.get("pip")
                if isinstance(pip_list, list):
                    for raw in pip_list:
                        if isinstance(raw, str):
                            loose, disp, code = _pep508_loose(raw)
                            if loose and code != "skip":
                                issues.append(
                                    {
                                        "section": "dependencies.pip",
                                        "raw": disp[:200],
                                        "reason": code,
                                        "detail": "Embedded pip requirement in conda env.",
                                    }
                                )
    return {"file": str(path), "kind": path.name, "issues": issues, "error": None}


_MIX_DEP_RE = re.compile(
    r"\{:(\w+)\s*,\s*([^}]+)\}",
)


def _mix_tuple_loose(inner: str) -> tuple[bool, str, str]:
    s = inner.strip()
    if s.startswith(":"):
        return True, s[:200], "atom_only"
    if "~>" in s or ">=" in s or "git:" in s or "github:" in s:
        return True, s[:200], "range_or_git"
    m = re.match(r'^["\']([^"\']+)["\']', s)
    if m and re.match(r"^[\d.]+$", m.group(1)):
        return False, s[:200], "exact_version_string"
    return True, s[:200], "mix_complex"


def analyze_mix_exs(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {
            "file": str(path),
            "kind": "mix.exs",
            "error": str(e)[:200],
            "issues": [],
        }
    in_deps = False
    for i, line in enumerate(text.splitlines(), 1):
        if re.match(r"^\s*defp\s+deps\s+do\s*$", line):
            in_deps = True
            continue
        if in_deps and re.match(r"^\s*end\s*$", line):
            break
        if not in_deps:
            continue
        for m in _MIX_DEP_RE.finditer(line):
            name, inner = m.group(1), m.group(2)
            loose, disp, code = _mix_tuple_loose(inner)
            if loose:
                issues.append(
                    {
                        "line": i,
                        "name": name,
                        "specifier": disp,
                        "reason": code,
                        "detail": "Mix deps tuple heuristic; verify mix.lock.",
                    }
                )
    return {"file": str(path), "kind": "mix.exs", "issues": issues, "error": None}


def analyze_package_swift(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {
            "file": str(path),
            "kind": "Package.swift",
            "error": str(e)[:200],
            "issues": [],
        }
    if re.search(
        r'\.branch\s*\(\s*"(?:main|master|develop|HEAD)"\s*\)',
        text,
        re.I,
    ):
        issues.append(
            {
                "reason": "swift_common_branch",
                "detail": "Floating Git branch; pin to a revision SHA for reproducibility.",
            }
        )
    for m in re.finditer(r'from:\s*"([^"]+)"', text):
        issues.append(
            {
                "specifier": m.group(1),
                "reason": "swift_package_from_range",
                "detail": "SwiftPM `from:` selects a range up to the next major, not a single exact version.",
            }
        )
    return {"file": str(path), "kind": "Package.swift", "issues": issues, "error": None}


def analyze_manifest(path: Path) -> dict[str, Any]:
    name = path.name
    if name == "package.json":
        return analyze_package_json(path)
    if name == "composer.json":
        return analyze_composer_json(path)
    if name == "Cargo.toml":
        return analyze_cargo_toml(path)
    if name == "Gemfile":
        return analyze_gemfile(path)
    if name == "go.mod":
        return analyze_go_mod(path)
    if name == "pom.xml":
        return analyze_pom_xml(path)
    if name in ("build.gradle", "build.gradle.kts"):
        return analyze_gradle(path)
    if name.endswith(".csproj"):
        return analyze_csproj(path)
    if name == "pubspec.yaml":
        return analyze_pubspec_yaml(path)
    if name in ("environment.yml", "conda.yml"):
        return analyze_conda_environment_yml(path)
    if name == "mix.exs":
        return analyze_mix_exs(path)
    if name == "Package.swift":
        return analyze_package_swift(path)
    if name == "Pipfile":
        return analyze_pipfile(path)
    if name == "pyproject.toml":
        return analyze_pyproject_toml(path)
    if name.endswith(".txt") and (
        name == "requirements.txt"
        or name.startswith("requirements")
        or name == "constraints.txt"
    ):
        return analyze_requirements_txt(path)
    return {"file": str(path), "kind": name, "issues": [], "error": "unsupported"}


def scan_dependency_pinning(
    search_root: str | Path = ".",
    max_depth: int = 8,
) -> dict[str, Any]:
    """
    Walk ``search_root`` for supported manifests and list unpinned / loosely pinned deps.

    ``search_root`` defaults to the process current working directory (typical MCP / IDE cwd).
    """
    root = Path(search_root).expanduser()
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()
    else:
        root = root.resolve()

    if not root.is_dir():
        return {
            "search_root": str(root),
            "error": "search_root is not a directory",
            "manifests_scanned": [],
            "summary": {},
        }

    paths = iter_manifest_files(root, max_depth=max_depth)
    reports: list[dict[str, Any]] = []
    total_issues = 0
    for p in paths:
        rep = analyze_manifest(p)
        reports.append(rep)
        total_issues += len(rep.get("issues") or [])

    by_kind: dict[str, int] = {}
    for r in reports:
        k = r.get("kind") or "unknown"
        by_kind[k] = by_kind.get(k, 0) + 1

    return {
        "search_root": str(root),
        "max_depth": max_depth,
        "manifest_paths_found": [str(p) for p in paths],
        "manifests_scanned": len(paths),
        "reports": reports,
        "loose_or_unpinned_issue_count": total_issues,
        "summary": {
            "files_by_kind": by_kind,
            "supported_manifests": sorted(MANIFEST_FILENAMES)
            + [ "*.csproj", "requirements-*.txt" ],
            "note": (
                "Issues list dependencies that are not pinned to an exact version (e.g. npm ==, "
                "PEP 508 ==, Cargo =, Maven literal) or that use ranges/tags/wildcards. "
                "Ecosystems: npm/package.json, Composer, Cargo, Bundler/Gemfile, Go (go.mod note), "
                "Maven (pom.xml), Gradle, NuGet (.csproj), Pub (pubspec.yaml), Conda (environment.yml), "
                "Mix (mix.exs), SwiftPM (Package.swift), Pip/Poetry/PDM/PEP 735 (pyproject), Pipenv, pip requirements. "
                "Commit lockfiles (package-lock, poetry.lock, Cargo.lock, mix.lock, go.sum, etc.) for reproducible installs."
            ),
        },
    }
