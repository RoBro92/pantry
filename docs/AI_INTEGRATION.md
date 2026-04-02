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
- AI suggestions must remain advisory and read-only in v1.
- Structured pantry and recipe context should be assembled server-side before prompts are built.
- Household AI routes must resolve tenant access server-side before any provider call happens.

## Current Foundation

- Instance-scoped provider configuration via platform admin routes and a minimal web page.
- Provider adapters for Ollama and OpenAI-compatible chat/structured JSON generation.
- Household AI status and pantry-aware suggestion entrypoints.
- Structured JSON prompt/output contracts for meal ideas, expiry-first ideas, buy-a-few-extra suggestions, and recipe-gap explanation foundations.
- Structured logs for AI request lifecycle plus audit coverage for config saves and user-triggered suggestion activity.

## Likely Use Cases

- Product normalization from imports.
- Recipe and pantry matching assistance.
- Shopping suggestions.
- Summaries of pantry state or expiring items.

## Not Built Yet

- Household override UI and resolution policy.
- Async AI job orchestration in the worker.
- AI-assisted import review flows.
- Full chatbot behavior.
- Usage metering, billing logic, or SaaS-hosted AI execution.
