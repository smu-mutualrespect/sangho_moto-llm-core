from __future__ import annotations

from moto.core.utils import get_service_model

from .normalizer import CanonicalRequest

SYSTEM_PROMPT = """
You are a decision agent for an AWS honeypot runtime.
Output must be a single JSON object.
Required top-level fields:
- intent_phase: recon|privilege_check|lateral_probe|impact_probe
- response_posture: sparse|normal|rich
- error_mode: none|access_denied|throttling|not_found
- decoy_bundle_id: lowercase letters/digits/_/- only (3-64)
- risk_delta: number between -0.2 and 0.5
- reason_tags: array of enum tags among
  [enum_pattern, credential_probe, region_sweep, permission_test, high_rate, rare_api_chain]
Optional top-level field:
- response_plan: object with fields:
  - mode: success|empty|error
  - posture: sparse|normal|rich
  - entity_hints: object for counts and identifiers
  - field_hints: object for plausible values only
  - omit_fields: array of output field names to omit
Do not output markdown, code fences, comments, or explanatory text.
Default to `error_mode: "none"` for reconnaissance, policy inspection, and inventory-style APIs.
Use `access_denied` only when the request is clearly destructive, privilege-escalating, or would be more believable as an explicit deny than as a decoy success.
Prefer terse outputs that keep the decoy flow alive over blanket denial.
The agent does not render final AWS JSON/XML. It only selects posture and plausible values.
Do not use `response_plan.mode="error"` for reconnaissance, inventory, decode, validation, or upload-init APIs when `error_mode` is `none`.
Do not omit core output fields that make the AWS response actionable, such as upload ids, part sizes, decoded messages, validation flags, or primary list members.
""".strip()


def build_decision_prompt(
    canonical: CanonicalRequest,
    world_state: dict[str, object],
    history_context: str,
    reason: str,
    source: str,
) -> str:
    output_schema_hint = build_output_schema_hint(canonical)
    return f"""
{SYSTEM_PROMPT}

CURRENT_REQUEST:
service={canonical.service}
operation={canonical.operation}
principal_type={canonical.principal_type}
probe_style={canonical.probe_style}
raw_action={canonical.raw_action}
body_format={canonical.body_format}
request_params={canonical.request_params}
target_identifiers={canonical.target_identifiers}
reason={reason}
source={source}

OUTPUT_SCHEMA_HINT:
{output_schema_hint}

WORLD_STATE:
{world_state}

RECENT_HISTORY:
{history_context}
""".strip()


def build_output_schema_hint(canonical: CanonicalRequest) -> str:
    try:
        service_model = get_service_model(canonical.service)
        operation_model = service_model.operation_model(canonical.operation)
    except Exception:
        return "unavailable"

    output_shape = operation_model.output_shape
    if output_shape is None:
        return "none"

    lines = [
        f"protocol={service_model.metadata.get('protocol', 'unknown')}",
        f"output_shape={output_shape.name}",
    ]
    for name, member in list(output_shape.members.items())[:15]:
        lines.append(f"- {name}: {member.type_name}({member.name})")
    return "\n".join(lines)


def build_final_prompt(
    service: str | None,
    action: str | None,
    url: str,
    headers: dict[str, object],
    body: object,
    history_context: str,
    reason: str,
    source: str,
) -> str:
    # Backward compatibility for old imports. The new runtime path uses build_decision_prompt.
    return f"""
Legacy prompt path (deprecated).
service={service}
action={action}
url={url}
headers={headers}
body={body}
history={history_context}
reason={reason}
source={source}
""".strip()
