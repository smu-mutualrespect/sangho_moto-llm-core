#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Scenario:
    label: str
    service: str
    action: str
    url: str
    body: str
    headers: tuple[str, ...] = ()


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        label="ecr batch-check-layer-availability",
        service="ecr",
        action="BatchCheckLayerAvailability",
        url="https://api.ecr.ap-northeast-2.amazonaws.com/",
        body='{"repositoryName":"demo","layerDigests":["sha256:abc"]}',
        headers=(
            "X-Amz-Target=AmazonEC2ContainerRegistry_V20150921.BatchCheckLayerAvailability",
            "Content-Type=application/x-amz-json-1.1",
        ),
    ),
    Scenario(
        label="ecr get-download-url-for-layer",
        service="ecr",
        action="GetDownloadUrlForLayer",
        url="https://api.ecr.ap-northeast-2.amazonaws.com/",
        body='{"repositoryName":"demo","layerDigest":"sha256:abc"}',
        headers=(
            "X-Amz-Target=AmazonEC2ContainerRegistry_V20150921.GetDownloadUrlForLayer",
            "Content-Type=application/x-amz-json-1.1",
        ),
    ),
    Scenario(
        label="ecr initiate-layer-upload",
        service="ecr",
        action="InitiateLayerUpload",
        url="https://api.ecr.ap-northeast-2.amazonaws.com/",
        body='{"repositoryName":"demo"}',
        headers=(
            "X-Amz-Target=AmazonEC2ContainerRegistry_V20150921.InitiateLayerUpload",
            "Content-Type=application/x-amz-json-1.1",
        ),
    ),
    Scenario(
        label="ecr complete-layer-upload",
        service="ecr",
        action="CompleteLayerUpload",
        url="https://api.ecr.ap-northeast-2.amazonaws.com/",
        body='{"repositoryName":"demo","uploadId":"test","layerDigests":["sha256:abc"]}',
        headers=(
            "X-Amz-Target=AmazonEC2ContainerRegistry_V20150921.CompleteLayerUpload",
            "Content-Type=application/x-amz-json-1.1",
        ),
    ),
    Scenario(
        label="ssm describe-instance-information",
        service="ssm",
        action="DescribeInstanceInformation",
        url="https://ssm.ap-northeast-2.amazonaws.com/",
        body="Action=DescribeInstanceInformation&Version=2014-11-06",
        headers=("Content-Type=application/x-www-form-urlencoded; charset=utf-8",),
    ),
    Scenario(
        label="iam create-service-specific-credential",
        service="iam",
        action="CreateServiceSpecificCredential",
        url="https://iam.amazonaws.com/",
        body="Action=CreateServiceSpecificCredential&ServiceName=codecommit.amazonaws.com&UserName=victim-admin&Version=2010-05-08",
        headers=("Content-Type=application/x-www-form-urlencoded; charset=utf-8",),
    ),
    Scenario(
        label="iam get-context-keys-for-principal-policy",
        service="iam",
        action="GetContextKeysForPrincipalPolicy",
        url="https://iam.amazonaws.com/",
        body="Action=GetContextKeysForPrincipalPolicy&PolicySourceArn=arn%3Aaws%3Aiam%3A%3A123456789012%3Auser%2Fvictim-admin&Version=2010-05-08",
        headers=("Content-Type=application/x-www-form-urlencoded; charset=utf-8",),
    ),
    Scenario(
        label="sts decode-authorization-message",
        service="sts",
        action="DecodeAuthorizationMessage",
        url="https://sts.amazonaws.com/",
        body="Action=DecodeAuthorizationMessage&EncodedMessage=ZmFrZS1hdXRob3JpemF0aW9uLW1lc3NhZ2U%3D&Version=2011-06-15",
        headers=("Content-Type=application/x-www-form-urlencoded; charset=utf-8",),
    ),
    Scenario(
        label="secretsmanager validate-resource-policy",
        service="secretsmanager",
        action="ValidateResourcePolicy",
        url="https://secretsmanager.ap-northeast-2.amazonaws.com/",
        body='{"SecretId":"prod/db/password","ResourcePolicy":"{\\"Version\\":\\"2012-10-17\\",\\"Statement\\":[{\\"Effect\\":\\"Allow\\",\\"Principal\\":\\"*\\",\\"Action\\":\\"secretsmanager:GetSecretValue\\",\\"Resource\\":\\"*\\"}]}"}',
        headers=(
            "X-Amz-Target=secretsmanager.ValidateResourcePolicy",
            "Content-Type=application/x-amz-json-1.1",
        ),
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the fallback benchmark matrix for nano/mini and print a markdown table"
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-5-nano", "gpt-5-mini"],
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts/benchmark_matrix",
    )
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict[str, dict[str, Any]]] = {}
    for scenario in SCENARIOS:
        results[scenario.label] = {}
        for model in args.models:
            results[scenario.label][model] = _run_scenario(
                scenario=scenario,
                model=model,
                env_file=args.env_file,
                artifacts_dir=artifacts_dir,
            )

    _print_markdown_table(results, args.models)
    return 0


def _run_scenario(
    *,
    scenario: Scenario,
    model: str,
    env_file: str,
    artifacts_dir: Path,
) -> dict[str, Any]:
    audit_path = artifacts_dir / f"{model}__{scenario.label.replace(' ', '_')}.json"
    env = os.environ.copy()
    env["MOTO_LLM_OPENAI_MODEL"] = model
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

    command = [
        "python3",
        "scripts/run_llm_agent_call.py",
        "--service",
        scenario.service,
        "--action",
        scenario.action,
        "--url",
        scenario.url,
        "--body",
        scenario.body,
        "--audit-file",
        str(audit_path),
        "--env-file",
        env_file,
    ]
    for header in scenario.headers:
        command.extend(["--header", header])

    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    record: dict[str, Any] = {
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "returncode": completed.returncode,
    }

    if audit_path.exists():
        data = json.loads(audit_path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else [data]
        if rows:
            record["audit"] = rows[-1]
    return record


def _print_markdown_table(results: dict[str, dict[str, dict[str, Any]]], models: list[str]) -> None:
    aliases = [_model_alias(model) for model in models]
    headers = ["명령어"]
    for alias in aliases:
        headers.extend([f"{alias} 응답", f"{alias} 시간"])
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")

    for label, model_results in results.items():
        row = [label]
        for model in models:
            result = model_results[model]
            row.append(_response_cell(result))
            row.append(_timing_cell(result))
        print("| " + " | ".join(row) + " |")

    summary = ["전체"]
    for model in models:
        model_results = [results[label][model] for label in results]
        summary.append(_success_summary(model_results))
        summary.append(_avg_timing_summary(model_results))
    print("| " + " | ".join(summary) + " |")


def _response_cell(result: dict[str, Any]) -> str:
    audit = result.get("audit", {})
    body = audit.get("response", {}).get("body")
    if body is None:
        body = result.get("stderr") or result.get("stdout") or f"process_failed:{result.get('returncode')}"
    return _compact(str(body))


def _timing_cell(result: dict[str, Any]) -> str:
    audit = result.get("audit", {})
    metrics = audit.get("metrics", {})
    llm = metrics.get("llm", {})
    total_ms = metrics.get("total_duration_ms")
    llm_ms = llm.get("duration_ms")
    if total_ms is None or llm_ms is None:
        return f"rc={result.get('returncode')}"
    return f"CLI {float(total_ms):.0f}ms, LLM {float(llm_ms):.0f}ms"


def _success_summary(results: list[dict[str, Any]]) -> str:
    passed = 0
    for result in results:
        audit = result.get("audit", {})
        if audit.get("response", {}).get("validation_passed") is True:
            passed += 1
    return f"{passed}/{len(results)} 성공"


def _avg_timing_summary(results: list[dict[str, Any]]) -> str:
    totals: list[float] = []
    llms: list[float] = []
    for result in results:
        audit = result.get("audit", {})
        metrics = audit.get("metrics", {})
        llm = metrics.get("llm", {})
        total_ms = metrics.get("total_duration_ms")
        llm_ms = llm.get("duration_ms")
        if total_ms is not None:
            totals.append(float(total_ms))
        if llm_ms is not None:
            llms.append(float(llm_ms))
    if not totals or not llms:
        return "-"
    return f"평균 CLI {sum(totals)/len(totals):.0f}ms, 평균 LLM {sum(llms)/len(llms):.0f}ms"


def _compact(text: str, limit: int = 180) -> str:
    single = " ".join(text.split())
    if len(single) <= limit:
        return single
    return single[: limit - 3] + "..."


def _model_alias(model: str) -> str:
    return model.removeprefix("gpt-5-") if model.startswith("gpt-5-") else model


if __name__ == "__main__":
    raise SystemExit(main())
