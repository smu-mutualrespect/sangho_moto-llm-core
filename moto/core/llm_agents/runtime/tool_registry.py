from __future__ import annotations


def get_available_tool_names() -> list[str]:
    return [
        "skills.load_skill_document",
        "schema.inspect_output_shape",
        "aws_cli.inspect_reference_output",
        "runtime.summarize_request_context",
        "state.inspect_consistency",
        "latency.estimate_budget",
        "validator.explain_last_failure",
    ]
