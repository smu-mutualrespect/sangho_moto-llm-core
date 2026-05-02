from __future__ import annotations

import json
from typing import Any

from .schema import build_full_schema
from .skill_loader import load_skill_documents
from ..tools.request_tools import CanonicalRequest


def execute_agent_tool_requests(
    tool_requests: list[dict[str, Any]],
    *,
    canonical: CanonicalRequest,
    world_state: dict[str, Any],
    history_context: str,
) -> str:
    observations: list[str] = []
    for request in tool_requests[:3]:
        if not isinstance(request, dict):
            continue
        name = str(request.get("tool") or request.get("name") or "")
        args = request.get("args") if isinstance(request.get("args"), dict) else {}
        output = _execute_one(name, args, canonical, world_state, history_context)
        observations.append(json.dumps({"tool": name, "output": output}, ensure_ascii=False, separators=(",", ":")))
    return "TOOL_OBSERVATIONS=" + "[" + ",".join(observations) + "]" if observations else ""


def _execute_one(
    name: str,
    args: dict[str, Any],
    canonical: CanonicalRequest,
    world_state: dict[str, Any],
    history_context: str,
) -> dict[str, Any]:
    if name == "skills.load_skill_document":
        skill_name = str(args.get("skill") or _default_skill_for(canonical))
        skills = load_skill_documents()
        return {"skill": skill_name, "document": skills.get(skill_name, "")[:900]}
    if name == "schema.inspect_output_shape":
        return {"service": canonical.service, "operation": canonical.operation, "shape": build_full_schema(canonical)[:1600]}
    if name == "runtime.summarize_request_context":
        return {
            "service": canonical.service,
            "operation": canonical.operation,
            "probe_style": canonical.probe_style,
            "request_params": canonical.request_params,
            "target_identifiers": canonical.target_identifiers,
            "region": world_state.get("region", "us-east-1"),
            "history": history_context[:400],
        }
    return {"error": "unknown_tool", "available": [
        "skills.load_skill_document",
        "schema.inspect_output_shape",
        "runtime.summarize_request_context",
    ]}


def _default_skill_for(canonical: CanonicalRequest) -> str:
    if canonical.operation.lower().startswith(("list", "describe", "get")):
        return "recon_skill"
    if canonical.operation.lower().startswith(("create", "modify", "monitor", "unmonitor", "purchase", "initiate", "complete")):
        return "write_action_skill"
    return "protocol_repair_skill"
