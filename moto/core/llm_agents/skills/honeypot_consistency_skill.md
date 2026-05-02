Use this skill when the request may expose fake cloud inventory, identities, or state.

Behavior:
- Keep account id, region, ARNs, resource names, and session history consistent.
- Echo request identifiers only when they are safe and already fake or user supplied.
- Prefer believable low-privilege inventory over dramatic privileged findings.
- Track state through environment_delta only when the response should affect future consistency.
- Never introduce real credentials, public callback URLs, private keys, or real account data.
