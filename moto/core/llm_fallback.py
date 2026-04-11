from __future__ import annotations
# 미래형 타입 힌트를 문자열 평가 없이 사용할 수 있게 한다.

import json
# fallback 확인용 JSON body를 만들 때 사용한다.

from html import escape

from moto.core.llm_agents import call_claude_api, call_gpt_api
# 실제 LLM API 호출 구현은 llm_agents 패키지에서 가져온다.


def build_llm_fallback_json(message: str = "llm_fallback!!") -> tuple[dict[str, str], str]:
    # fallback 표식을 JSON 응답 body와 헤더로 만들어 돌려준다.

    headers = {"Content-Type": "application/json"}
    # 응답 body가 JSON이라는 것을 명시한다.

    body = json.dumps({"message": message})
    # 사람이 보기 쉬운 단일 message 필드 JSON을 만든다.

    return headers, body
    # 호출부가 바로 HTTP 응답에 쓸 수 있도록 헤더와 body를 함께 반환한다.


def format_llm_fallback_response(
    service: str | None, action: str | None, body: str
) -> tuple[dict[str, str], str]:
    normalized_service = (service or "").lower()
    normalized_action = (action or "").lower()
    data = _json_body_or_empty(body)

    if normalized_service == "iam":
        if normalized_action == "create_service_specific_credential":
            credential = data.get("ServiceSpecificCredential", data)
            return _xml_headers(), _iam_create_service_specific_credential_xml(credential)
        if normalized_action == "get_context_keys_for_principal_policy":
            keys = data.get("ContextKeyNames", [])
            return _xml_headers(), _iam_get_context_keys_xml(keys)

    if normalized_service == "sts" and normalized_action == "decode_authorization_message":
        decoded = data.get("DecodedMessage", body)
        return _xml_headers(), _sts_decode_authorization_message_xml(decoded)

    return {"Content-Type": "application/json"}, body


def _json_body_or_empty(body: str) -> dict[str, object]:
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        return {}
    if isinstance(value, dict):
        return value
    return {}


def _xml_headers() -> dict[str, str]:
    return {"Content-Type": "text/xml"}


def _xml_text(value: object, default: str = "") -> str:
    if value is None:
        value = default
    return escape(str(value), quote=False)


def _iam_create_service_specific_credential_xml(credential: object) -> str:
    if not isinstance(credential, dict):
        credential = {}
    return f"""<CreateServiceSpecificCredentialResponse xmlns="https://iam.amazonaws.com/doc/2010-05-08/">
  <CreateServiceSpecificCredentialResult>
    <ServiceSpecificCredential>
      <CreateDate>{_xml_text(credential.get("CreateDate"), "2026-04-11T00:00:00Z")}</CreateDate>
      <ServiceName>{_xml_text(credential.get("ServiceName"), "codecommit.amazonaws.com")}</ServiceName>
      <ServicePassword>REDACTED_FAKE_SERVICE_PASSWORD</ServicePassword>
      <ServiceSpecificCredentialId>{_xml_text(credential.get("ServiceSpecificCredentialId"), "ACCAEXAMPLEFALLBACK123")}</ServiceSpecificCredentialId>
      <ServiceUserName>{_xml_text(credential.get("ServiceUserName"), "decoy-user")}</ServiceUserName>
      <Status>{_xml_text(credential.get("Status"), "Active")}</Status>
      <UserName>{_xml_text(credential.get("UserName"), "victim-admin")}</UserName>
    </ServiceSpecificCredential>
  </CreateServiceSpecificCredentialResult>
  <ResponseMetadata>
    <RequestId>00000000-0000-0000-0000-000000000000</RequestId>
  </ResponseMetadata>
</CreateServiceSpecificCredentialResponse>"""


def _iam_get_context_keys_xml(keys: object) -> str:
    if not isinstance(keys, list):
        keys = []
    members = "\n".join(
        f"      <member>{_xml_text(key)}</member>" for key in keys
    )
    return f"""<GetContextKeysForPrincipalPolicyResponse xmlns="https://iam.amazonaws.com/doc/2010-05-08/">
  <GetContextKeysForPrincipalPolicyResult>
    <ContextKeyNames>
{members}
    </ContextKeyNames>
  </GetContextKeysForPrincipalPolicyResult>
  <ResponseMetadata>
    <RequestId>00000000-0000-0000-0000-000000000000</RequestId>
  </ResponseMetadata>
</GetContextKeysForPrincipalPolicyResponse>"""


def _sts_decode_authorization_message_xml(decoded: object) -> str:
    return f"""<DecodeAuthorizationMessageResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">
  <DecodeAuthorizationMessageResult>
    <DecodedMessage>{_xml_text(decoded, "{}")}</DecodedMessage>
  </DecodeAuthorizationMessageResult>
  <ResponseMetadata>
    <RequestId>00000000-0000-0000-0000-000000000000</RequestId>
  </ResponseMetadata>
</DecodeAuthorizationMessageResponse>"""
