# Support

Pantry is a self-hosted, operator-managed application. This public repository covers the shipped self-hosted product only.

## Scope

- Pantry is self-hosted and operator-managed
- Pantry does not include SaaS billing, hosted control-plane logic, or other hosted-only product behavior
- AI features are optional and the core product remains usable without them
- Pantry does not auto-update; operators choose when to upgrade

## Getting Help

- Use the public docs in [README.md](README.md), [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), [docs/SECURITY.md](docs/SECURITY.md), and [docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md) first
- Use GitHub issues for bug reports, regressions, documentation fixes, and scoped feature requests
- Use pull requests for focused fixes that stay within the self-hosted product scope

General support is best-effort. Maintainers may prioritize release blockers, regressions, security issues, and documentation gaps over environment-specific hand-holding.

## Bug Reports

Include:

- Pantry version from `VERSION` or the running diagnostics page
- install path used: local dev stack or released self-hosted deployment
- exact reproduction steps
- relevant logs or screenshots with secrets removed
- whether the issue reproduces on the latest release, if you can verify that safely

## Security Issues

Do not file public issues with exploit details, credentials, or sensitive deployment data.

Start with [docs/SECURITY.md](docs/SECURITY.md). If GitHub private vulnerability reporting is enabled for this repository, use that channel. If it is not available, open a minimal public issue that asks for a private contact path without including sensitive details.

## What This Repo Does Not Provide

- hosted Pantry accounts or a managed Pantry service
- automatic upgrades or unattended update support
- support for adding SaaS-only logic to this repository
