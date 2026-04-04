# Future Scope

Pantry should continue separating near-term self-hosted completion work from later hosted-only work.

## Planned Self-Hosted Expansion

- Shopping workflows and pantry-to-shopping capture from recipes.
- UI, accessibility, and interaction refinement after the current hardening pass.
- Release/version/update workflow using GitHub Releases and GHCR.
- Admin-visible update-available notification for self-hosted operators.
- Production deployment guidance for Docker-based installs and LXC-hosted infrastructure.
- Stronger backup, restore, and upgrade guidance for production self-hosting.
- Richer import pipeline work such as OCR and deeper parsing after the release path is stable.

## Later-Stage Hosted Expansion

- SaaS tenant lifecycle, billing, and hosted plan management.
- Managed onboarding, backups, and support workflows.
- Recipe intelligence, meal planning, and shopping suggestions.
- Notification channels such as email or mobile push.
- Feature-flag-driven plan differences across `demo` and future hosted `saas` capabilities.
- Platform-level analytics and usage metering for hosted tiers.

## Deliberate Constraints Today

- No SaaS-only operational docs in the public tree.
- No hosted-only billing, support, or control-plane code in the public repo.
- No self-hosted auto-updater; operators remain responsible for manual upgrades.
- No provider-specific AI logic in domain services.
