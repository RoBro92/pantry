# Settings Model

Pantry needs configuration at multiple levels.

## Configuration Layers

- Deployment-level settings from environment variables.
- Platform-level settings for installation-wide behavior.
- Household-level settings for preferences and feature availability.
- User-level settings for UI and workflow preferences.

## Examples

- Deployment level: database URL, Redis URL, base URLs, log level.
- Platform level: default feature flags, allowed deployment mode, bootstrap behavior, public browser URL, SMTP foundation, and instance AI provider configuration.
- Household level: pantry conventions, future AI provider override policy, and import defaults.
- User level: preferred units, dashboard ordering, notification preferences.

## Current Instance-Level Settings

- AI provider configuration is stored in the database at installation scope.
- Public/browser base URL is stored in the database and used for generated browser links such as location QR codes.
- SMTP foundation settings are stored in the database at installation scope with password redaction and encrypted-at-rest storage.

## Precedence

- `PUBLIC_BROWSER_BASE_URL` overrides the saved instance public URL when it is set.
- `SMTP_HOST` and related `SMTP_*` environment variables override the saved instance SMTP configuration when `SMTP_HOST` is set.
- If no public browser URL override exists, generated browser links fall back to the saved platform value, then to `WEB_APP_URL`.
- The admin UI still shows the saved database values even when environment variables are currently taking precedence.

## Sensitive Settings

- Provider credentials and secrets require redaction in logs.
- Future UI for sensitive settings should avoid exposing raw secret values after initial entry.
- The current AI provider foundation encrypts stored provider secrets at rest using `SETTINGS_ENCRYPTION_KEY` when provided, otherwise a derived key from `SESSION_SECRET_KEY` for self-hosted defaults.
- Stored SMTP passwords follow the same encrypted-at-rest pattern and are only exposed back through boolean readiness fields such as `has_password`.
