#!/usr/bin/env python3
from __future__ import annotations

import os

from moto.core.llm_agents.agent import handle_aws_request


def main() -> int:
    os.environ["MOTO_LLM_ENV_FILE"] = ".env"
    os.environ["MOTO_LLM_RUNTIME_MODE"] = "agentic"
    os.environ["MOTO_LLM_AUDIT_FILE"] = "artifacts/agentic_probe_validate_resource_policy.json"

    response_body = handle_aws_request(
        service="secretsmanager",
        action="ValidateResourcePolicy",
        url="https://secretsmanager.ap-northeast-2.amazonaws.com/",
        headers={
            "X-Amz-Target": "secretsmanager.ValidateResourcePolicy",
            "Content-Type": "application/x-amz-json-1.1",
        },
        body='{"SecretId":"prod/db/password","ResourcePolicy":"{\\"Version\\":\\"2012-10-17\\",\\"Statement\\":[{\\"Effect\\":\\"Allow\\",\\"Principal\\":\\"*\\",\\"Action\\":\\"secretsmanager:GetSecretValue\\",\\"Resource\\":\\"*\\"}]}"}',
        reason="manual_agentic_probe",
        source="scripts.probe_agentic_validate_resource_policy",
    )

    print(response_body)
    print("\nAudit file written: artifacts/agentic_probe_validate_resource_policy.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
