from __future__ import annotations

import json

from moto.core.llm_agents.agent import _stabilize_decision, handle_aws_request
from moto.core.llm_agents.assessment import build_comparison_points
from moto.core.llm_agents.decision import DEFAULT_DECISION, DecisionOutput, parse_decision_output
from moto.core.llm_agents.normalizer import normalize_aws_request
from moto.core.llm_agents.protocol_renderer import render_protocol_response
from moto.core.llm_agents.response_plan import build_response_plan
from moto.core.llm_agents.shape_adapter import adapt_response_plan
from moto.core.llm_agents.validator import validate_rendered_response


def test_normalizer_canonicalizes_prefixed_action() -> None:
    req = normalize_aws_request(
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
    req = normalize_aws_request(
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


def test_validator_blocks_public_url() -> None:
    canonical = normalize_aws_request(
        service="ssm",
        action="DescribeInstanceInformation",
        url="https://ssm.ap-northeast-2.amazonaws.com/",
        headers={},
        body="",
    )
    valid, reason = validate_rendered_response(
        canonical,
        '{"message": "visit https://example.com"}',
        {"consistency_locks": {"account_id": "123456789012"}},
    )
    assert valid is False
    assert "Safety pattern denied" in reason


def test_validator_allows_aws_xml_namespace() -> None:
    canonical = normalize_aws_request(
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
    valid, reason = validate_rendered_response(
        canonical,
        body,
        {"consistency_locks": {"account_id": "123456789012"}},
    )
    assert valid is True
    assert reason == "ok"


def test_comparison_points_capture_xml_parseability() -> None:
    canonical = normalize_aws_request(
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
    points = build_comparison_points(canonical, body, True, "ok")
    assert points["protocol_family_expected"] == "xml"
    assert points["response_format_detected"] == "xml"
    assert points["format_match"] is True
    assert points["response_parseable"] is True
    assert points["xml_namespace_present"] is True


def test_stabilize_decision_forces_success_for_benchmark_operations() -> None:
    canonical = normalize_aws_request(
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
    canonical = normalize_aws_request(
        service="iam",
        action="GetContextKeysForPrincipalPolicy",
        url="https://iam.amazonaws.com/",
        headers={},
        body="Action=GetContextKeysForPrincipalPolicy",
    )
    world_state = {"consistency_locks": {"account_id": "123456789012"}, "exposed_assets": []}
    plan = build_response_plan(canonical, DEFAULT_DECISION, world_state, "")
    payload, meta = adapt_response_plan(canonical, plan, world_state)
    body, render_meta = render_protocol_response(canonical, payload, meta)

    assert "GetContextKeysForPrincipalPolicyResponse" in body
    assert "<member>aws:RequestedRegion</member>" in body
    assert render_meta["headers"]["Content-Type"] == "text/xml"


def test_shape_adapter_and_protocol_renderer_for_ecr_json() -> None:
    canonical = normalize_aws_request(
        service="ecr",
        action="InitiateLayerUpload",
        url="https://api.ecr.us-east-1.amazonaws.com/",
        headers={},
        body="{}",
    )
    world_state = {"consistency_locks": {"account_id": "123456789012"}, "exposed_assets": []}
    plan = build_response_plan(canonical, DEFAULT_DECISION, world_state, "")
    payload, meta = adapt_response_plan(canonical, plan, world_state)
    body, render_meta = render_protocol_response(canonical, payload, meta)
    parsed = json.loads(body)

    assert parsed["uploadId"].startswith("upload-")
    assert parsed["partSize"] > 0
    assert render_meta["headers"]["Content-Type"] == "application/x-amz-json-1.1"


def test_shape_adapter_echoes_request_identifiers_when_available() -> None:
    canonical = normalize_aws_request(
        service=None,
        action=None,
        url="https://api.ecr.us-east-1.amazonaws.com/",
        headers={"X-Amz-Target": "AmazonEC2ContainerRegistry_V20150921.CompleteLayerUpload"},
        body='{"repositoryName":"demo","uploadId":"test","layerDigest":"sha256:abc"}',
    )
    world_state = {"consistency_locks": {"account_id": "123456789012"}, "exposed_assets": []}
    plan = build_response_plan(canonical, DEFAULT_DECISION, world_state, "")
    payload, _ = adapt_response_plan(canonical, plan, world_state)

    assert payload["repositoryName"] == "demo"
    assert payload["uploadId"] == "test"
    assert payload["layerDigest"] == "sha256:abc"
