from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_ALLOWED_PHASES = {"recon", "privilege_check", "lateral_probe", "impact_probe"}
_ALLOWED_POSTURES = {"sparse", "normal", "rich"}
_ALLOWED_ERROR_MODES = {"none", "access_denied", "throttling", "not_found"}
_ALLOWED_REASON_TAGS = {
    "enum_pattern",
    "credential_probe",
    "region_sweep",
    "permission_test",
    "high_rate",
    "rare_api_chain",
}


@dataclass(frozen=True)
class DecisionOutput:
    intent_phase: str
    response_posture: str
    error_mode: str
    decoy_bundle_id: str
    risk_delta: float
    reason_tags: list[str]


DEFAULT_DECISION = DecisionOutput(
    intent_phase="recon",
    response_posture="normal",
    error_mode="none",
    decoy_bundle_id="baseline",
    risk_delta=0.1,
    reason_tags=["enum_pattern"],
)


def parse_decision_output(raw_text: str) -> DecisionOutput:
    parsed = _extract_json_object(raw_text)
    if not isinstance(parsed, dict):
        return DEFAULT_DECISION

    intent_phase = _coerce_enum(parsed.get("intent_phase"), _ALLOWED_PHASES, DEFAULT_DECISION.intent_phase)
    response_posture = _coerce_enum(
        parsed.get("response_posture"), _ALLOWED_POSTURES, DEFAULT_DECISION.response_posture
    )
    error_mode = _coerce_enum(parsed.get("error_mode"), _ALLOWED_ERROR_MODES, DEFAULT_DECISION.error_mode)

    decoy_bundle_id = str(parsed.get("decoy_bundle_id") or DEFAULT_DECISION.decoy_bundle_id)
    if not re.match(r"^[a-z0-9_\-]{3,64}$", decoy_bundle_id):
        decoy_bundle_id = DEFAULT_DECISION.decoy_bundle_id

    risk_delta = _coerce_float(parsed.get("risk_delta"), DEFAULT_DECISION.risk_delta)
    risk_delta = max(-0.2, min(0.5, risk_delta))

    reason_tags = parsed.get("reason_tags")
    if isinstance(reason_tags, list):
        valid_tags = [str(tag) for tag in reason_tags if str(tag) in _ALLOWED_REASON_TAGS][:6]
    else:
        valid_tags = []

    if not valid_tags:
        valid_tags = list(DEFAULT_DECISION.reason_tags)

    return DecisionOutput(
        intent_phase=intent_phase,
        response_posture=response_posture,
        error_mode=error_mode,
        decoy_bundle_id=decoy_bundle_id,
        risk_delta=risk_delta,
        reason_tags=valid_tags,
    )


def _extract_json_object(raw_text: str) -> Any:
    candidate = raw_text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.replace("json", "", 1).strip()

    try:
        return json.loads(candidate)
    except Exception:
        pass

    first = raw_text.find("{")
    last = raw_text.rfind("}")
    if first >= 0 and last > first:
        try:
            return json.loads(raw_text[first : last + 1])
        except Exception:
            return None
    return None


def _coerce_enum(value: Any, allowed: set[str], default: str) -> str:
    string_value = str(value or "")
    return string_value if string_value in allowed else default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default
