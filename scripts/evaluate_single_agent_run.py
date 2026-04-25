#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from xml.etree import ElementTree


PLACEHOLDER_EXACT = {
    "modelName",
    "providerName",
    "Key",
    "Value",
    "Bucket",
    "Prefix",
    "Code",
    "Description",
    "EventType",
    "IoPerformance",
    "UploadPolicySignature",
    "IPAddress",
    "IamRole",
    "ServiceCredentialAlias",
    "Progress",
}

PLACEHOLDER_PATTERNS = [
    re.compile(r"synthetic\s+[a-z0-9:.-]+", re.IGNORECASE),
    re.compile(r"^ec2-[0-9a-f]{8}$"),
    re.compile(r"^ssm-[0-9a-f]{8}$"),
    re.compile(r"^bedrock-[0-9a-f]{8}$"),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate one single-agent run from result JSON or audit JSON"
    )
    parser.add_argument("run_file", help="runtime result JSON or audit JSON")
    parser.add_argument(
        "--golden-file",
        default="",
        help="Optional real AWS result JSON keyed by label/index/command for comparison",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write the full evaluation JSON",
    )
    args = parser.parse_args()

    run_path = Path(args.run_file)
    rows = _load_rows(run_path)
    golden_index = _load_golden_index(Path(args.golden_file)) if args.golden_file else {}

    evaluated = [_evaluate_row(row, golden_index) for row in rows]
    summary = _build_summary(evaluated)
    report = {
        "source": str(run_path),
        "row_count": len(evaluated),
        "summary": summary,
        "rows": evaluated,
    }

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_summary(report)
    return 0


def _load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "request" in data[0] and "response" in data[0]:
            return [_normalize_audit_row(item) for item in data if isinstance(item, dict)]
        return [_normalize_result_row(item) for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            return [_normalize_result_row(item) for item in data["results"] if isinstance(item, dict)]
        if "request" in data and "response" in data:
            return [_normalize_audit_row(data)]
        return [_normalize_result_row(data)]
    raise ValueError(f"Unsupported JSON structure: {path}")


def _normalize_result_row(row: dict[str, Any]) -> dict[str, Any]:
    usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
    audit_request = row.get("audit_request") if isinstance(row.get("audit_request"), dict) else {}
    return {
        "index": row.get("index"),
        "label": row.get("label") or _guess_label_from_command(str(row.get("command", ""))),
        "command": str(row.get("command", "")),
        "service": str(audit_request.get("service", _service_from_label(str(row.get("label", ""))))).lower(),
        "operation": str(audit_request.get("operation", "")),
        "body": str(row.get("stdout", "")).strip(),
        "returncode": row.get("returncode"),
        "elapsed_ms": _float_or_none(row.get("elapsed_ms")),
        "llm_duration_ms": _float_or_none(row.get("llm_duration_ms")),
        "usage": usage,
        "validation_passed": _bool_or_none(row.get("validation_passed")),
        "llm_provider": row.get("llm_provider"),
        "llm_error": row.get("llm_error"),
        "request_params": _extract_cli_request_params(str(row.get("command", ""))),
        "comparison_points": {},
    }


def _normalize_audit_row(row: dict[str, Any]) -> dict[str, Any]:
    request = row.get("request", {}) if isinstance(row.get("request"), dict) else {}
    canonical = request.get("canonical", {}) if isinstance(request.get("canonical"), dict) else {}
    metrics = row.get("metrics", {}) if isinstance(row.get("metrics"), dict) else {}
    llm = metrics.get("llm", {}) if isinstance(metrics.get("llm"), dict) else {}
    response = row.get("response", {}) if isinstance(row.get("response"), dict) else {}
    return {
        "index": row.get("index"),
        "label": row.get("label") or _command_key_from_audit(request, canonical),
        "command": str(row.get("command", "")),
        "service": str(canonical.get("service") or request.get("service") or "").lower(),
        "operation": str(canonical.get("operation") or request.get("action") or ""),
        "body": str(response.get("body", "")).strip(),
        "returncode": row.get("returncode"),
        "elapsed_ms": _float_or_none(metrics.get("total_duration_ms")),
        "llm_duration_ms": _float_or_none(llm.get("duration_ms")),
        "usage": llm.get("usage") if isinstance(llm.get("usage"), dict) else {},
        "validation_passed": _bool_or_none(
            response.get("validation_passed", row.get("comparison_points", {}).get("validator_passed"))
        ),
        "llm_provider": llm.get("provider"),
        "llm_error": llm.get("error"),
        "request_params": canonical.get("request_params") if isinstance(canonical.get("request_params"), dict) else {},
        "comparison_points": row.get("comparison_points", {}) if isinstance(row.get("comparison_points"), dict) else {},
    }


def _load_golden_index(path: Path) -> dict[str, dict[str, Any]]:
    rows = _load_rows(path)
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key in _candidate_keys(row):
            index[key] = row
    return index


def _evaluate_row(row: dict[str, Any], golden_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    parsed = _parse_body(row["body"])
    parseable = parsed["parseable"]
    placeholder_hits = _collect_placeholder_hits(parsed["parsed"], row["body"])
    echo = _evaluate_echo(row["request_params"], parsed["parsed"], row["body"])

    golden = _match_golden(row, golden_index)
    structure = _compare_structure(parsed["parsed"], golden["parsed"]) if golden else None

    score = 100
    if row.get("returncode") not in (None, 0):
        score -= 40
    if not parseable:
        score -= 35
    score -= min(len(placeholder_hits) * 5, 20)
    score -= min(len(echo["missing"]) * 4, 20)
    if structure:
        score -= min(structure["missing_key_count"] * 3, 15)
        score -= min(structure["extra_key_count"] * 1, 10)
    if row.get("validation_passed") is False:
        score -= 10
    score = max(score, 0)

    return {
        "index": row.get("index"),
        "label": row.get("label"),
        "service": row.get("service"),
        "operation": row.get("operation"),
        "returncode": row.get("returncode"),
        "elapsed_ms": row.get("elapsed_ms"),
        "llm_duration_ms": row.get("llm_duration_ms"),
        "usage": row.get("usage"),
        "validation_passed": row.get("validation_passed"),
        "llm_provider": row.get("llm_provider"),
        "llm_error": row.get("llm_error"),
        "format": parsed["format"],
        "parseable": parseable,
        "top_level_type": parsed["top_level_type"],
        "placeholder_hits": placeholder_hits,
        "echo": echo,
        "golden_match": golden is not None,
        "structure": structure,
        "score": score,
    }


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    input_tokens = [int(item["usage"].get("input_tokens", 0) or 0) for item in rows]
    output_tokens = [int(item["usage"].get("output_tokens", 0) or 0) for item in rows]
    total_tokens = [int(item["usage"].get("total_tokens", 0) or 0) for item in rows]
    elapsed = [float(item["elapsed_ms"]) for item in rows if item.get("elapsed_ms") is not None]
    llm_elapsed = [float(item["llm_duration_ms"]) for item in rows if item.get("llm_duration_ms") is not None]

    return {
        "parseable_count": sum(1 for item in rows if item["parseable"]),
        "validation_passed_count": sum(1 for item in rows if item.get("validation_passed") is True),
        "golden_matched_count": sum(1 for item in rows if item["golden_match"]),
        "placeholder_hit_rows": sum(1 for item in rows if item["placeholder_hits"]),
        "missing_echo_rows": sum(1 for item in rows if item["echo"]["missing"]),
        "average_score": round(_avg([float(item["score"]) for item in rows]), 2),
        "total_input_tokens": sum(input_tokens),
        "total_output_tokens": sum(output_tokens),
        "total_tokens": sum(total_tokens),
        "avg_input_tokens": round(_avg(input_tokens), 2),
        "avg_output_tokens": round(_avg(output_tokens), 2),
        "avg_total_tokens": round(_avg(total_tokens), 2),
        "avg_elapsed_ms": round(_avg(elapsed), 2),
        "avg_llm_duration_ms": round(_avg(llm_elapsed), 2),
        "slowest": _extreme_row(rows, key="elapsed_ms", highest=True),
        "fastest": _extreme_row(rows, key="elapsed_ms", highest=False),
        "most_tokens": _extreme_row(rows, key="usage.total_tokens", highest=True),
        "lowest_score": _extreme_row(rows, key="score", highest=False),
    }


def _match_golden(row: dict[str, Any], golden_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for key in _candidate_keys(row):
        if key in golden_index:
            matched = golden_index[key]
            parsed = _parse_body(matched["body"])
            return {
                "row": matched,
                "parsed": parsed["parsed"],
            }
    return None


def _candidate_keys(row: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    if row.get("label"):
        keys.append(f"label:{row['label']}")
    if row.get("index") is not None:
        keys.append(f"index:{row['index']}")
    service = str(row.get("service", "")).lower()
    operation = str(row.get("operation", ""))
    if service and operation:
        keys.append(f"op:{service}:{operation}")
    command = str(row.get("command", "")).strip()
    if command:
        keys.append(f"command:{command}")
    return keys


def _parse_body(body: str) -> dict[str, Any]:
    text = str(body or "").strip()
    if not text:
        return {"format": "empty", "parseable": True, "parsed": "", "top_level_type": "empty"}
    if text.startswith("<"):
        try:
            root = ElementTree.fromstring(text)
            return {
                "format": "xml",
                "parseable": True,
                "parsed": _xml_to_obj(root),
                "top_level_type": "dict",
            }
        except Exception:
            return {"format": "xml", "parseable": False, "parsed": None, "top_level_type": "invalid"}
    try:
        parsed = json.loads(text)
        return {
            "format": "json",
            "parseable": True,
            "parsed": parsed,
            "top_level_type": type(parsed).__name__,
        }
    except Exception:
        return {"format": "text", "parseable": False, "parsed": None, "top_level_type": "invalid"}


def _xml_to_obj(elem: ElementTree.Element) -> Any:
    children = list(elem)
    if not children:
        return (elem.text or "").strip()

    grouped: dict[str, list[Any]] = {}
    for child in children:
        tag = child.tag.split("}", 1)[-1]
        grouped.setdefault(tag, []).append(_xml_to_obj(child))

    out: dict[str, Any] = {}
    for key, values in grouped.items():
        out[key] = values[0] if len(values) == 1 else values
    return out


def _evaluate_echo(request_params: dict[str, Any], parsed_body: Any, raw_body: str) -> dict[str, Any]:
    expected = _flatten_identifiers(request_params)
    echoed: list[str] = []
    missing: list[str] = []
    haystack = json.dumps(parsed_body, ensure_ascii=False) if parsed_body is not None and parsed_body != "" else raw_body

    for key, value in expected.items():
        if len(value) < 4:
            continue
        if value in haystack:
            echoed.append(key)
        else:
            missing.append(key)

    return {
        "expected_count": len(expected),
        "echoed": echoed,
        "missing": missing,
    }


def _compare_structure(actual: Any, golden: Any) -> dict[str, Any] | None:
    if actual is None or golden is None:
        return None
    if isinstance(actual, dict) and isinstance(golden, dict):
        actual_keys = set(actual.keys())
        golden_keys = set(golden.keys())
        return {
            "missing_keys": sorted(golden_keys - actual_keys),
            "extra_keys": sorted(actual_keys - golden_keys),
            "missing_key_count": len(golden_keys - actual_keys),
            "extra_key_count": len(actual_keys - golden_keys),
        }
    if isinstance(actual, list) and isinstance(golden, list):
        if not actual or not golden:
            return {
                "missing_keys": [],
                "extra_keys": [],
                "missing_key_count": 0,
                "extra_key_count": 0,
            }
        return _compare_structure(actual[0], golden[0])
    return {
        "missing_keys": [],
        "extra_keys": [],
        "missing_key_count": 0,
        "extra_key_count": 0,
    }


def _collect_placeholder_hits(parsed_body: Any, raw_body: str) -> list[str]:
    hits: list[str] = []
    for value in _walk_values(parsed_body):
        if not isinstance(value, str):
            continue
        if value in PLACEHOLDER_EXACT and value not in hits:
            hits.append(value)
            continue
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(value):
                token = pattern.pattern
                if token not in hits:
                    hits.append(token)
    for exact in sorted(PLACEHOLDER_EXACT):
        quoted = f'"{exact}"'
        if quoted in raw_body and exact not in hits:
            hits.append(exact)
    return hits


def _walk_values(value: Any) -> list[Any]:
    items: list[Any] = []
    if isinstance(value, dict):
        for nested in value.values():
            items.extend(_walk_values(nested))
    elif isinstance(value, list):
        for nested in value:
            items.extend(_walk_values(nested))
    else:
        items.append(value)
    return items


def _flatten_identifiers(request_params: dict[str, Any]) -> dict[str, str]:
    flattened: dict[str, str] = {}

    def visit(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                next_prefix = key if not prefix else f"{prefix}.{key}"
                visit(next_prefix, nested)
            return
        if isinstance(value, list):
            if value:
                visit(prefix, value[0])
            return
        key = prefix.split(".")[-1]
        lowered = key.lower()
        if any(token in lowered for token in ("id", "name", "arn", "digest", "bucket", "secret", "repository", "user")):
            flattened[key] = str(value)

    if isinstance(request_params, dict):
        visit("", request_params)
    return flattened


def _extract_cli_request_params(command: str) -> dict[str, Any]:
    params: dict[str, Any] = {}

    for key, value in re.findall(r"--([a-z0-9-]+)\s+('(?:[^']*)'|\"(?:[^\"]*)\"|[^\s]+)", command):
        cleaned = value.strip("'\"")
        if key in {"endpoint-url"}:
            continue
        normalized_key = "".join(part.capitalize() if idx else part for idx, part in enumerate(key.split("-")))
        if normalized_key.endswith("Ids") or normalized_key.endswith("Digests"):
            params[normalized_key] = [cleaned]
        else:
            params[normalized_key] = cleaned

    query_match = re.search(r"Action=[^ ]+", command)
    if query_match:
        for key, values in parse_qs(query_match.group(0), keep_blank_values=True).items():
            params[key] = values[0] if len(values) == 1 else values
    return params


def _guess_label_from_command(command: str) -> str:
    tokens = command.split()
    if len(tokens) < 3:
        return command
    return f"{tokens[1]} {tokens[2]}"


def _service_from_label(label: str) -> str:
    return label.split()[0] if label else ""


def _command_key_from_audit(request: dict[str, Any], canonical: dict[str, Any]) -> str:
    service = str(canonical.get("service") or request.get("service") or "unknown").lower()
    operation = str(canonical.get("operation") or request.get("action") or "unknown")
    return f"{service}:{operation}"


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _avg(values: list[float] | list[int]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _extreme_row(rows: list[dict[str, Any]], *, key: str, highest: bool) -> dict[str, Any] | None:
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        value = _nested_get(row, key)
        if value is None:
            continue
        try:
            scored.append((float(value), row))
        except Exception:
            continue
    if not scored:
        return None
    picked = max(scored, key=lambda item: item[0]) if highest else min(scored, key=lambda item: item[0])
    value, row = picked
    return {
        "label": row.get("label"),
        "value": round(value, 3),
    }


def _nested_get(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _print_summary(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(f"Source: {report['source']}")
    print(f"Rows: {report['row_count']}")
    print("")
    print("| Metric | Value |")
    print("| --- | ---: |")
    print(f"| Parseable | {summary['parseable_count']}/{report['row_count']} |")
    print(f"| Validation passed | {summary['validation_passed_count']}/{report['row_count']} |")
    print(f"| Golden matched | {summary['golden_matched_count']}/{report['row_count']} |")
    print(f"| Placeholder-hit rows | {summary['placeholder_hit_rows']} |")
    print(f"| Missing-echo rows | {summary['missing_echo_rows']} |")
    print(f"| Avg score | {summary['average_score']} |")
    print(f"| Total input tokens | {summary['total_input_tokens']} |")
    print(f"| Total output tokens | {summary['total_output_tokens']} |")
    print(f"| Total tokens | {summary['total_tokens']} |")
    print(f"| Avg elapsed ms | {summary['avg_elapsed_ms']} |")
    print(f"| Avg LLM duration ms | {summary['avg_llm_duration_ms']} |")
    print("")
    print("| Label | Score | Parse | Validation | Time ms | Tokens | Notes |")
    print("| --- | ---: | --- | --- | ---: | ---: | --- |")
    for row in report["rows"]:
        notes: list[str] = []
        if row["placeholder_hits"]:
            notes.append(f"placeholder={len(row['placeholder_hits'])}")
        if row["echo"]["missing"]:
            notes.append(f"missing_echo={len(row['echo']['missing'])}")
        if row["structure"] and row["structure"]["missing_key_count"]:
            notes.append(f"missing_keys={row['structure']['missing_key_count']}")
        if row.get("llm_error"):
            notes.append(f"llm_error={row['llm_error']}")
        total_tokens = int(row["usage"].get("total_tokens", 0) or 0)
        print(
            f"| {row['label']} | {row['score']} | {row['parseable']} | {row.get('validation_passed')} | "
            f"{int(row['elapsed_ms'] or 0)} | {total_tokens} | {', '.join(notes) or '-'} |"
        )


if __name__ == "__main__":
    raise SystemExit(main())
