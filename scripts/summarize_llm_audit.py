#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize LLM audit logs with protocol and quality comparison points"
    )
    parser.add_argument("audit_files", nargs="+")
    parser.add_argument(
        "--mode",
        choices=("summary", "compare"),
        default="summary",
        help="summary: model-level aggregate, compare: command-level nano/mini table",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-5-nano", "gpt-5-mini"],
        help="Model names to compare when using --mode compare",
    )
    args = parser.parse_args()

    rows = []
    for audit_file in args.audit_files:
        rows.extend(_load_rows(Path(audit_file)))

    if args.mode == "compare":
        _print_compare(rows, args.models)
        return 0

    _print_summary(rows)
    return 0


def _print_summary(rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        llm = row.get("metrics", {}).get("llm", {})
        model = str(llm.get("model", "unknown"))
        grouped[model].append(row)

    print(
        "| model | calls | validator pass | format match | parseable | xml namespace ok | avg total ms | avg llm ms | avg total tokens |"
    )
    print(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )

    for model, items in sorted(grouped.items()):
        calls = len(items)
        validator_pass = sum(1 for item in items if item.get("comparison_points", {}).get("validator_passed"))
        format_match = sum(1 for item in items if item.get("comparison_points", {}).get("format_match"))
        parseable = sum(1 for item in items if item.get("comparison_points", {}).get("response_parseable"))
        xml_namespace = sum(
            1
            for item in items
            if item.get("comparison_points", {}).get("xml_namespace_present")
            or item.get("comparison_points", {}).get("protocol_family_expected") != "xml"
        )
        avg_total_ms = _avg([item.get("metrics", {}).get("total_duration_ms", 0.0) for item in items])
        avg_llm_ms = _avg([item.get("metrics", {}).get("llm", {}).get("duration_ms", 0.0) for item in items])
        avg_total_tokens = _avg(
            [
                item.get("metrics", {}).get("llm", {}).get("usage", {}).get("total_tokens", 0.0)
                for item in items
            ]
        )
        print(
            f"| {model} | {calls} | {validator_pass}/{calls} | {format_match}/{calls} | {parseable}/{calls} | {xml_namespace}/{calls} | {avg_total_ms:.1f} | {avg_llm_ms:.1f} | {avg_total_tokens:.1f} |"
        )

 
def _print_compare(rows: list[dict[str, Any]], models: list[str]) -> None:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        model = str(row.get("metrics", {}).get("llm", {}).get("model", "unknown"))
        if model not in models:
            continue
        command_key = _command_key(row)
        grouped[command_key][model] = row

    headers = ["명령어"]
    for model in models:
        alias = _model_alias(model)
        headers.extend(
            [
                f"{alias} 응답",
                f"{alias} 비교",
                f"{alias} 시간",
            ]
        )

    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")

    included_rows: list[dict[str, Any]] = []
    for command_key in sorted(grouped):
        row_cells = [_command_display(command_key)]
        command_rows = grouped[command_key]
        for model in models:
            row = command_rows.get(model)
            if row is None:
                row_cells.extend(["-", "-", "-"])
                continue
            included_rows.append(row)
            row_cells.extend(
                [
                    _single_line_jsonish(row.get("response", {}).get("body", "")),
                    _comparison_cell(row),
                    _timing_cell(row),
                ]
            )
        print("| " + " | ".join(row_cells) + " |")

    if not included_rows:
        return

    summary_cells = ["전체"]
    for model in models:
        model_rows = [row for row in included_rows if row.get("metrics", {}).get("llm", {}).get("model") == model]
        if not model_rows:
            summary_cells.extend(["-", "-", "-"])
            continue
        summary_cells.extend(
            [
                _success_summary(model_rows),
                _quality_summary(model_rows),
                _timing_summary(model_rows),
            ]
        )
    print("| " + " | ".join(summary_cells) + " |")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _command_key(row: dict[str, Any]) -> str:
    request = row.get("request", {})
    service = str(request.get("service", "unknown")).lower()
    canonical = request.get("canonical", {})
    operation = str(canonical.get("operation") or request.get("action") or "unknown")
    return f"{service} {_to_kebab_case(operation)}"


def _command_display(command_key: str) -> str:
    return command_key


def _model_alias(model: str) -> str:
    if model.startswith("gpt-5-"):
        return model.removeprefix("gpt-5-")
    return model


def _to_kebab_case(value: str) -> str:
    value = value.replace(":", " ")
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    value = re.sub(r"[\s_]+", "-", value)
    return value.strip("-").lower()


def _single_line_jsonish(body: str, limit: int = 160) -> str:
    compact = " ".join(str(body).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _comparison_cell(row: dict[str, Any]) -> str:
    points = row.get("comparison_points", {})
    format_match = _yn(points.get("format_match"))
    parseable = _yn(points.get("response_parseable"))
    validator = _yn(points.get("validator_passed"))
    xml_namespace_ok = _yn(
        points.get("xml_namespace_present")
        or points.get("protocol_family_expected") != "xml"
    )
    fallback = _yn(points.get("fallback_triggered"))
    return (
        f"format {format_match}, "
        f"parse {parseable}, "
        f"validator {validator}, "
        f"xml ns {xml_namespace_ok}, "
        f"fallback {fallback}"
    )


def _timing_cell(row: dict[str, Any]) -> str:
    metrics = row.get("metrics", {})
    llm = metrics.get("llm", {})
    total_ms = float(metrics.get("total_duration_ms", 0.0))
    llm_ms = float(llm.get("duration_ms", 0.0))
    return f"CLI {total_ms:.0f}ms, LLM {llm_ms:.0f}ms"


def _success_summary(rows: list[dict[str, Any]]) -> str:
    passed = sum(
        1 for row in rows if row.get("response", {}).get("validation_passed") is True
    )
    return f"{passed}/{len(rows)} 성공"


def _quality_summary(rows: list[dict[str, Any]]) -> str:
    format_match = sum(
        1 for row in rows if row.get("comparison_points", {}).get("format_match")
    )
    parseable = sum(
        1 for row in rows if row.get("comparison_points", {}).get("response_parseable")
    )
    validator = sum(
        1 for row in rows if row.get("comparison_points", {}).get("validator_passed")
    )
    return (
        f"format {format_match}/{len(rows)}, "
        f"parse {parseable}/{len(rows)}, "
        f"validator {validator}/{len(rows)}"
    )


def _timing_summary(rows: list[dict[str, Any]]) -> str:
    avg_total_ms = _avg(
        [float(row.get("metrics", {}).get("total_duration_ms", 0.0)) for row in rows]
    )
    avg_llm_ms = _avg(
        [float(row.get("metrics", {}).get("llm", {}).get("duration_ms", 0.0)) for row in rows]
    )
    return f"평균 CLI {avg_total_ms:.0f}ms, 평균 LLM {avg_llm_ms:.0f}ms"


def _yn(value: Any) -> str:
    return "Y" if bool(value) else "N"


if __name__ == "__main__":
    raise SystemExit(main())
