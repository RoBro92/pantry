# File Map

## Root

- `VERSION`: canonical application version.
- `compose.yml`: local development stack.
- `.env.example`: environment variable template.
- `AGENTS.md`: repo-specific agent rules.
- `README.md`: project overview and local setup.

## Applications

- `apps/web/`: Next.js frontend scaffold.
- `apps/api/`: FastAPI backend scaffold.
- `apps/worker/`: Python worker scaffold.

## Packages

- `packages/shared-types/`: shared TypeScript constants for deployment modes, roles, and domain entities.

## Infrastructure

- `infra/docker/`: Dockerfiles for web, API, and worker.
- `infra/scripts/`: small repository utility scripts such as version helpers.

## Documentation

- `docs/PROJECT_STATE.md`: latest implementation state and next recommended step.
- `docs/MILESTONES.md`: roadmap.
- `docs/ARCHITECTURE.md`: high-level technical shape.
- `docs/DOMAIN_MODEL.md`: initial entity definitions.
- `docs/SECURITY.md`: security posture and guardrails.

## Local-Only

- `private-docs/`: gitignored space for SaaS operations or private runbooks.

