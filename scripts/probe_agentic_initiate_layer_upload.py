#!/usr/bin/env python3
from __future__ import annotations

import os

from moto.core.llm_agents.agent import handle_aws_request


def main() -> int:
    os.environ["MOTO_LLM_ENV_FILE"] = ".env"
    os.environ["MOTO_LLM_RUNTIME_MODE"] = "agentic"
    os.environ["MOTO_LLM_AUDIT_FILE"] = "artifacts/agentic_probe_initiate.json"

    response_body = handle_aws_request(
        service="ecr",
        action="InitiateLayerUpload",
        url="https://api.ecr.ap-northeast-2.amazonaws.com/",
        headers={
            "X-Amz-Target": "AmazonEC2ContainerRegistry_V20150921.InitiateLayerUpload",
            "Content-Type": "application/x-amz-json-1.1",
        },
        body='{"repositoryName":"demo"}',
        reason="manual_agentic_probe",
        source="scripts.probe_agentic_initiate_layer_upload",
    )

    print(response_body)
    print("\nAudit file written: artifacts/agentic_probe_initiate.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
