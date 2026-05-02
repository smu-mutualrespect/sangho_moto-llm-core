Use this skill when live fallback latency must stay near 3 to 4 seconds.

Behavior:
- Prefer a direct sparse response_plan when schema and protocol are already known.
- Avoid optional tool rounds unless the request is unfamiliar, state-sensitive, or failed validation.
- Keep reason_tags and field_hints compact.
- Use latency.estimate_budget before requesting multiple tools.
- If validation already failed once, repair with the smallest valid shape instead of expanding context.
