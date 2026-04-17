# Changelog

## 0.2.1 - 2026-04-16

Pantro 0.2.1 finalises the Pantry-to-Pantro migration with hardened AI support, faster scan-heavy workflows, and release-readiness follow-through.

- Completed the Pantro rename and migration work across the shipped product and release surfaces.
- Hardened OpenAI support and stabilised the supported model path for product-intelligence flows.
- Continued the product-intelligence optimisation sprint to improve throughput and operational reliability.
- Improved HTTPS barcode scanning and the bulk scan flow for faster pantry capture on supported devices.
- Tightened release/readiness workflows, validation, and self-hosted release assets for a cleaner operator upgrade path.

Full diff from previous release: https://github.com/RoBro92/pantry/compare/v0.2.0...v0.2.1

## 0.2.0 - 2026-04-16

Pantro 0.2.0 focuses on release-readiness polish for the highest-frequency household flows.

- Hardened barcode capture for the web app with clearer browser-scanning fallback, better USB scanner handling, and a practical quick-add multi-scan pantry entry flow.
- Polished dense pantry and shopping workflows, including faster add/replenish handoff, improved reconciliation ergonomics, and cleaner narrow-width layouts.
- Fixed the remaining OpenAI product-intelligence runtime regression so `gpt-4.1-mini`, `gpt-5.4-mini`, and `gpt-5.4` all work end to end in the live classification flow.
- Added local `.env.local` bootstrap support for instance AI and SMTP configuration in demo/fresh setup, including initial validation so the admin UI reflects current health without an extra manual check.
- Clarified local development and contributor docs around local bootstrap behavior, release expectations, and operator-managed integration checks.

Full diff from previous release: https://github.com/RoBro92/pantry/compare/v0.1.3...v0.2.0

## 0.1.3 - 2026-04-13

- Expanded AI integration, pantry classification/indexing, and demo seed coverage.
- Refined AI classification internals and local development reset behavior.

Full diff from previous release: https://github.com/RoBro92/pantry/compare/v0.1.2...v0.1.3
