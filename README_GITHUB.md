# GitHub configuration for open source projects

This guide summarizes **recommended GitHub settings and habits** for public repositories, with emphasis on **security** and alignment with **Open Source Security Foundation (OpenSSF)** guidance. It is generic advice; adapt it to your org’s policies and threat model.

For automated checks against a **GitHub repo**, the OpenSSF **Scorecard** API is one signal among many; this repo’s MCP server can query it via **`check_openssf_scorecard`** (see **[README_TOOLS.md](README_TOOLS.md)**).

---

## 1. Repository basics

| Practice | Why |
|----------|-----|
| **Clear README** | Explains what the project does, how to install/run, and where to get help. |
| **Open source license** | Use a standard SPDX license (e.g. MIT, Apache-2.0) via `LICENSE` in the root; set the license in the repo **About** metadata. |
| **CODE_OF_CONDUCT.md** | Sets expectations for community behavior; many foundations expect one. |
| **CONTRIBUTING.md** | How to report issues, propose changes, run tests, and follow commit/PR conventions. |

These support **discoverability, legal clarity, and healthy collaboration**—themes reflected in OpenSSF **Scorecard** checks such as **License** and **Maintained**.

---

## 2. Security policy and responsible disclosure

| Practice | Why |
|----------|-----|
| **`SECURITY.md`** in the root | Documents **how to report vulnerabilities privately** (email, form, or GitHub **Security Advisories**), expected response times, and supported versions. |
| Enable **private vulnerability reporting** (repo **Settings → Security** → *Private vulnerability reporting*) | Lets researchers report without public issues; aligns with **Coordinated vulnerability disclosure** practice. |
| **Security advisories** for confirmed issues | Publish CVE-ready advisories when appropriate; helps consumers patch and scanners attribute risk. |

OpenSSF and industry guidance stress **not** fixing serious issues only in silence—balance transparency with a short private window.

---

## 3. Branch protection and review (supply chain hygiene)

| Practice | Why |
|----------|-----|
| **Protect default branch** | Require **pull requests** for changes; avoid direct pushes that bypass review. |
| **Required reviews** | At least one (or two, for critical repos) approval from people who understand the code. |
| **Dismiss stale reviews** when new commits are pushed | Prevents merging on an outdated approval. |
| **Require status checks** to pass before merge | CI (tests, lint, build) must be green. |
| **Require linear history** or **merge queues** (optional) | Reduces accidental merge complexity; queues help high-churn repos. |
| **Restrict who can push** to protected branches | Limits who can bypass rules (ideally **no one** for the default branch). |
| **Signed commits** (optional but strong) | Proves authorship; GPG or SSH signing; orgs can **require verified signatures**. |

These map closely to Scorecard checks such as **Branch-Protection** and **Code-Review**.

### Branch layout and workflow (best practices)

| Practice | Notes |
|----------|--------|
| **Default branch (`main` / `master`)** | Treat as the **integration line**: reviewed, CI-clean work lands here. Protect it; prefer **PR + merge** over direct pushes for contributors. |
| **Topic branches** | One logical change when possible. Name clearly: `fix/…`, `feat/…`, `docs/…`, `chore/…`, or `issue-123-short-slug`. Branch from an **up-to-date** default branch. |
| **After merge** | Delete remote topic branches to reduce clutter (GitHub: *Automatically delete head branches*). |
| **Release branches** | Optional **`release/x.y`** (or similar) when you must **patch older lines** while default moves forward. Ship from **tags** (`v1.2.3`) with release notes. |
| **Long-lived `develop`** | Optional second integration branch (develop → default). Many small OSS projects skip this and use only the default branch. |
| **Docs / Pages** | **`gh-pages`** or a **docs** branch only if your publishing model needs it; otherwise keep docs on the default branch (or publish via Actions from default). |
| **Automation** | Treat **Dependabot** (and similar) PRs like other contributions: review and merge through the same protections. |
| **Avoid** | Force-pushing **shared** branches without agreement; one eternal branch for many unrelated features; **secrets** on any branch (use secrets / env, not commits). |

### GitHub branch protections (detailed reference)

GitHub implements protections through **classic branch protection rules** (per branch pattern) and **rulesets** (targets, bypass lists, enforcement). Labels in the UI can change slightly; the capabilities below are the ones teams usually configure.

#### Classic branch protection rules

**Pull requests**

| Option | Effect |
|--------|--------|
| **Require a pull request before merging** | Changes to the branch must go through a PR (subject to bypass lists, if any). |
| **Required approving review count** | e.g. one or two approvals before merge. |
| **Dismiss stale pull request approvals when new commits are pushed** | Prior approvals do not count after new commits on the PR branch. |
| **Require review from Code Owners** | Uses **`CODEOWNERS`** so relevant owners approve touched paths. |
| **Restrict who can dismiss pull request reviews** | Limits who can clear review state. |
| **Require approval of the most recent reviewable push** | When enabled, adds a check that the latest push was reviewed (stricter workflow). |

**Status checks**

| Option | Effect |
|--------|--------|
| **Require status checks to pass before merging** | Selected CI checks must succeed. |
| **Require branches to be up to date before merging** | PR branch must incorporate latest default before merge (stricter than “green on last push”). |

**Conversation, history, queue**

| Option | Effect |
|--------|--------|
| **Require conversation resolution before merging** | All review threads must be resolved. |
| **Require linear history** | Enforces a linear graph (policy depends on allowed merge methods: squash/rebase/restrict merge commits). |
| **Require merge queue** | Merges go through a queue that re-validates against the latest default (useful for busy repos). |

**Integrity and lifecycle**

| Option | Effect |
|--------|--------|
| **Require signed commits** | Only verified (GPG/SSH) commits allowed, when you enforce signing. |
| **Lock branch** | Branch becomes read-only (emergency or archive scenarios). |
| **Restrict who can push to matching branches** | Narrows who may push directly (often **no one** on default). |

**Risky exceptions (usually off on default)**

| Option | Effect |
|--------|--------|
| **Allow force pushes** | If on, typically limited to specific roles; usually **off** on default. |
| **Allow deletions** | Usually **off** on default. |
| **Bypass rules** | Prefer **enforcing the same rules for administrators** when your threat model allows—so admins cannot silently bypass protection. |

#### Rulesets (repository or organization)

**Rulesets** attach **rules** to **targets** (branch names, tags, refs) with explicit **enforcement** (active, evaluate/audit, disabled) and **bypass** actors.

Common rule types include:

- Restrict or block **creation**, **update**, or **deletion** of matching refs.
- **Require a pull request** (with required reviews, Code Owners, etc.).
- **Required status checks** (and optional “up to date” behavior).
- **Require linear history** / **merge queue** (depending on configuration).
- **Require signed commits**.
- **Block force pushes** explicitly.
- **Require deployments** to succeed (environment gates) before merge, when configured.

Use **rulesets** when you need consistent policy across many branches or repos; use **classic rules** when a single branch pattern is enough.

#### Practical default for public OSS

On the **default branch**: require PRs, **≥1** approval, **dismiss stale reviews**, **required CI checks**, **up to date** if you can afford the friction, **no force-push**, **no branch delete**, admins **not** bypassing when feasible. Add **merge queue** or **signed commits** as the project matures.

---

## 4. Dependencies and automated updates

| Practice | Why |
|----------|-----|
| **Dependabot version updates** | Opens PRs for outdated dependencies; keeps the tree fresher. |
| **Dependabot security updates** | Faster path to patched versions when GitHub alerts exist. |
| **Pin dependencies** where it matters | Lockfiles (npm, Poetry, etc.) and reproducible builds reduce “floating” supply-chain drift. For app-level repos, prefer explicit versions or lockfiles over unbounded ranges. |
| **Review dependency PRs** | Auto-merge without review can be risky; use policies that fit your risk tolerance. |

Scorecard’s **Dependency-Update-Tool** check rewards enabled update automation; your own pinning posture can be reviewed with tooling (e.g. **`check_dependency_version_pinning`** in this repo’s MCP server).

---

## 5. GitHub Actions and CI/CD security

| Practice | Why |
|----------|-----|
| **`actions/checkout` and third-party actions: pin by commit SHA** | Tags can be moved; full SHA is more tamper-evident. |
| **Minimal `GITHUB_TOKEN` permissions** | Default to read-only; grant `contents: write` only where needed; avoid `write-all`. |
| **Separate environments for deploy secrets** | Use **environments** with required reviewers for production credentials. |
| **Never commit secrets** | Use **GitHub Secrets** (and OIDC to cloud where possible) instead of tokens in workflow YAML or repo files. |
| **Fork PR workflows** | Use `pull_request_target` only when you understand the risk; prefer `pull_request` from same-repo branches or trusted patterns. |

OpenSSF **Secure Software Development Framework (SSDF)** and **SLSA**-adjacent guidance emphasize **least privilege** and **hermetic, reviewable** build steps—your Actions config is part of that surface.

---

## 6. Secret scanning and push protection

| Practice | Why |
|----------|-----|
| **Secret scanning** (enabled for public repos on GitHub.com) | Detects known secret patterns in history and notifies you. |
| **Push protection** | Blocks commits that contain detected secrets before they land on GitHub. |

Rotate any credential that was ever exposed in git history; removing the commit is not enough if the secret was pushed or mirrored.

---

## 7. Two-factor authentication and org hygiene

| Practice | Why |
|----------|-----|
| **2FA for all maintainers** | Reduces account takeover → malicious releases or repo changes. |
| **Org-level 2FA requirement** (if applicable) | Enforces the baseline for every member. |
| **Least-privilege collaborators** | Admin access only for people who need it; use teams for permissions. |
| **Audit **who** can publish packages** (npm, PyPI, etc.) | GitHub is only one piece; registry tokens and OIDC trust must match your release story. |

Scorecard includes **Token-Permissions** and related signals for workflows; org policies complement repo settings.

---

## 8. Releases and provenance

| Practice | Why |
|----------|-----|
| **Signed tags or signed release artifacts** | Helps consumers verify integrity (GPG, Sigstore/cosign, or platform-native signing). |
| **Release notes** | Document breaking changes and security fixes; link to advisories when relevant. |
| **SLSA provenance** (optional, advanced) | Attestations that describe how artifacts were built; increasingly used in enterprise consumption policies. |

---

## 9. OpenSSF alignment (what to read next)

| Resource | Use |
|----------|-----|
| **[OpenSSF Scorecard](https://scorecard.dev/)** | Understand which checks apply to your repo and how they are scored. |
| **[OpenSSF Best Practices / guides](https://best.openssf.org/)** | Curated patterns for maintainers and consumers (including supply chain). |
| **SSDF (NIST SP 800-218)** | High-level secure development activities; map GitHub settings and CI to those activities. |

Scorecard is **not** a complete security audit; treat it as a **gap finder** and **policy nudge**, then fix findings with engineering judgment.

---

## 10. Quick checklist (default branch + security)

- [ ] `LICENSE`, `README`, `CONTRIBUTING`, `CODE_OF_CONDUCT` (as appropriate)
- [ ] `SECURITY.md` + private vulnerability reporting
- [ ] Branch protection: PR required, reviews required, status checks required
- [ ] Dependabot (security + version updates) configured
- [ ] Actions: pinned actions, minimal tokens, secrets in **Secrets**, not in files
- [ ] Secret scanning + push protection on
- [ ] Maintainer 2FA; limited admin access
- [ ] Release process documented; consider signing

---

## Related documentation in this repository

| Doc | Topic |
|-----|--------|
| **[README_MCP.md](README_MCP.md)** | Running the MCP server (optional `GITHUB_TOKEN` for API rate limits) |
| **[README_TOOLS.md](README_TOOLS.md)** | `check_openssf_scorecard`, `find_package_github_repository`, and related tools |
