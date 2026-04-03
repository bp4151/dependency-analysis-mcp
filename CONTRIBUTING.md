# Contributing to Dependency Analysis MCP

Thank you for helping improve this project. These guidelines follow common open-source practice so reviews stay predictable and safe.

---

## Code of conduct

Be respectful and constructive. Assume good intent. Harassment and personal attacks are not acceptable.

If this repository later adopts a formal **Code of Conduct** (for example Contributor Covenant), it will live in `CODE_OF_CONDUCT.md` and takes precedence for community rules.

---

## Before you start

1. **Search existing issues and pull requests** so you do not duplicate work.
2. **Discuss large changes** (new tools, breaking behavior, or broad refactors) in an issue first unless the maintainer has already agreed on direction.
3. **Security issues** — follow **[SECURITY.md](SECURITY.md)**. Do **not** open a public issue for exploitable vulnerabilities. See also **[README_GITHUB.md](README_GITHUB.md)** for broader GitHub security expectations.

---

## Fork and pull request workflow

Contributions from outside the main team usually go through a **fork** on GitHub and a **pull request (PR)** into the upstream repository. If you have **direct push access** to this repo, you may skip the fork and open a PR from a branch on the same remote instead—the steps below still apply except you push to `origin` rather than a personal fork.

Examples below use **`main`** as the default branch name; if this repository uses something else (for example **`master`**), substitute that name in the commands.

### 1. Fork and clone

1. On GitHub, **fork** this repository to your account (Fork button on the repo page).
2. **Clone your fork** locally (replace `YOUR_USERNAME` with your GitHub username):

   ```bash
   git clone https://github.com/YOUR_USERNAME/DependencyAnalysisMcp.git
   cd DependencyAnalysisMcp
   ```

3. Add the **upstream** remote so you can sync with the canonical repo (replace `UPSTREAM_ORG` with the organization or user that owns the original repository):

   ```bash
   git remote add upstream https://github.com/UPSTREAM_ORG/DependencyAnalysisMcp.git
   git fetch upstream
   ```

   Confirm remotes: `git remote -v` should show `origin` (your fork) and `upstream`.

### 2. Branch, implement, commit

1. Start from the latest default branch (often `main`; use whatever this repo uses):

   ```bash
   git checkout main
   git pull upstream main
   git push origin main
   ```

2. Create a **topic branch** with a short, descriptive name:

   ```bash
   git checkout -b fix-nuget-registration-url
   ```

3. Make your changes, commit on that branch, and follow the **[Commit messages](#commit-messages)** guidance.

### 3. Push and open the PR

1. Push the branch to **your fork**:

   ```bash
   git push -u origin fix-nuget-registration-url
   ```

2. On GitHub, open your fork. You should see a prompt to **Compare & pull request**; choose the upstream repository’s default branch as the **base** and your branch as the **compare** branch.
3. Fill in the PR title and description: **what** changed, **why**, and links to related **issues** (`Fixes #123` closes the issue when merged, if that convention is used).
4. Wait for **review**. Push additional commits to the **same branch** to address feedback; they appear on the PR automatically.

### 4. Keep your branch up to date

If the upstream default branch moves while your PR is open, **rebase or merge** it into your branch so the PR stays mergeable:

```bash
git fetch upstream
git checkout fix-nuget-registration-url
git merge upstream/main
# or: git rebase upstream/main
git push origin fix-nuget-registration-url
```

Use **merge** if you prefer a simpler history; use **rebase** if the project prefers a linear history (ask maintainers if unsure). After a rebase that was already pushed, you may need `git push --force-with-lease`—only on **your** topic branch, never on `main`.

---

## Development setup

- **Python 3.11+** (see `requires-python` in `pyproject.toml`).
- Use a **virtual environment**:

  ```bash
  python -m venv .venv
  # Windows
  .venv\Scripts\activate
  # macOS / Linux
  source .venv/bin/activate

  pip install -e .
  ```

- **Smoke test** the server (stdio mode, no `PORT`):

  ```bash
  python -m dependency_analysis_mcp.server
  ```

  The process waits on stdin/stdout; that is expected for MCP. For HTTP mode and deployment details, see **[README_MCP.md](README_MCP.md)** and **[README_flyio.md](README_flyio.md)**.

There is no project test suite in the repository yet. If you add automated tests, document how to run them here and keep them fast and deterministic where possible.

---

## Making changes

### Scope and style

- Prefer **small, focused pull requests** that solve one problem or tell one story.
- **Match the existing code**: naming, structure, error handling, and typing style in `dependency_analysis_mcp/`.
- Follow **PEP 8** in spirit; favor clarity over cleverness.
- **Do not commit secrets** (API keys, tokens, `.env` files with real values). Use environment variables and local-only config.
- **Dependency and supply-chain hygiene**: justify new dependencies; prefer maintained, widely used libraries.

### MCP tools and documentation

If you add or change a tool in `server.py` or behavior in `services.py` / `pinning_scan.py`, update **[README_TOOLS.md](README_TOOLS.md)** so parameters, return shapes, and limits stay accurate.

If you change how users run or configure the server, update the relevant doc (**[README_MCP.md](README_MCP.md)**, **[README_flyio.md](README_flyio.md)**, or **[README_Inspector.md](README_Inspector.md)**).

### Docker and Fly.io

If you change the runtime image or deployment contract, update **`Dockerfile`**, **`fly.toml`**, and **[README_flyio.md](README_flyio.md)** together so build, `PORT`, and health checks remain consistent.

---

## Pull request checklist

- [ ] Explains **what** changed and **why** (PR description or linked issue).
- [ ] Keeps unrelated refactors out of the same PR when possible.
- [ ] Updates **documentation** when behavior or interfaces change (especially `README_TOOLS.md` for tools).
- [ ] Does not introduce **committed secrets** or sensitive local paths.
- [ ] You are comfortable licensing your contribution under the same terms as the project (**[LICENSE](LICENSE)** — MIT).

---

## Commit messages

Clear messages help history and releases. A simple convention many projects use:

- **Present tense, short subject** (about 50 characters): `Fix NuGet registration URL handling`
- Optional **body** for context, breaking changes, or follow-ups.

Conventional Commits (`feat:`, `fix:`, …) are welcome but not required unless maintainers standardize on them.

---

## Licensing

By contributing, you agree that your contributions are licensed under the **MIT License** in **[LICENSE](LICENSE)**, the same as the rest of the project.

---

## Questions

Open a **GitHub issue** for questions that are not security-sensitive, or ask in the discussion channel the maintainers prefer (if listed in **README.md**).
