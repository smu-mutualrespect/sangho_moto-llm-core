from __future__ import annotations

from typing import Any

_session_storage: dict[str, list[dict[str, str]]] = {}


def get_session_history(session_id: str) -> str:
    history = _session_storage.get(session_id, [])
    if not history:
        return "No previous interactions in this session."

    formatted: list[str] = []
    for idx, item in enumerate(history, start=1):
        formatted.append(f"Request {idx}: {item['request']}")
        formatted.append(f"Response {idx}: {item['response'][:280]}")

    return "\n".join(formatted)


def add_to_session_history(session_id: str, request_info: str, response: str) -> None:
    _session_storage.setdefault(session_id, []).append(
        {"request": request_info, "response": response}
    )
    if len(_session_storage[session_id]) > 8:
        _session_storage[session_id].pop(0)


def extract_session_id(headers: dict[str, Any]) -> str:
    return str(
        headers.get("X-Forwarded-For")
        or headers.get("x-forwarded-for")
        or headers.get("X-Amzn-Trace-Id")
        or headers.get("x-amzn-trace-id")
        or "default_session"
    )
