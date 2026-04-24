Use this skill for list/describe/get style reconnaissance APIs.

Behavior:
- Prefer sparse but plausible success responses.
- Echo stable identifiers from the request when available.
- Avoid turning inventory-style APIs into access denied errors unless the request is clearly destructive.
- When validation fails, reduce the response to the minimum shape that still looks useful.
