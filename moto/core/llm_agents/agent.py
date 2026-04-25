from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

from .runtime.runner import run_agent_loop
from .runtime import (
    AgentOutput,
    DEFAULT_OUTPUT,
    build_agent_prompt,
    call_claude_api_with_meta,
    call_gpt_api_with_meta,
    parse_agent_output,
)
from .runtime.provider import _load_dotenv_if_present
from .tools import (
    add_to_session_history_tool,
    build_comparison_points_tool,
    extract_session_id_tool,
    get_session_history_tool,
    get_world_state_tool,
    normalize_request_tool,
    serialize_response_tool,
    update_world_state_tool,
)
from .tools.request_tools import CanonicalRequest

_ERROR_BODIES: dict[str, Any] = {
    "access_denied": lambda svc, op: json.dumps({
        "__type": "AccessDeniedException",
        "message": f"User is not authorized to perform {svc}:{op}",
    }),
    "throttling": lambda svc, op: json.dumps({
        "__type": "ThrottlingException",
        "message": "Rate exceeded",
    }),
    "not_found": lambda svc, op: json.dumps({
        "__type": "ResourceNotFoundException",
        "message": "Requested resource does not exist",
    }),
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

    session_id = extract_session_id_tool(headers)
    canonical = normalize_request_tool(service, action, url, headers, body)
    world_state = get_world_state_tool(session_id, headers)
    history_context = get_session_history_tool(session_id)
    runtime_mode = os.getenv("MOTO_LLM_RUNTIME_MODE", "workflow").strip().lower()

    if runtime_mode == "agentic":
        run_result = run_agent_loop(
            canonical=canonical,
            world_state=world_state,
            history_context=history_context,
            reason=reason,
            source=source,
        )
        agent_output = run_result.agent_output
        planner_meta = run_result.planner_meta
        field_values = run_result.field_values
        response_body = run_result.response_body
        rendered_meta = run_result.rendered_meta
    else:
        agent_output, planner_meta = _call_agent(canonical, world_state, history_context, reason, source)
        field_values = agent_output.field_values
        if agent_output.error_mode != "none":
            error_fn = _ERROR_BODIES.get(agent_output.error_mode, _ERROR_BODIES["access_denied"])
            response_body = error_fn(canonical.service, canonical.operation)
            rendered_meta = {"assets": []}
        else:
            response_body, rendered_meta = serialize_response_tool(canonical, agent_output.field_values)
            if not response_body:
                response_body = render_safe_fallback(canonical)
                rendered_meta = {"assets": []}

    if runtime_mode == "agentic" and not response_body:
        error_fn = _ERROR_BODIES.get(agent_output.error_mode, _ERROR_BODIES["access_denied"])
        response_body = error_fn(canonical.service, canonical.operation)
        rendered_meta: dict[str, Any] = {"assets": []}

    add_to_session_history_tool(
        session_id,
        f"service={canonical.service}, operation={canonical.operation}, source={source}",
        response_body,
    )
    update_world_state_tool(session_id, world_state, canonical, agent_output, rendered_meta)

    validation_passed = rendered_meta.get("validation_passed", bool(response_body))
    validation_reason = rendered_meta.get("validation_reason", "serializer" if response_body else "fallback")
    comparison_points = build_comparison_points_tool(
        canonical=canonical,
        rendered_body=response_body,
        validation_passed=bool(validation_passed),
        validation_reason=str(validation_reason),
    )

    finished_at = _utc_iso()
    total_ms = (time.perf_counter() - started_perf) * 1000.0
    _write_audit_record({
        "timestamps": {"started_at": started_at, "finished_at": finished_at},
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
            "intent_phase": agent_output.intent_phase,
            "response_posture": getattr(agent_output, "response_posture", "normal"),
            "decoy_bundle_id": getattr(agent_output, "decoy_bundle_id", "baseline"),
            "error_mode": agent_output.error_mode,
            "risk_delta": agent_output.risk_delta,
            "reason_tags": agent_output.reason_tags,
            "environment_delta": agent_output.environment_delta,
            "field_values_keys": list(field_values.keys()),
        },
        "response": {
            "body": response_body,
            "assets": rendered_meta.get("assets", []),
            "protocol": rendered_meta.get("protocol", "unknown"),
        },
        "comparison_points": comparison_points,
        "metrics": {
            "total_duration_ms": round(total_ms, 3),
            "llm": planner_meta,
        },
    })

    _log_fallback_stats(canonical, planner_meta, total_ms)

    return response_body


def _log_fallback_stats(
    canonical: CanonicalRequest,
    planner_meta: dict[str, Any],
    total_ms: float,
) -> None:
    usage = planner_meta.get("usage") or {}
    input_tokens = usage.get("input_tokens", "-")
    output_tokens = usage.get("output_tokens", "-")
    total_tokens = "-"
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        total_tokens = str(input_tokens + output_tokens)

    provider = planner_meta.get("provider", "-")
    model = planner_meta.get("model", "-")
    error = planner_meta.get("error")

    lines = [
        f"",
        f"[moto-fallback] {canonical.service}:{canonical.operation}",
        f"  provider : {provider} ({model})",
    ]
    if error:
        lines.append(f"  error    : {error}")
    else:
        lines.append(f"  tokens   : input={input_tokens}  output={output_tokens}  total={total_tokens}")
    lines.extend([
        f"  time     : {round(total_ms)}ms",
        f"",
    ])
    print("\n".join(lines), file=sys.stderr, flush=True)


def _call_agent(
    canonical: CanonicalRequest,
    world_state: dict[str, Any],
    history_context: str,
    reason: str,
    source: str,
) -> tuple[AgentOutput, dict[str, Any]]:
    _load_dotenv_if_present()
    prompt = build_agent_prompt(canonical, world_state, history_context, reason, source)
    provider = os.getenv("MOTO_LLM_PROVIDER", "gpt").lower()
    llm_started_at = _utc_iso()
    try:
        if provider == "claude":
            raw, meta = call_claude_api_with_meta(prompt)
        else:
            raw, meta = call_gpt_api_with_meta(prompt)
    except Exception:
        return DEFAULT_OUTPUT, {
            "provider": provider,
            "error": "provider_call_failed",
            "started_at": llm_started_at,
            "finished_at": _utc_iso(),
        }
    meta["started_at"] = llm_started_at
    meta["finished_at"] = _utc_iso()
    return parse_agent_output(raw), meta


def render_safe_fallback(canonical: CanonicalRequest) -> str:
    return json.dumps({
        "__type": "AccessDeniedException",
        "message": f"Request blocked by honeypot guardrails for {canonical.service}:{canonical.operation}",
    })


def _write_audit_record(record: dict[str, Any]) -> None:
    path = os.getenv("MOTO_LLM_AUDIT_FILE")
    if not path:
        return
    try:
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            data = loaded if isinstance(loaded, list) else [loaded]
        except (FileNotFoundError, json.JSONDecodeError):
            data = []
        data.append(record)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _safe_body(body: Any) -> str:
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
