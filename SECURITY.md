# Security policy

We take security reports seriously. Please **do not** file exploitable vulnerabilities as **public GitHub issues**, and do not disclose details publicly until maintainers have had a reasonable time to address the problem.

---

## Reporting a vulnerability

### Preferred: GitHub private vulnerability reporting

If this repository has **[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)** enabled, use it:

1. Open the repository on GitHub.
2. Go to **Security** → **Report a vulnerability** (wording may vary slightly).
3. Submit a **private** advisory with the details below.

This keeps the report visible only to maintainers and GitHub until you agree to publish or disclose.

### If private reporting is not available

Contact the **repository maintainers** through a **non-public** channel they publish for security (for example a security email or org process). If none is listed, you may open a **generic issue** asking *only* for a secure contact method—**without** including exploit details in the public thread.

---

## What to include

Helpful reports usually contain:

- **Description** of the issue and its **impact** (confidentiality, integrity, availability, supply chain, etc.).
- **Affected component** (e.g. MCP tool, HTTP surface, Docker image) and **version or commit** if known.
- **Steps to reproduce** or a **proof of concept** where safe and appropriate.
- **Suggested fix** or mitigation, if you have one (optional).

---

## Scope (illustrative)

Reports are in scope when they concern **this project’s code, configuration, or documented deployment**—for example:

- The MCP server process, its tools, or parsing/HTTP handling that could lead to unintended behavior or exposure.
- **Remote deployments** (e.g. public HTTP MCP endpoints) where authentication, authorization, or network exposure is misconfigured **as shipped or documented** in this repository.

Out of scope for *this* policy (report to the relevant vendor instead):

- Vulnerabilities in **third-party dependencies** unless the issue is specific to **how this project uses** them.
- **Social engineering**, physical access, or **user misconfiguration** that contradicts documented security guidance.
- **Denial of service** via resource exhaustion may be considered on a case-by-case basis.

Maintainers may refine scope over time; when in doubt, report privately.

---

## Supported versions

Security fixes are generally applied to the **latest development state on the default branch** and, when applicable, documented for **released versions**. If you rely on an older install, say so in your report.

---

## Response and disclosure

- We aim to **acknowledge** receipt of valid reports within **a few business days** (this is a goal, not a guarantee for small or volunteer-maintained projects).
- We will work toward a **fix or mitigation** and coordinate **disclosure** with you when possible (coordinated disclosure). Please allow time for patching and user notification before public discussion.
- You may receive credit in an advisory or release notes if you wish; say so in your report.

---

## Safe harbor

We will not pursue legal action against researchers who make a **good-faith effort** to follow this policy: report privately first, avoid privacy violations and data destruction, and do not disrupt services beyond what is necessary to demonstrate the issue.

---

## Additional resources

- [GitHub: Privately reporting a security vulnerability](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
- [GitHub: Adding a security policy to your repository](https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository)
- **[README_flyio.md](README_flyio.md)** — deployment and exposure considerations for this server

For general contributions and non-sensitive bugs, see **[CONTRIBUTING.md](CONTRIBUTING.md)**.
