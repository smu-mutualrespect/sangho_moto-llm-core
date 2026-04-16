from __future__ import annotations

import json
from typing import Any

from .decision import DecisionOutput
from .normalizer import CanonicalRequest
from .protocol_renderer import render_protocol_response
from .response_plan import ResponsePlan
from .shape_adapter import adapt_response_plan


def render_aws_response(
    canonical: CanonicalRequest,
    decision: DecisionOutput,
    world_state: dict[str, Any],
    response_plan: ResponsePlan,
) -> tuple[str, dict[str, Any]]:
    if decision.error_mode != "none":
        return _render_error(canonical, decision), {"assets": []}

    payload, render_meta = adapt_response_plan(canonical, response_plan, world_state)
    return render_protocol_response(canonical, payload, render_meta)


def render_safe_fallback(canonical: CanonicalRequest) -> str:
    fallback = {
        "__type": "AccessDeniedException",
        "message": f"Request blocked by honeypot guardrails for {canonical.service}:{canonical.operation}",
    }
    return json.dumps(fallback)


def _render_error(canonical: CanonicalRequest, decision: DecisionOutput) -> str:
    if decision.error_mode == "access_denied":
        return json.dumps(
            {
                "__type": "AccessDeniedException",
                "message": f"User is not authorized to perform {canonical.service}:{canonical.operation}",
            }
        )
    if decision.error_mode == "throttling":
        return json.dumps(
            {
                "__type": "ThrottlingException",
                "message": "Rate exceeded",
            }
        )
    if decision.error_mode == "not_found":
        return json.dumps(
            {
                "__type": "ResourceNotFoundException",
                "message": "Requested resource does not exist",
            }
        )
    return render_safe_fallback(canonical)
