# Honeypot LLM Tuning Plan

## Goal

Make the fallback path behave like a believable AWS honeypot responder:

- do not overfit to a fixed shortlist of commands
- preserve AWS protocol and output shape compatibility
- echo attacker-supplied identifiers when plausible
- keep world-state consistency across related probes
- avoid obvious placeholders and synthetic artifacts

## Scope

This tuning loop uses 50 attacker-plausible AWS CLI commands grouped into 10 batches of 5.
The commands are chosen to look like reconnaissance, permission testing, credential harvesting,
container abuse, or secrets discovery. They are intentionally biased toward paths likely to miss
native Moto handling and therefore exercise the LLM fallback runtime.

## Metrics

Per scenario we track:

- protocol serialization success
- validator pass/fail
- safe fallback triggered or not
- request identifier echo coverage
- placeholder artifacts in rendered output
- obviously implausible values

Per batch we record:

- pass count
- fallback count
- placeholder count
- batch-specific weak points
- code changes made in response

## Workflow

1. Run one batch of 5 scenarios.
2. Read structured artifacts and batch summary.
3. Record shortcomings in `artifacts/tuning/tuning_log.md`.
4. Patch generic generation logic, not batch-specific hacks.
5. Re-run the affected batch and continue to the next.
6. After all 10 batches, summarize remaining failure modes.

## Guardrails

- Do not add operation-specific tuning unless the fix is clearly reusable.
- Prefer shape-driven and member-name-driven rules over scenario matching.
- Keep a written record for every tuning pass.
- If a response fails validation, prioritize schema-safe fixes first.
