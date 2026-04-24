from __future__ import annotations

from copy import deepcopy
from typing import Any

from .request_tools import CanonicalRequest

_session_storage: dict[str, list[dict[str, str]]] = {}
_session_state: dict[str, dict[str, Any]] = {}


def get_session_history_tool(session_id: str) -> str:
    history = _session_storage.get(session_id, [])
    if not history:
        return "No previous interactions in this session."
    formatted: list[str] = []
    for idx, item in enumerate(history, start=1):
        formatted.append(f"Request {idx}: {item['request']}")
        formatted.append(f"Response {idx}: {item['response'][:280]}")
    return "\n".join(formatted)


def add_to_session_history_tool(session_id: str, request_info: str, response: str) -> None:
    _session_storage.setdefault(session_id, []).append({"request": request_info, "response": response})
    if len(_session_storage[session_id]) > 8:
        _session_storage[session_id].pop(0)


def extract_session_id_tool(headers: dict[str, Any]) -> str:
    return str(
        headers.get("X-Forwarded-For")
        or headers.get("x-forwarded-for")
        or headers.get("X-Amzn-Trace-Id")
        or headers.get("x-amzn-trace-id")
        or "default_session"
    )


def get_world_state_tool(session_id: str, headers: dict[str, Any]) -> dict[str, Any]:
    if session_id not in _session_state:
        _session_state[session_id] = {
            "session_id": session_id,
            "persona": "mid-size-prod-account",
            "region": headers.get("X-Amz-Region", "us-east-1"),
            "phase": "recon",
            "exposed_assets": [],
            "exposed_roles": ["ReadOnlyOpsRole"],
            "credibility_level": "medium",
            "risk_score": 0.2,
            "last_actions": [],
            "consistency_locks": {
                "account_id": "123456789012",
                "os_family": "Amazon Linux 2",
            },
        }
    return deepcopy(_session_state[session_id])


def update_world_state_tool(
    session_id: str,
    current: dict[str, Any],
    canonical: CanonicalRequest,
    agent_output: Any,
    rendered_meta: dict[str, Any],
) -> None:
    next_state = deepcopy(current)

    next_state["phase"] = agent_output.intent_phase
    risk_score = float(next_state.get("risk_score", 0.2)) + float(agent_output.risk_delta)
    next_state["risk_score"] = max(0.0, min(1.0, risk_score))

    action_key = f"{canonical.service}:{canonical.operation}"
    last_actions = list(next_state.get("last_actions", []))
    last_actions.append(action_key)
    next_state["last_actions"] = last_actions[-10:]

    # Merge environment_delta into world_state
    for key, value in agent_output.environment_delta.items():
        if isinstance(value, list):
            existing = list(next_state.get(key, []))
            for item in value:
                if item not in existing:
                    existing.append(item)
            next_state[key] = existing
        else:
            next_state[key] = value

    # Track exposed assets from the serialized response
    exposed_assets = list(next_state.get("exposed_assets", []))
    for asset in rendered_meta.get("assets", []):
        if asset not in exposed_assets:
            exposed_assets.append(asset)
    next_state["exposed_assets"] = exposed_assets

    _session_state[session_id] = next_state
