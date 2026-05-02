from __future__ import annotations


def get_available_tool_names() -> list[str]:
    return [
        "request_tools.normalize_request_tool",
        "state_tools.get_world_state_tool",
        "state_tools.get_session_history_tool",
        "skills.load_skill_document",
        "schema.inspect_output_shape",
        "runtime.summarize_request_context",
        "planning_tools.build_response_plan_tool",
        "shape_adapter.adapt_response_plan",
        "render_tools.serialize_response_tool",
        "validation_tools.validate_rendered_response_tool",
    ]
