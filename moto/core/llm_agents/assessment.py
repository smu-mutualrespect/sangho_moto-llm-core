from __future__ import annotations

import json
from typing import Any
from xml.etree import ElementTree

from .normalizer import CanonicalRequest


def build_comparison_points(
    canonical: CanonicalRequest,
    rendered_body: str,
    validation_passed: bool,
    validation_reason: str,
) -> dict[str, Any]:
    protocol_family = _expected_protocol_family(canonical)
    detected_format = _detect_body_format(rendered_body)
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


def _expected_protocol_family(canonical: CanonicalRequest) -> str:
    if canonical.service in {"ec2", "iam", "sts", "s3"}:
        return "xml"
    return "json"


def _detect_body_format(rendered_body: str) -> str:
    stripped = rendered_body.lstrip()
    if stripped.startswith("<"):
        return "xml"
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    return "text"


def _parseability(body_format: str, rendered_body: str) -> dict[str, Any]:
    if body_format == "xml":
        try:
            root = ElementTree.fromstring(rendered_body)
            return {
                "parseable": True,
                "parse_error": "",
                "xml_namespace_present": root.tag.startswith("{"),
                "xml_root_tag": root.tag.split("}", 1)[-1],
                "json_top_level_type": "",
            }
        except Exception as exc:
            return {
                "parseable": False,
                "parse_error": str(exc),
                "xml_namespace_present": False,
                "xml_root_tag": "",
                "json_top_level_type": "",
            }

    if body_format == "json":
        try:
            parsed = json.loads(rendered_body)
            return {
                "parseable": True,
                "parse_error": "",
                "xml_namespace_present": False,
                "xml_root_tag": "",
                "json_top_level_type": type(parsed).__name__,
            }
        except Exception as exc:
            return {
                "parseable": False,
                "parse_error": str(exc),
                "xml_namespace_present": False,
                "xml_root_tag": "",
                "json_top_level_type": "",
            }

    return {
        "parseable": False,
        "parse_error": "Unsupported response format",
        "xml_namespace_present": False,
        "xml_root_tag": "",
        "json_top_level_type": "",
    }
