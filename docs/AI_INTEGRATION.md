# AI Integration

AI is a planned subsystem, not a prerequisite for the product to function.

## Initial Provider Targets

- Ollama
- OpenAI-compatible APIs

## Architecture Rules

- Provider access goes through adapters behind a common abstraction.
- Core domain code should request capabilities, not provider-specific APIs.
- Secrets and provider credentials must never be logged.
- AI outputs should be treated as suggestions or intermediate results, not authoritative truth.

## Likely Use Cases

- Product normalization from imports.
- Recipe and pantry matching assistance.
- Shopping suggestions.
- Summaries of pantry state or expiring items.

## Not Built Yet

- Provider config UI.
- Prompt libraries.
- Async AI job orchestration.
- Plan-aware rate limits.

