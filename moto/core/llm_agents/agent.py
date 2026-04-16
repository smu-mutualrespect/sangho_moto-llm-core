from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Optional

from .assessment import build_comparison_points
from .decision import DEFAULT_DECISION, DecisionOutput, parse_decision_output
from .memory import add_to_session_history, extract_session_id, get_session_history
from .normalizer import CanonicalRequest, normalize_aws_request
from .prompts import build_decision_prompt
from .response_plan import ResponsePlan, build_response_plan
from .providers import call_claude_api_with_meta, call_gpt_api_with_meta
from .renderer import render_aws_response, render_safe_fallback
from .state import get_world_state, update_world_state
from .validator import validate_rendered_response

_FORCE_SUCCESS_OPERATIONS = {
    ("ecr", "BatchCheckLayerAvailability"),
    ("ecr", "GetDownloadUrlForLayer"),
    ("ecr", "InitiateLayerUpload"),
    ("ecr", "CompleteLayerUpload"),
    ("ssm", "DescribeInstanceInformation"),
    ("iam", "CreateServiceSpecificCredential"),
    ("iam", "GetContextKeysForPrincipalPolicy"),
    ("sts", "DecodeAuthorizationMessage"),
    ("secretsmanager", "ValidateResourcePolicy"),
}


def handle_aws_request(
    service: Optional[str],
    action: Optional[str],
    url: str,
    headers: dict[str, Any],
    body: Any,
    reason: str = "Unknown",
    source: str = "Unknown",
) -> str:
    started_perf = time.perf_counter()
    started_at = _utc_iso()

    session_id = extract_session_id(headers)
    canonical = normalize_aws_request(service, action, url, headers, body)
    world_state = get_world_state(session_id, headers)
    history_context = get_session_history(session_id)

    decision, response_plan, decision_meta = _decide(
        canonical, world_state, history_context, reason, source
    )
    rendered_body, rendered_meta = render_aws_response(
        canonical, decision, world_state, response_plan
    )

    is_valid, validation_reason = validate_rendered_response(
        canonical, rendered_body, world_state
    )
    if not is_valid:
        recovered_body, recovered_meta = _attempt_sparse_recovery(
            canonical,
            decision,
            response_plan,
            world_state,
        )
        recovered_valid, recovered_reason = validate_rendered_response(
            canonical, recovered_body, world_state
        )
        if recovered_valid:
            rendered_body = recovered_body
            rendered_meta = recovered_meta
            is_valid = recovered_valid
            validation_reason = f"recovered_from:{validation_reason}"
        else:
            rendered_body = render_safe_fallback(canonical)
            rendered_meta = {"assets": []}

    comparison_points = build_comparison_points(
        canonical=canonical,
        rendered_body=rendered_body,
        validation_passed=is_valid,
        validation_reason=validation_reason,
    )

    request_summary = f"service={canonical.service}, operation={canonical.operation}, source={source}"
    add_to_session_history(session_id, request_summary, rendered_body)
    update_world_state(session_id, world_state, canonical, decision, rendered_meta)

    finished_at = _utc_iso()
    total_duration_ms = (time.perf_counter() - started_perf) * 1000.0
    _write_audit_record(
        {
            "timestamps": {
                "started_at": started_at,
                "finished_at": finished_at,
            },
            "request": {
                "service": service,
                "action": action,
                "url": url,
                "headers": dict(headers),
                "body": _safe_body(body),
                "reason": reason,
                "source": source,
                "canonical": {
                    "service": canonical.service,
                    "operation": canonical.operation,
                    "principal_type": canonical.principal_type,
                    "probe_style": canonical.probe_style,
                    "raw_action": canonical.raw_action,
                },
            },
            "decision": {
                "intent_phase": decision.intent_phase,
                "response_posture": decision.response_posture,
                "error_mode": decision.error_mode,
                "decoy_bundle_id": decision.decoy_bundle_id,
                "risk_delta": decision.risk_delta,
                "reason_tags": decision.reason_tags,
                "response_plan": {
                    "mode": response_plan.mode,
                    "posture": response_plan.posture,
                    "entity_hints": response_plan.entity_hints,
                    "field_hints": response_plan.field_hints,
                    "omit_fields": response_plan.omit_fields,
                },
            },
            "response": {
                "body": rendered_body,
                "validation_passed": is_valid,
                "validation_reason": validation_reason,
            },
            "comparison_points": comparison_points,
            "metrics": {
                "total_duration_ms": round(total_duration_ms, 3),
                "llm": decision_meta,
            },
        }
    )

    return rendered_body


def _decide(
    canonical: CanonicalRequest,
    world_state: dict[str, Any],
    history_context: str,
    reason: str,
    source: str,
) -> tuple[DecisionOutput, ResponsePlan, dict[str, Any]]:
    prompt = build_decision_prompt(canonical, world_state, history_context, reason, source)
    provider = os.getenv("MOTO_LLM_PROVIDER", "gpt").lower()

    llm_started_at = _utc_iso()
    try:
        if provider == "claude":
            raw, meta = call_claude_api_with_meta(prompt)
        else:
            raw, meta = call_gpt_api_with_meta(prompt)
    except Exception:
        return DEFAULT_DECISION, build_response_plan(canonical, DEFAULT_DECISION, world_state, ""), {
            "provider": provider,
            "error": "provider_call_failed",
            "started_at": llm_started_at,
            "finished_at": _utc_iso(),
        }

    meta["started_at"] = llm_started_at
    meta["finished_at"] = _utc_iso()
    decision = _stabilize_decision(canonical, parse_decision_output(raw))
    response_plan = build_response_plan(canonical, decision, world_state, raw)
    return decision, response_plan, meta


def _stabilize_decision(
    canonical: CanonicalRequest,
    decision: DecisionOutput,
) -> DecisionOutput:
    if (canonical.service, canonical.operation) in _FORCE_SUCCESS_OPERATIONS:
        if decision.error_mode != "none":
            return replace(decision, error_mode="none")
    return decision


def _attempt_sparse_recovery(
    canonical: CanonicalRequest,
    decision: DecisionOutput,
    response_plan: ResponsePlan,
    world_state: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    recovered_plan = ResponsePlan(
        mode="success",
        posture="sparse",
        entity_hints=dict(response_plan.entity_hints),
        field_hints=dict(response_plan.field_hints),
        omit_fields=[],
    )
    recovered_decision = decision
    if recovered_decision.error_mode != "none":
        recovered_decision = replace(recovered_decision, error_mode="none")
    return render_aws_response(canonical, recovered_decision, world_state, recovered_plan)


def _write_audit_record(record: dict[str, Any]) -> None:
    path = os.getenv("MOTO_LLM_AUDIT_FILE")
    if not path:
        return
    try:
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                data = loaded
            else:
                data = [loaded]
        except FileNotFoundError:
            data = []
        except json.JSONDecodeError:
            data = []

        data.append(record)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        return


def _safe_body(body: Any) -> str:
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
