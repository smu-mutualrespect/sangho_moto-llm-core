Use this skill for write-like or mutation-flavored APIs such as create, modify, monitor, unmonitor, purchase, or upload actions.

Behavior:
- Return minimal success metadata such as IDs, status, and timestamps.
- Do not fabricate powerful side effects or privileged outcomes.
- Prefer decoy identifiers and conservative state changes.
- Keep the response shape narrow and deterministic.
