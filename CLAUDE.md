# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Lead.Tracker is an **Opportunity Intelligence module for Tech.Forge**. It turns customer/prospect data, technology portfolio, products, services, and external sources into prioritized commercial opportunities. It is not a standalone app in its final form — it's an installable Tech.Forge module (`.mod` package) with a manifest, health check, and lifecycle (install/enable/disable/uninstall).

## Architecture

Stack: Python/FastAPI backend, React/TypeScript frontend (Tech.Forge Module Host-compatible), SQLite local persistence (SQLAlchemy async), `.env`/`env-model` config, `.mod` packaging.

Dependency direction (interface must never reach past its layer, e.g. no direct Salesforce/Maps/AI calls from the UI):

```
Interface
 ↓
Application services
 ↓
Domain / Opportunity Engine
 ↓
Provider interfaces
 ↓
External systems
```

Providers (Salesforce, Website, Google Maps, CSV, Manual, ...) collect and normalize data only — they never compute scores, generate emails, run AI prompts, or touch the UI. Salesforce is one optional provider among others, not a first-class domain concept.

## Core domain rules

- **Company** is the unified entity; `is_customer`/`customer_status` is an attribute of Company, never a Salesforce-specific concept. Multiple sources (`sources: [{type, confidence}]`) attach to one Company — never duplicate a company because it appeared in two sources; normalization must consolidate.
- **Product vs Service**: separate models, can generate independent opportunities.
- **Score vs financial potential are distinct**: `opportunity_score` (adherence), `financial_potential`, `strategic_score`, `confidence_score` — never collapse into one number; they can produce different rankings.
- **Portfolio is the commercial authority.** AI must ground recommendations in the configured portfolio and must never invent products/services or decide an opportunity exists on its own.
- **Deterministic rules come before AI.** E.g. "Veeam VBR present + M365 present + VDC365 absent → VDC365 opportunity." AI is complementary: interprets, correlates, enriches, summarizes, drafts — never decides alone, never edits source data, never sends email automatically.
- **No opportunity without sufficient evidence** — every opportunity needs motivo/evidências/fontes/nível de confiança.
- **Opportunity status flow**: detected → qualified → reviewed → contacted → opportunity → dismissed.
- Portfolio sync never silently overwrites existing data — user explicitly chooses **Adicionar** (merge) or **Sobrescrever** (replace).
- The core must stay generic/open-source: no hardcoded vendors, portfolio, or business rules for any specific company.

## Configuration

`.env` holds real install values (never committed). `env-model` is the distributed template. On startup/upgrade: diff `.env` against `env-model`, add only missing keys, never overwrite or remove existing values. Users configure everything through a settings screen — never by hand-editing `.env`. Secrets must never appear in tables, logs, error messages, PDFs, exports, or AI prompts.

## Error handling & resilience

Convert all technical exceptions into friendly, actionable domain errors (target user is non-technical) — never surface raw stack traces or exceptions like `requests.exceptions.ConnectionError`. Every external call needs an explicit timeout. Retry only transient errors — never retry invalid credentials/requests/authorization failures. An optional integration going down (e.g. AI provider) must degrade gracefully, not take down the module (deterministic opportunities keep working without AI).

## Testing

Unit tests cover models, normalization, dedup, filters, scoring, correlation, portfolio merge, config, error handling. Integration tests use mocked providers/Salesforce/AI. Never use real customer data in tests — use fictitious companies. Every bug fix adds/updates a regression test.

## Model routing

Mandatory, two-phase per task:
1. **Planning phase** (deciding approach, architecture, breaking down the task, non-trivial debugging root-causing, design tradeoffs) — ALWAYS Sonnet 5, regardless of how simple the eventual execution turns out to be.
2. **Execution phase** (writing the planned code/edits, boilerplate, mechanical multi-file changes, formatting, repetitive edits) — hand off to Haiku 4.5 once the plan is decided, unless the execution itself keeps requiring judgment calls (then stay on Sonnet 5).

Pass `model: "haiku"` when delegating execution via the Agent tool, or switch session model for direct simple execution. No project-specific subagents exist yet to hardcode this in frontmatter; apply it manually until agents are added under `.claude/agents`.

## Token economy

Mandatory, aggressive optimization: prefer `ast-grep`/`ast-grep-outline` over reading whole files; don't re-read a file just edited (Edit/Write already confirm success); keep responses terse, no recapping what's already in CLAUDE.md; avoid spawning subagents/forks unless they yield a real context-size win (each cold start re-derives context).

## Search tooling

Mandatory: for code search/lookup tasks, use the `ast-grep` skills instead of plain text grep — pick whichever fits the situation: `ast-grep-outline` for a cheap structural map (files, imports, exports, members) before reading full source; `ast-grep` for structural/AST pattern queries (find specific language constructs, not just text matches).

## Agent skill discipline

Mandatory: run the `using-agent-skills` skill both before and after any coding work in this session — before, to select the right skill(s) for the task; after, to confirm nothing applicable was skipped.
