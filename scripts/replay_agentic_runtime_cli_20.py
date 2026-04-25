#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from moto.core.llm_agents.agent import handle_aws_request


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO_ROOT / "artifacts"
SOURCE_AUDIT = ARTIFACTS / "runtime_cli_20_audit_v2.json"
SOURCE_RESULTS = ARTIFACTS / "runtime_cli_20_results_v2.json"
OUT_RESULTS = ARTIFACTS / "agentic_runtime_cli_20_results.json"
OUT_AUDIT = ARTIFACTS / "agentic_runtime_cli_20_audit.json"
OUT_SUMMARY = ARTIFACTS / "agentic_runtime_cli_20_summary.md"


def main() -> int:
    os.environ["MOTO_LLM_ENV_FILE"] = ".env"
    os.environ["MOTO_LLM_RUNTIME_MODE"] = "agentic"
    os.environ["MOTO_LLM_AUDIT_FILE"] = str(OUT_AUDIT)

    source_audit = _load_json(SOURCE_AUDIT)
    source_results = _load_json(SOURCE_RESULTS)
    if not isinstance(source_audit, list) or not isinstance(source_results, list):
        raise ValueError("Expected list-shaped source audit/results files")

    if OUT_AUDIT.exists():
        OUT_AUDIT.unlink()

    rows: list[dict[str, Any]] = []
    for idx, (audit_row, result_row) in enumerate(zip(source_audit, source_results), start=1):
        req = audit_row["request"]
        response_body = handle_aws_request(
            service=req["service"],
            action=req["action"],
            url=req["url"],
            headers=dict(req["headers"]),
            body=req["body"],
            reason=f"agentic_replay:{req['reason']}",
            source="scripts.replay_agentic_runtime_cli_20",
        )
        latest = _load_last_audit(OUT_AUDIT)
        llm = latest.get("metrics", {}).get("llm", {})
        rows.append(
            {
                "index": idx,
                "label": result_row.get("label") or f"{req['service']} {req['action']}",
                "command": result_row.get("command", ""),
                "returncode": 0,
                "elapsed_ms": latest.get("metrics", {}).get("total_duration_ms"),
                "stdout": _pretty_body(response_body),
                "stderr": "",
                "llm_duration_ms": llm.get("duration_ms"),
                "usage": llm.get("usage"),
                "audit_request": latest.get("request", {}).get("canonical", {}),
                "validation_passed": latest.get("comparison_points", {}).get("validator_passed"),
                "llm_error": llm.get("error"),
                "llm_provider": llm.get("provider"),
            }
        )

    OUT_RESULTS.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SUMMARY.write_text(_render_summary(rows), encoding="utf-8")
    print(f"Wrote {OUT_RESULTS}")
    print(f"Wrote {OUT_AUDIT}")
    print(f"Wrote {OUT_SUMMARY}")
    print(_render_summary(rows))
    return 0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_last_audit(path: Path) -> dict[str, Any]:
    data = _load_json(path)
    if isinstance(data, list):
        return data[-1]
    if isinstance(data, dict):
        return data
    raise ValueError(f"Unexpected audit format: {path}")


def _pretty_body(body: str) -> str:
    text = str(body or "")
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, ensure_ascii=False, indent=4) + "\n"
    except Exception:
        return text


def _render_summary(rows: list[dict[str, Any]]) -> str:
    total_input = sum(int((row.get("usage") or {}).get("input_tokens", 0) or 0) for row in rows)
    total_output = sum(int((row.get("usage") or {}).get("output_tokens", 0) or 0) for row in rows)
    total_tokens = sum(int((row.get("usage") or {}).get("total_tokens", 0) or 0) for row in rows)
    total_time = sum(float(row.get("elapsed_ms") or 0.0) for row in rows)
    avg_input = total_input / len(rows) if rows else 0.0
    avg_output = total_output / len(rows) if rows else 0.0
    avg_tokens = total_tokens / len(rows) if rows else 0.0
    avg_time = total_time / len(rows) if rows else 0.0

    lines = [
        "# Agentic Runtime CLI 20 Summary",
        "",
        "| 순번 | 서비스 및 액션 (Action) | 입력 토큰 | 출력 토큰 | 전체 토큰 | 응답 시간 (ms) |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        canonical = row.get("audit_request", {})
        service = canonical.get("service", "-")
        operation = canonical.get("operation", "-")
        usage = row.get("usage") or {}
        lines.append(
            f"| {row['index']} | **{service}**: {operation} | "
            f"{int(usage.get('input_tokens', 0) or 0):,} | "
            f"{int(usage.get('output_tokens', 0) or 0):,} | "
            f"{int(usage.get('total_tokens', 0) or 0):,} | "
            f"{round(float(row.get('elapsed_ms') or 0.0)):,} |"
        )

    lines.extend(
        [
            "",
            "| 항목 | 합계 (Total) | 평균 (Average) |",
            "| --- | ---: | ---: |",
            f"| 입력 토큰 (Input) | {total_input:,} | {avg_input:,.2f} |",
            f"| 출력 토큰 (Output) | {total_output:,} | {avg_output:,.2f} |",
            f"| 전체 토큰 (Total) | {total_tokens:,} | {avg_tokens:,.2f} |",
            f"| 응답 시간 (Time) | {round(total_time):,} ms | {avg_time:,.2f} ms |",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
