# AI Latency Reduction Sprint

## Goal

Deliver the first focused pass on AI latency and token reduction across Pantro's existing self-hosted web product without weakening current AI product intelligence or blocking the later canonical ingredient and product knowledge-base direction.

## In-Scope Deliverables

- Reduce avoidable AI runtime latency in normal user flows by removing repeated provider readiness overhead where safe.
- Trim AI request payloads for household meal suggestions and related suggestion flows without materially reducing useful structured context.
- Tighten product intelligence targeting so broad reprocessing is not the default path for unchanged products.
- Improve lightweight AI diagnostics so Pantro can better expose request duration, token usage when providers report it, health-check reuse, and applied runtime optimizations.
- Keep Open Food Facts advisory enrichment working and preserve existing product intelligence separation from Pantro-owned product records.

## Out Of Scope

- Canonical ingredient schema work.
- Alias mapping tables or canonical match persistence.
- SaaS, billing, hosted control-plane, or native app work.
- Major queue architecture rewrites.
- Broad provider expansion or visible provider-surface changes.
- Broad UX redesign beyond small status or diagnostics clarifications needed to support the sprint.

## Implementation Plan

- Add a runtime health-check reuse path so recent provider health results can be reused during normal AI requests instead of probing on every call.
- Trim meal and suggestion payload builders toward compact, high-signal context:
  - reduce low-value free-text fields,
  - cap recipe candidate detail more aggressively,
  - keep structured signals preferred over long text.
- Tighten product intelligence targeting:
  - filter run targets before queueing,
  - add a stale-only path for selective refreshes,
  - keep current full and single-product paths available.
- Extend AI runtime diagnostics with request timing, provider-reported token usage where available, and optimization metadata for cached health checks and payload trimming.
- Keep changes isolated to service and small UI status layers so self-hosted deployment assumptions stay unchanged.

## Acceptance Criteria

- At least one meaningful source of avoidable AI latency is reduced.
- At least one meaningful source of avoidable token usage is reduced.
- Product intelligence targeting is more selective than before.
- AI latency and cost diagnostics are improved.
- Current AI product intelligence still works.
- Common user flows remain materially intact on desktop and mobile web.
- Self-hosted Docker behaviour remains valid.
- The later canonical ingredient and product knowledge-base direction remains unblocked.

## Files Expected To Change

- `apps/api/app/services/ai_config.py`
- `apps/api/app/services/ai_context.py`
- `apps/api/app/services/ai_meal_context.py`
- `apps/api/app/services/ai_suggestions.py`
- `apps/api/app/services/ai_meal_suggestions.py`
- `apps/api/app/services/ai_providers/base.py`
- `apps/api/app/services/ai_providers/openai.py`
- `apps/api/app/services/ai_providers/openai_compatible.py`
- `apps/api/app/services/ai_providers/claude.py`
- `apps/api/app/services/ai_providers/gemini.py`
- `apps/api/app/services/ai_providers/ollama.py`
- `apps/api/app/services/product_intelligence.py`
- `apps/api/app/services/product_intelligence_runs.py`
- `apps/api/app/schemas/pantry.py`
- `apps/web/components/admin-ai-config-form.tsx`
- `apps/web/components/product-intelligence-run-dialog.tsx`
- relevant API tests

## Canonical Direction Compatibility

This sprint preserves the future canonical ingredient and product database direction by only improving transient AI runtime behaviour, targeting, and observability. It does not introduce canonical schema, alias tables, or new coupling that treats AI or Open Food Facts output as permanent truth. Product enrichment remains advisory, product intelligence remains separately versioned and rerunnable, and payload builders stay replaceable so a later canonical matching layer can reuse or supersede them cleanly.

## Final Cleanup Note

- Restored the mobile shell account menu to render above later pantry cards by fixing the header-level stacking context instead of adding denser layout changes.
- Restored mobile pantry access to per-product AI enhancement as a secondary action inside product tools, keeping AI available without returning it to a prominent primary mobile CTA.
