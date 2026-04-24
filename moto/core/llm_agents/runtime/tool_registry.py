from __future__ import annotations


def get_available_tool_names() -> list[str]:
    return [
        "request_tools.normalize_request",
        "state_tools.get_world_state",
        "state_tools.get_session_history",
        "planning_tools.build_response_plan",
        "render_tools.adapt_response_plan",
        "render_tools.render_protocol_response",
        "validation_tools.validate_rendered_response",
    ]
