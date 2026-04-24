from __future__ import annotations

import json

from moto.core.llm_agents.agent import _stabilize_decision, handle_aws_request
from moto.core.llm_agents.runtime import DEFAULT_DECISION, DecisionOutput, call_gpt_api_with_meta, parse_decision_output
from moto.core.llm_agents.tools.planning_tools import build_response_plan_tool
from moto.core.llm_agents.tools.render_tools import adapt_response_plan_tool, render_protocol_response_tool
from moto.core.llm_agents.tools.request_tools import normalize_request_tool
from moto.core.llm_agents.tools.validation_tools import build_comparison_points_tool, validate_rendered_response_tool


def test_normalizer_canonicalizes_prefixed_action() -> None:
    req = normalize_request_tool(
        service="ssm",
        action="ssm:DescribeInstanceInformation",
        url="https://ssm.ap-northeast-2.amazonaws.com/",
        headers={},
        body="",
    )
    assert req.service == "ssm"
    assert req.operation == "DescribeInstanceInformation"
    assert req.probe_style == "enumeration"
    assert req.body_format == "text"


def test_normalizer_extracts_json_request_params_and_identifiers() -> None:
    req = normalize_request_tool(
        service=None,
        action=None,
        url="https://api.ecr.ap-northeast-2.amazonaws.com/",
        headers={"X-Amz-Target": "AmazonEC2ContainerRegistry_V20150921.CompleteLayerUpload"},
        body='{"repositoryName":"demo","layerDigest":"sha256:abc","uploadId":"test"}',
    )
    assert req.service == "ecr"
    assert req.operation == "CompleteLayerUpload"
    assert req.body_format == "json"
    assert req.request_params["repositoryName"] == "demo"
    assert req.target_identifiers["repositoryName"] == "demo"
    assert req.target_identifiers["layerDigest"] == "sha256:abc"


def test_parse_decision_output_falls_back_on_invalid_text() -> None:
    decision = parse_decision_output("not-a-json")
    assert decision == DEFAULT_DECISION


def test_handle_aws_request_renders_ec2_xml_from_decision(monkeypatch) -> None:
    decision_json = {
        "intent_phase": "recon",
        "response_posture": "rich",
        "error_mode": "none",
        "decoy_bundle_id": "ec2_primary",
        "risk_delta": 0.2,
        "reason_tags": ["enum_pattern", "permission_test"],
    }

    monkeypatch.setattr(
        "moto.core.llm_agents.agent.call_gpt_api_with_meta",
        lambda _: (json.dumps(decision_json), {"provider": "openai", "duration_ms": 1.0}),
    )

    response_body = handle_aws_request(
        service="ec2",
        action="DescribeInstances",
        url="https://ec2.ap-northeast-2.amazonaws.com/",
        headers={"X-Forwarded-For": "1.2.3.4"},
        body="Action=DescribeInstances",
        reason="test",
        source="unit_test",
    )

    assert "<DescribeInstancesResponse" in response_body
    assert "<instanceId>i-" in response_body


def test_handle_aws_request_replans_after_validation_failure(monkeypatch) -> None:
    calls: list[str] = []
    responses = iter(
        [
            json.dumps(
                {
                    "intent_phase": "recon",
                    "response_posture": "normal",
                    "error_mode": "none",
                    "decoy_bundle_id": "first_pass",
                    "risk_delta": 0.1,
                    "reason_tags": ["enum_pattern"],
                    "response_plan": {
                        "mode": "success",
                        "posture": "normal",
                        "field_hints": {
                            "InstanceInformationList": [
                                {
                                    "InstanceId": "not-an-instance-id",
                                    "PlatformType": "TotallyLinux",
                                }
                            ]
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "intent_phase": "recon",
                    "response_posture": "sparse",
                    "error_mode": "none",
                    "decoy_bundle_id": "second_pass",
                    "risk_delta": 0.1,
                    "reason_tags": ["enum_pattern"],
                }
            ),
        ]
    )

    def fake_call(prompt: str) -> tuple[str, dict[str, object]]:
        calls.append(prompt)
        return next(responses), {"provider": "openai", "duration_ms": 1.0}

    monkeypatch.setattr("moto.core.llm_agents.agent.call_gpt_api_with_meta", fake_call)
    monkeypatch.setenv("MOTO_LLM_AGENT_MAX_ATTEMPTS", "2")

    response_body = handle_aws_request(
        service="ssm",
        action="DescribeInstanceInformation",
        url="https://ssm.ap-northeast-2.amazonaws.com/",
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        body="Action=DescribeInstanceInformation&Version=2014-11-06",
        reason="test",
        source="unit_test",
    )

    parsed = json.loads(response_body)
    assert parsed["InstanceInformationList"][0]["InstanceId"].startswith("i-")
    assert len(calls) == 2
    assert "LATEST_OBSERVATION" in calls[1]
    assert "tool=validate_rendered_response status=failed" in calls[1]


def test_validator_blocks_public_url() -> None:
    canonical = normalize_request_tool(
        service="ssm",
        action="DescribeInstanceInformation",
        url="https://ssm.ap-northeast-2.amazonaws.com/",
        headers={},
        body="",
    )
    valid, reason = validate_rendered_response_tool(
        canonical,
        '{"message": "visit https://example.com"}',
        {"consistency_locks": {"account_id": "123456789012"}},
    )
    assert valid is False
    assert "Safety pattern denied" in reason


def test_validator_allows_aws_xml_namespace() -> None:
    canonical = normalize_request_tool(
        service="ec2",
        action="DescribeInstances",
        url="https://ec2.ap-northeast-2.amazonaws.com/",
        headers={},
        body="",
    )
    body = (
        '<DescribeInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2016-11-15/">'
        "<reservationSet><item><instancesSet><item><instanceId>i-12345678</instanceId>"
        "</item></instancesSet></item></reservationSet></DescribeInstancesResponse>"
    )
    valid, reason = validate_rendered_response_tool(
        canonical,
        body,
        {"consistency_locks": {"account_id": "123456789012"}},
    )
    assert valid is True
    assert reason == "ok"


def test_comparison_points_capture_xml_parseability() -> None:
    canonical = normalize_request_tool(
        service="ec2",
        action="DescribeInstances",
        url="https://ec2.ap-northeast-2.amazonaws.com/",
        headers={},
        body="",
    )
    body = (
        '<DescribeInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2016-11-15/">'
        "<reservationSet><item><instancesSet><item><instanceId>i-12345678</instanceId>"
        "</item></instancesSet></item></reservationSet></DescribeInstancesResponse>"
    )
    points = build_comparison_points_tool(canonical, body, True, "ok")
    assert points["protocol_family_expected"] == "xml"
    assert points["response_format_detected"] == "xml"
    assert points["format_match"] is True
    assert points["response_parseable"] is True
    assert points["xml_namespace_present"] is True


def test_stabilize_decision_forces_success_for_benchmark_operations() -> None:
    canonical = normalize_request_tool(
        service="ssm",
        action="DescribeInstanceInformation",
        url="https://ssm.ap-northeast-2.amazonaws.com/",
        headers={},
        body="",
    )
    decision = DecisionOutput(
        intent_phase="recon",
        response_posture="normal",
        error_mode="access_denied",
        decoy_bundle_id="ssm_probe",
        risk_delta=0.05,
        reason_tags=["enum_pattern"],
    )
    stabilized = _stabilize_decision(canonical, decision)
    assert stabilized.error_mode == "none"
    assert stabilized.response_posture == "normal"


def test_shape_adapter_and_protocol_renderer_for_iam_query() -> None:
    canonical = normalize_request_tool(
        service="iam",
        action="GetContextKeysForPrincipalPolicy",
        url="https://iam.amazonaws.com/",
        headers={},
        body="Action=GetContextKeysForPrincipalPolicy",
    )
    world_state = {"consistency_locks": {"account_id": "123456789012"}, "exposed_assets": []}
    plan = build_response_plan_tool(canonical, DEFAULT_DECISION, world_state, "")
    payload, meta = adapt_response_plan_tool(canonical, plan, world_state)
    body, render_meta = render_protocol_response_tool(canonical, payload, meta)

    assert "GetContextKeysForPrincipalPolicyResponse" in body
    assert "<member>aws:RequestedRegion</member>" in body
    assert render_meta["headers"]["Content-Type"] == "text/xml"


def test_shape_adapter_and_protocol_renderer_for_ecr_json() -> None:
    canonical = normalize_request_tool(
        service="ecr",
        action="InitiateLayerUpload",
        url="https://api.ecr.us-east-1.amazonaws.com/",
        headers={},
        body="{}",
    )
    world_state = {"consistency_locks": {"account_id": "123456789012"}, "exposed_assets": []}
    plan = build_response_plan_tool(canonical, DEFAULT_DECISION, world_state, "")
    payload, meta = adapt_response_plan_tool(canonical, plan, world_state)
    body, render_meta = render_protocol_response_tool(canonical, payload, meta)
    parsed = json.loads(body)

    assert parsed["uploadId"].startswith("upload-")
    assert parsed["partSize"] > 0
    assert render_meta["headers"]["Content-Type"] == "application/x-amz-json-1.1"


def test_shape_adapter_echoes_request_identifiers_when_available() -> None:
    canonical = normalize_request_tool(
        service=None,
        action=None,
        url="https://api.ecr.us-east-1.amazonaws.com/",
        headers={"X-Amz-Target": "AmazonEC2ContainerRegistry_V20150921.CompleteLayerUpload"},
        body='{"repositoryName":"demo","uploadId":"test","layerDigest":"sha256:abc"}',
    )
    world_state = {"consistency_locks": {"account_id": "123456789012"}, "exposed_assets": []}
    plan = build_response_plan_tool(canonical, DEFAULT_DECISION, world_state, "")
    payload, _ = adapt_response_plan_tool(canonical, plan, world_state)

    assert payload["repositoryName"] == "demo"
    assert payload["uploadId"] == "test"
    assert payload["layerDigest"] == "sha256:abc"


def test_call_gpt_api_uses_direct_openai_by_default(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("MOTO_LLM_OPENAI_TRANSPORT", raising=False)

    captured: dict[str, object] = {}

    def fake_post_json(
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: float,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {
            "id": "resp_test",
            "usage": {"total_tokens": 12},
            "output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}],
        }

    monkeypatch.setattr("moto.core.llm_agents.runtime.provider._post_json", fake_post_json)

    text, meta = call_gpt_api_with_meta("test-prompt", timeout=7.5)

    assert text == '{"ok":true}'
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["timeout"] == 7.5
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer test-key"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["input"][0]["content"] == "test-prompt"
    assert meta["provider"] == "openai"


def test_call_gpt_api_uses_direct_openai_for_invalid_transport(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MOTO_LLM_OPENAI_TRANSPORT", "something-else")

    monkeypatch.setattr(
        "moto.core.llm_agents.runtime.provider._post_json",
        lambda **_: {
            "id": "resp_test",
            "usage": {"total_tokens": 10},
            "output": [{"content": [{"type": "output_text", "text": '{"route":"api"}'}]}],
        },
    )

    text, meta = call_gpt_api_with_meta("test-prompt")

    assert text == '{"route":"api"}'
    assert meta["provider"] == "openai"


def test_call_gpt_api_uses_opencode_only_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("MOTO_LLM_OPENAI_TRANSPORT", "opencode")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    monkeypatch.setattr(
        "moto.core.llm_agents.runtime.provider._call_opencode_with_meta",
        lambda prompt, model=None, timeout=20.0: (
            '{"route":"opencode"}',
            {"provider": "opencode", "duration_ms": 1.0, "prompt": prompt},
        ),
    )

    text, meta = call_gpt_api_with_meta("test-prompt")

    assert text == '{"route":"opencode"}'
    assert meta["provider"] == "opencode"
