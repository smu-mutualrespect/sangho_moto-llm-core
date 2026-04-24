from __future__ import annotations

import json
import re
from typing import Any
from xml.etree import ElementTree

from .request_tools import CanonicalRequest

_SAFE_DENY_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
]
_SAFE_XML_NAMESPACE_PATTERNS = [
    re.compile(r'xmlns="https?://[^"]+amazonaws\.com/[^"]*"', re.IGNORECASE),
    re.compile(r"xmlns='https?://[^']+amazonaws\.com/[^']*'", re.IGNORECASE),
]


def validate_rendered_response_tool(canonical: CanonicalRequest, rendered_body: str, world_state: dict[str, Any]) -> tuple[bool, str]:
    is_safe, safety_reason = _validate_safety(rendered_body)
    if not is_safe:
        return False, safety_reason
    if canonical.service == "ec2" and canonical.operation == "DescribeInstances":
        return _validate_ec2_describe_instances(rendered_body)
    if canonical.service == "ssm" and canonical.operation == "DescribeInstanceInformation":
        return _validate_ssm_describe_instance_information(rendered_body)
    quality_ok, quality_reason = _validate_non_empty_success(canonical, rendered_body)
    if not quality_ok:
        return False, quality_reason
    return _validate_world_state_consistency(rendered_body, world_state)


def build_comparison_points_tool(canonical: CanonicalRequest, rendered_body: str, validation_passed: bool, validation_reason: str) -> dict[str, Any]:
    protocol_family = "xml" if canonical.service in {"ec2", "iam", "sts", "s3"} else "json"
    stripped = rendered_body.lstrip()
    detected_format = "xml" if stripped.startswith("<") else "json" if stripped.startswith("{") or stripped.startswith("[") else "text"
    parseability = _parseability(detected_format, rendered_body)
    return {
        "protocol_family_expected": protocol_family,
        "response_format_detected": detected_format,
        "format_match": protocol_family == detected_format,
        "response_parseable": parseability["parseable"],
        "parse_error": parseability["parse_error"],
        "xml_namespace_present": parseability["xml_namespace_present"],
        "xml_root_tag": parseability["xml_root_tag"],
        "json_top_level_type": parseability["json_top_level_type"],
        "validator_passed": validation_passed,
        "validator_reason": validation_reason,
        "fallback_triggered": not validation_passed,
    }


def _validate_safety(rendered_body: str) -> tuple[bool, str]:
    for pattern in _SAFE_DENY_PATTERNS:
        if pattern.search(rendered_body):
            if pattern.pattern == r"https?://" and _is_allowed_xml_namespace(rendered_body):
                continue
            return False, f"Safety pattern denied: {pattern.pattern}"
    return True, "ok"


def _is_allowed_xml_namespace(rendered_body: str) -> bool:
    stripped = rendered_body.lstrip()
    return stripped.startswith("<") and any(pattern.search(rendered_body) for pattern in _SAFE_XML_NAMESPACE_PATTERNS)


def _validate_ec2_describe_instances(rendered_body: str) -> tuple[bool, str]:
    try:
        root = ElementTree.fromstring(rendered_body)
    except Exception as exc:
        return False, f"Schema validation failed (XML parse): {exc}"
    if "DescribeInstancesResponse" not in root.tag:
        return False, "Protocol validation failed: expected DescribeInstancesResponse root"
    if not re.findall(r"i-[0-9a-f]{8,17}", rendered_body):
        return False, "Protocol validation failed: missing valid instance id"
    return True, "ok"


def _validate_ssm_describe_instance_information(rendered_body: str) -> tuple[bool, str]:
    try:
        payload = json.loads(rendered_body)
    except Exception as exc:
        return False, f"Schema validation failed (JSON parse): {exc}"
    if not isinstance(payload, dict):
        return False, "Schema validation failed: payload must be object"
    instances = payload.get("InstanceInformationList")
    if not isinstance(instances, list):
        return False, "Protocol validation failed: InstanceInformationList must be list"
    for item in instances:
        if not isinstance(item, dict):
            return False, "Protocol validation failed: instance item must be object"
        iid = str(item.get("InstanceId", ""))
        if not re.match(r"^i-[0-9a-f]{8,17}$", iid):
            return False, "Protocol validation failed: invalid InstanceId"
        if item.get("PlatformType") not in {"Linux", "Windows", "MacOS"}:
            return False, "Protocol validation failed: invalid PlatformType"
    return True, "ok"


def _validate_world_state_consistency(rendered_body: str, world_state: dict[str, Any]) -> tuple[bool, str]:
    account_id = str(world_state.get("consistency_locks", {}).get("account_id", ""))
    if "arn:aws:" in rendered_body and account_id and account_id not in rendered_body:
        return False, "World-state validation failed: account_id lock mismatch"
    return True, "ok"


def _validate_non_empty_success(canonical: CanonicalRequest, rendered_body: str) -> tuple[bool, str]:
    if rendered_body.strip() == "{}":
        return False, "Quality validation failed: empty object success payload"
    try:
        payload = json.loads(rendered_body)
    except Exception:
        return True, "ok"
    if not isinstance(payload, dict):
        return True, "ok"
    required_members: dict[tuple[str, str], list[str]] = {
        ("ecr", "InitiateLayerUpload"): ["uploadId", "partSize"],
        ("ecr", "GetDownloadUrlForLayer"): ["downloadUrl", "layerDigest"],
        ("ecr", "CompleteLayerUpload"): ["uploadId", "layerDigest", "repositoryName"],
        ("ecr", "BatchCheckLayerAvailability"): ["layers"],
        ("ssm", "DescribeInstanceInformation"): ["InstanceInformationList"],
        ("sts", "DecodeAuthorizationMessage"): ["DecodedMessage"],
        ("secretsmanager", "ValidateResourcePolicy"): ["PolicyValidationPassed"],
    }
    for member in required_members.get((canonical.service, canonical.operation), []):
        if member not in payload:
            return False, f"Quality validation failed: missing core member {member}"
    return True, "ok"


def _parseability(body_format: str, rendered_body: str) -> dict[str, Any]:
    if body_format == "xml":
        try:
            root = ElementTree.fromstring(rendered_body)
            return {"parseable": True, "parse_error": "", "xml_namespace_present": root.tag.startswith("{"), "xml_root_tag": root.tag.split('}',1)[-1], "json_top_level_type": ""}
        except Exception as exc:
            return {"parseable": False, "parse_error": str(exc), "xml_namespace_present": False, "xml_root_tag": "", "json_top_level_type": ""}
    if body_format == "json":
        try:
            parsed = json.loads(rendered_body)
            return {"parseable": True, "parse_error": "", "xml_namespace_present": False, "xml_root_tag": "", "json_top_level_type": type(parsed).__name__}
        except Exception as exc:
            return {"parseable": False, "parse_error": str(exc), "xml_namespace_present": False, "xml_root_tag": "", "json_top_level_type": ""}
    return {"parseable": False, "parse_error": "Unsupported response format", "xml_namespace_present": False, "xml_root_tag": "", "json_top_level_type": ""}
