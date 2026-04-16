#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moto.core.llm_agents.agent import handle_aws_request


def main() -> int:
    parser = argparse.ArgumentParser(description="Run tuning corpus in batches and persist structured summaries.")
    parser.add_argument("--corpus", default="artifacts/tuning/command_corpus.json")
    parser.add_argument("--artifacts-dir", default="artifacts/tuning/runs")
    parser.add_argument("--batch", type=int, default=0, help="Run one batch only. 0 means run all.")
    parser.add_argument("--env-file", default="", help="Optional env file for external provider credentials.")
    args = parser.parse_args()

    corpus_path = Path(args.corpus)
    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    scenarios = json.loads(corpus_path.read_text(encoding="utf-8"))
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for scenario in scenarios:
        grouped[int(scenario["batch"])].append(scenario)

    batches = [args.batch] if args.batch else sorted(grouped)
    index: dict[str, Any] = {"batches": []}
    for batch_no in batches:
        batch_dir = artifacts_dir / f"batch_{batch_no:02d}"
        batch_dir.mkdir(parents=True, exist_ok=True)
        batch_summary = run_batch(grouped[batch_no], batch_dir, args.env_file)
        (batch_dir / "summary.json").write_text(
            json.dumps(batch_summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (batch_dir / "summary.md").write_text(render_batch_markdown(batch_summary), encoding="utf-8")
        index["batches"].append(
            {
                "batch": batch_no,
                "summary_json": str(batch_dir / "summary.json"),
                "summary_md": str(batch_dir / "summary.md"),
            }
        )

    (artifacts_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(index, ensure_ascii=False, indent=2))
    return 0


def run_batch(
    scenarios: list[dict[str, Any]],
    batch_dir: Path,
    env_file: str,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        audit_path = batch_dir / f"{scenario['id']}.audit.json"
        env = os.environ.copy()
        env["MOTO_LLM_AUDIT_FILE"] = str(audit_path)
        if env_file:
            env["MOTO_LLM_ENV_FILE"] = env_file
        os.environ["MOTO_LLM_AUDIT_FILE"] = str(audit_path)
        if env_file:
            os.environ["MOTO_LLM_ENV_FILE"] = env_file

        headers = parse_header_list(scenario.get("headers", []))
        try:
            response_body = handle_aws_request(
                service=scenario["service"],
                action=scenario["action"],
                url=scenario["url"],
                headers=headers,
                body=scenario["body"],
                reason="tuning_batch_probe",
                source="scripts.run_honeypot_tuning_batches",
            )
            audit = load_last_audit(audit_path)
            heuristics = analyze_result(response_body, audit, scenario)
            result = {
                "scenario": scenario,
                "response_body": response_body,
                "audit": audit,
                "heuristics": heuristics,
            }
        except Exception as exc:
            result = {
                "scenario": scenario,
                "response_body": "",
                "audit": {},
                "heuristics": {
                    "validation_passed": False,
                    "safe_fallback": False,
                    "llm_error": "runner_exception",
                    "expected_echo_count": len(scenario.get("expected_echo", [])),
                    "echoed": [],
                    "missing_echo": list(scenario.get("expected_echo", [])),
                    "placeholder_hits": [],
                    "exception": f"{type(exc).__name__}: {exc}",
                },
            }
        results.append(result)
        (batch_dir / f"{scenario['id']}.result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    aggregate = aggregate_batch(results)
    return {"results": results, "aggregate": aggregate}


def parse_header_list(items: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in items:
        key, value = item.split("=", 1)
        headers[key] = value
    return headers


def load_last_audit(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data[-1] if data else {}
    return data


def analyze_result(
    response_body: str,
    audit: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    validation_passed = bool(audit.get("response", {}).get("validation_passed"))
    safe_fallback = "Request blocked by honeypot guardrails" in response_body
    llm_error = audit.get("metrics", {}).get("llm", {}).get("error")
    expected_echo = list(scenario.get("expected_echo", []))
    echoed = []
    missing = []
    request_params = audit.get("request", {}).get("canonical", {})
    del request_params

    for key in expected_echo:
        raw = _find_expected_value(key, scenario["body"])
        if raw and raw in response_body:
            echoed.append(key)
        else:
            missing.append(key)

    placeholder_hits = []
    for label, token in [
        ("IPAddress", '"IPAddress": "IPAddress"'),
        ("IamRole", '"IamRole": "IamRole"'),
        ("ServiceCredentialAlias", ">ServiceCredentialAlias<"),
        ("DetailedStatus", '"DetailedStatus": "ssm-describeinstanceinformation"'),
        ("SyntheticName", "ssm-describeinstanceinformation"),
    ]:
        if token in response_body:
            placeholder_hits.append(label)

    if "<ServiceCredentialAlias>ServiceCredentialAlias</ServiceCredentialAlias>" in response_body:
        placeholder_hits.append("ServiceCredentialAlias")

    return {
        "validation_passed": validation_passed,
        "safe_fallback": safe_fallback,
        "llm_error": llm_error,
        "expected_echo_count": len(expected_echo),
        "echoed": echoed,
        "missing_echo": missing,
        "placeholder_hits": placeholder_hits,
    }


def _find_expected_value(key: str, body: str) -> str:
    try:
        if body.strip().startswith("{"):
            parsed = json.loads(body)
            value = parsed.get(key)
            if value is None and key[:1].islower():
                alt = key[:1].upper() + key[1:]
                value = parsed.get(alt)
            if isinstance(value, list):
                return str(value[0]) if value else ""
            return str(value or "")
    except Exception:
        pass

    for part in body.split("&"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k == key or k.lower() == key.lower():
            return v
    return ""


def aggregate_batch(results: list[dict[str, Any]]) -> dict[str, Any]:
    validation_passed = 0
    safe_fallback = 0
    missing_echo = 0
    placeholder_hits = 0
    llm_provider_failures = 0

    for item in results:
        heuristics = item["heuristics"]
        if heuristics["validation_passed"]:
            validation_passed += 1
        if heuristics["safe_fallback"]:
            safe_fallback += 1
        if heuristics["missing_echo"]:
            missing_echo += len(heuristics["missing_echo"])
        if heuristics["placeholder_hits"]:
            placeholder_hits += len(heuristics["placeholder_hits"])
        if heuristics["llm_error"] == "provider_call_failed":
            llm_provider_failures += 1

    return {
        "scenario_count": len(results),
        "validation_passed": validation_passed,
        "safe_fallback": safe_fallback,
        "missing_echo_total": missing_echo,
        "placeholder_hits_total": placeholder_hits,
        "llm_provider_failures": llm_provider_failures,
    }


def render_batch_markdown(summary: dict[str, Any]) -> str:
    agg = summary["aggregate"]
    lines = [
        "# Batch Summary",
        "",
        f"- scenarios: {agg['scenario_count']}",
        f"- validation_passed: {agg['validation_passed']}",
        f"- safe_fallback: {agg['safe_fallback']}",
        f"- missing_echo_total: {agg['missing_echo_total']}",
        f"- placeholder_hits_total: {agg['placeholder_hits_total']}",
        f"- llm_provider_failures: {agg['llm_provider_failures']}",
        "",
        "| id | label | valid | fallback | missing_echo | placeholders |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in summary["results"]:
        heuristics = item["heuristics"]
        scenario = item["scenario"]
        lines.append(
            f"| {scenario['id']} | {scenario['label']} | {heuristics['validation_passed']} | {heuristics['safe_fallback']} | {','.join(heuristics['missing_echo']) or '-'} | {','.join(heuristics['placeholder_hits']) or '-'} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
