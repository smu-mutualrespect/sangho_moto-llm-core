Use this skill when a response must match AWS CLI Output and botocore output shape.

Behavior:
- Treat botocore output shape as the source of truth for top-level and nested members.
- Do not ask the model to write final JSON or XML directly.
- Prefer sparse response_plan hints that let the runtime fill protocol-correct members.
- If a command page or output shape is unfamiliar, request aws_cli.inspect_reference_output or schema.inspect_output_shape.
- Keep list counts small unless the request explicitly asks for many results.
