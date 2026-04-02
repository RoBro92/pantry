# Settings Model

Pantry needs configuration at multiple levels.

## Configuration Layers

- Deployment-level settings from environment variables.
- Platform-level settings for installation-wide behavior.
- Household-level settings for preferences and feature availability.
- User-level settings for UI and workflow preferences.

## Examples

- Deployment level: database URL, Redis URL, base URLs, log level.
- Platform level: default feature flags, allowed deployment mode, bootstrap behavior.
- Household level: pantry conventions, AI provider policy, import defaults.
- User level: preferred units, dashboard ordering, notification preferences.

## Sensitive Settings

- Provider credentials and secrets require redaction in logs.
- Future UI for sensitive settings should avoid exposing raw secret values after initial entry.

