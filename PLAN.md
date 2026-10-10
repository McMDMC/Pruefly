# Prüfly — Plan

**Vision.** A teacher photographs a Grundschule test. Prüfly detects its structure, generates a *new variant of equal difficulty* with fresh values, verifies every answer in code, and hands back a print-ready worksheet plus a Lösungsblatt as PDF. First real user: Joanna (Grundschullehrerin, BW). If she uses it weekly, the product is validated.

**Blueprint.** The Wandelbar MVP (`wandelbar_mvp.html`). The engine is proven; this repo turns it into a server-side, model-agnostic product. Nothing in the core idea changes:

```
photo ─► derender ─► IR (typed tasks) ─► transform ─► reconcile + solve (code) ─► render ─► PDF
         (LLM)       slot roles          (LLM)         never trusts the model      HTML/CSS
```

## Non-negotiable invariants (carried over from Wandelbar)

1. **Slot roles.** GEGEBEN (printed value the pupil needs) is always regenerated. LÜCKE (blank) always stays blank, rendered as `_`. FIX (numbers, points, headings) is never touched.
2. **Answers are computed, never trusted.** The LLM proposes values; deterministic code decides whether they are valid and computes every solution.
3. **Structure is restored from the original** when the model drifts (task count, types, templates, labels, points).
4. **Model swappability.** All LLM access goes through `ModelRouter`. No provider SDK is imported outside `pruefly/llm/`.

## Decisions

| # | Decision | Why |
|---|----------|-----|
| D1 | Anthropic first, Gemini (Vertex) second, order set by env per task | Joanna needs it now; Claude vision is proven on the MVP. Gemini is a drop-in via the same interface. |
| D2 | Stateless API; the client holds the IR | No pupil photo or worksheet is stored. Simplest GDPR story. History (Firestore) is opt-in later. |
| D3 | Server-side render, WeasyPrint → PDF | Phone/tablet users cannot rely on browser print. Same HTML powers preview and PDF. |
| D4 | M0 frontend is one static page served by FastAPI | Joanna can use it the day it deploys. Next.js 15 (as in the earlier design) is deferred until there is a feature that needs it. |
| D5 | Fail-closed access code (`X-Access-Code`) | A public Cloud Run URL would otherwise let anyone burn the API key. |
| D6 | Deterministic regeneration for equations | If the model returns an invalid or pattern-breaking item, code generates a valid one (same digits, same Zehnerübergang pattern, within Zahlenraum). |
| D7 | Preview in a sandboxed iframe (`srcdoc`) | IR text is escaped, and the iframe cannot run scripts, as defence in depth. |

## Milestones

**M0 — this PR (usable end to end)**
Router + providers, IR schema, reconcile/solve, renderer, PDF, API, German UI, tests, Dockerfile, `deploy.sh`.
*Exit:* Joanna uploads a test photo on her phone and prints a variant.

**M1 — Joanna loop (week 1 after deploy)**
Run 5–10 of her real tests. Log failure classes (not content): wrong slot count, wrong type, layout drift. Turn each failure into a golden test.
*Exit:* ≥ 8 of 10 variants printable without edits.

**M2 — Provider eval**
Same 10 tests through Anthropic and Gemini. Compare slot-count accuracy, validator fix rate, cost per sheet, latency. Pick the default per task from data (`PRUEFLY_*_PROVIDERS`).

**M3 — Production hardening**
Terraform, Cloud Build CI/CD, Secret Manager, Firebase Auth, opt-in history, structured outputs if the providers' schema support covers the IR.

**M4 — Product depth**
Differenzierung (3 levels), Bildungsplan context injection, new task types, Grundschrift font.

## Open items that need a human

- **`ANTHROPIC_API_KEY`** — needed to run for real. Put it in Secret Manager (see `deploy.sh`).
- **Gemini model id** — set `PRUEFLY_GEMINI_MODEL`; check the exact GA id in the Vertex model list before relying on it.
- **Publisher material — DECIDED (Michael, 2026-10-10):** allowed as input, **private use by Joanna only**. No sharing of the URL/access code, no distribution or sale of generated sheets, no commercial rollout until the legal question is answered. Nothing is stored server-side, so no publisher content persists in Prüfly.
- **Pupil data.** Tell Joanna not to photograph sheets with pupil names. Nothing is stored, but the photo does reach the model provider.
