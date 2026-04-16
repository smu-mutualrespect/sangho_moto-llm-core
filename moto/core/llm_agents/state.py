from __future__ import annotations

from copy import deepcopy
from typing import Any

from .decision import DecisionOutput
from .normalizer import CanonicalRequest

_session_state: dict[str, dict[str, Any]] = {}


def get_world_state(session_id: str, headers: dict[str, Any]) -> dict[str, Any]:
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


def update_world_state(
    session_id: str,
    current: dict[str, Any],
    canonical: CanonicalRequest,
    decision: DecisionOutput,
    rendered_meta: dict[str, Any],
) -> None:
    next_state = deepcopy(current)
    next_state["phase"] = decision.intent_phase

    risk_score = float(next_state.get("risk_score", 0.2)) + float(decision.risk_delta)
    next_state["risk_score"] = max(0.0, min(1.0, risk_score))

    action_key = f"{canonical.service}:{canonical.operation}"
    last_actions = list(next_state.get("last_actions", []))
    last_actions.append(action_key)
    next_state["last_actions"] = last_actions[-10:]

    exposed_assets = list(next_state.get("exposed_assets", []))
    for asset in rendered_meta.get("assets", []):
        if asset not in exposed_assets:
            exposed_assets.append(asset)
    next_state["exposed_assets"] = exposed_assets

    _session_state[session_id] = next_state
