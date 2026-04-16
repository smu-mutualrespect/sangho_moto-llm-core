#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from moto.core.llm_agents.agent import handle_aws_request


def parse_header(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid header format: {item}. Use Key=Value")
        k, v = item.split("=", 1)
        headers[k.strip()] = v.strip()
    return headers


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one honeypot LLM-agent call and persist audit JSON"
    )
    parser.add_argument("--service", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--header", action="append", default=[])
    parser.add_argument(
        "--audit-file",
        default="artifacts/llm_agent_call_log.json",
        help="Path to JSON file where request/response/usage/timing is stored",
    )
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional .env file path to load before calling the provider",
    )
    parser.add_argument("--reason", default="manual_runtime_probe")
    parser.add_argument("--source", default="scripts.run_llm_agent_call")
    args = parser.parse_args()

    audit_path = Path(args.audit_file)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["MOTO_LLM_AUDIT_FILE"] = str(audit_path)
    if args.env_file:
        os.environ["MOTO_LLM_ENV_FILE"] = args.env_file

    headers = parse_header(args.header)
    response_body = handle_aws_request(
        service=args.service,
        action=args.action,
        url=args.url,
        headers=headers,
        body=args.body,
        reason=args.reason,
        source=args.source,
    )

    print(response_body)
    print(f"\nAudit file written: {audit_path}")

    # Print the last audit object for quick verification
    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    last = data[-1] if isinstance(data, list) and data else data
    print(json.dumps(last, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
