from __future__ import annotations

import json
from typing import Any

from moto.core.utils import get_service_model

from ..tools.request_tools import CanonicalRequest

_MAX_DEPTH = 4


def build_full_schema(canonical: CanonicalRequest) -> str:
    """Return a JSON-formatted description of the operation's output shape for the LLM."""
    try:
        service_model = get_service_model(canonical.service)
        operation_model = service_model.operation_model(canonical.operation)
    except Exception:
        return "unavailable"

    output_shape = operation_model.output_shape
    if output_shape is None:
        return "empty_response"

    protocol = service_model.metadata.get("protocol", "unknown")
    schema = _shape_to_dict(output_shape, depth=0)
    return f"protocol={protocol}\n{json.dumps(schema, indent=2)}"


def _shape_to_dict(shape: Any, depth: int = 0) -> dict[str, Any]:
    if depth > _MAX_DEPTH:
        return {"type": shape.type_name}

    if shape.type_name == "structure":
        required = set(getattr(shape, "required_members", []) or [])
        members: dict[str, Any] = {}
        for name, member in shape.members.items():
            info = _shape_to_dict(member, depth + 1)
            if name in required:
                info["required"] = True
            members[name] = info
        return {"type": "structure", "members": members}

    if shape.type_name == "list":
        return {"type": "list", "member": _shape_to_dict(shape.member, depth + 1)}

    if shape.type_name == "map":
        return {
            "type": "map",
            "key": shape.key.type_name,
            "value": _shape_to_dict(shape.value, depth + 1),
        }

    result: dict[str, Any] = {"type": shape.type_name}
    if hasattr(shape, "enum") and shape.enum:
        result["enum"] = list(shape.enum)
    return result
