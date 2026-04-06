from __future__ import annotations
# 미래형 타입 힌트를 문자열 평가 없이 사용할 수 있게 한다.

import json
# HTTP 요청/응답 body를 JSON으로 직렬화/역직렬화할 때 사용한다.

import os
# API 키와 기본 모델명을 환경변수에서 읽기 위해 사용한다.

from typing import Any, Optional
# 함수 시그니처에 사용하는 타입 힌트를 가져온다.

from urllib.request import Request, urlopen
# 표준 라이브러리만으로 HTTP POST 요청을 보내기 위해 사용한다.


def call_gpt_api(
    prompt: str,
    *,
    model: Optional[str] = None,
    timeout: float = 20.0,
) -> str:
    # OpenAI Responses API를 호출해서 텍스트 응답을 받아오는 함수다.

    api_key = os.getenv("OPENAI_API_KEY")
    # OpenAI API 키를 환경변수에서 읽는다.

    if not api_key:
        # API 키가 없으면 바로 예외를 발생시킨다.
        raise ValueError("OPENAI_API_KEY is not set")

    payload = {
        # OpenAI API에 보낼 JSON 요청 body를 만든다.
        "model": model or os.getenv("MOTO_LLM_OPENAI_MODEL", "gpt-5-mini"),
        # 호출에 사용할 모델명을 정한다. 인자가 없으면 환경변수, 그것도 없으면 기본값을 쓴다.
        "input": [
            # Responses API의 공식 message 배열 형태로 입력을 보낸다.
            {
                "role": "user",
                # 이 메시지가 사용자 입력이라는 뜻이다.
                "content": prompt,
                # 실제 프롬프트 문자열을 담는다.
            }
        ],
    }

    response = _post_json(
        # 공통 POST 함수로 OpenAI Responses API를 호출한다.
        url="https://api.openai.com/v1/responses",
        # OpenAI Responses API 엔드포인트다.
        headers={
            # OpenAI 요청에 필요한 HTTP 헤더를 만든다.
            "Authorization": f"Bearer {api_key}",
            # Bearer 토큰 방식으로 API 키를 전달한다.
            "Content-Type": "application/json",
            # 요청 body가 JSON이라는 것을 명시한다.
        },
        payload=payload,
        # 위에서 만든 요청 body를 전달한다.
        timeout=timeout,
        # 네트워크 대기 시간을 초 단위로 전달한다.
    )

    parts: list[str] = []
    # 응답 안의 텍스트 조각들을 모을 리스트를 만든다.

    for item in response.get("output", []):
        # OpenAI 응답의 output 배열을 순회한다.
        for content in item.get("content", []):
            # 각 output 항목 안의 content 배열을 순회한다.
            if content.get("type") == "output_text":
                # 텍스트 출력 항목만 골라낸다.
                text = content.get("text")
                # 실제 생성된 텍스트를 읽는다.
                if text:
                    # 비어 있지 않은 텍스트만 추가한다.
                    parts.append(text)

    return "\n".join(parts).strip()
    # 여러 텍스트 조각을 하나의 문자열로 합쳐 최종 응답으로 돌려준다.


def call_claude_api(
    prompt: str,
    *,
    model: Optional[str] = None,
    timeout: float = 20.0,
) -> str:
    # Anthropic Messages API를 호출해서 텍스트 응답을 받아오는 함수다.

    api_key = os.getenv("ANTHROPIC_API_KEY")
    # Anthropic API 키를 환경변수에서 읽는다.

    if not api_key:
        # API 키가 없으면 바로 예외를 발생시킨다.
        raise ValueError("ANTHROPIC_API_KEY is not set")

    payload = {
        # Anthropic API에 보낼 JSON 요청 body를 만든다.
        "model": model
        or os.getenv("MOTO_LLM_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        # 사용할 Claude 모델명을 정한다. 인자가 우선이고, 없으면 환경변수, 그것도 없으면 기본값을 쓴다.
        "max_tokens": 2000,
        # Claude가 생성할 최대 토큰 수를 정한다.
        "messages": [
            # Anthropic Messages API의 공식 messages 배열을 구성한다.
            {
                "role": "user",
                # 사용자 메시지라는 뜻이다.
                "content": prompt,
                # 실제 프롬프트 문자열을 넣는다.
            }
        ],
    }

    response = _post_json(
        # 공통 POST 함수로 Anthropic Messages API를 호출한다.
        url="https://api.anthropic.com/v1/messages",
        # Anthropic Messages API 엔드포인트다.
        headers={
            # Anthropic 요청에 필요한 HTTP 헤더를 만든다.
            "x-api-key": api_key,
            # Anthropic 전용 API 키 헤더다.
            "anthropic-version": "2023-06-01",
            # 사용할 API 버전을 명시한다.
            "content-type": "application/json",
            # 요청 body가 JSON이라는 것을 명시한다.
        },
        payload=payload,
        # 위에서 만든 요청 body를 전달한다.
        timeout=timeout,
        # 네트워크 대기 시간을 초 단위로 전달한다.
    )

    parts: list[str] = []
    # 응답 안의 텍스트 조각들을 모을 리스트를 만든다.

    for item in response.get("content", []):
        # Anthropic 응답의 content 배열을 순회한다.
        if item.get("type") == "text":
            # 텍스트 타입 블록만 골라낸다.
            text = item.get("text")
            # 실제 생성된 텍스트를 읽는다.
            if text:
                # 비어 있지 않은 텍스트만 추가한다.
                parts.append(text)

    return "\n".join(parts).strip()
    # 여러 텍스트 조각을 하나의 문자열로 합쳐 최종 응답으로 돌려준다.


def _post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    # JSON POST 요청을 보내고 JSON 객체를 돌려주는 공통 헬퍼 함수다.

    request = Request(
        # urllib가 사용할 Request 객체를 만든다.
        url=url,
        # 요청 URL을 넣는다.
        headers=headers,
        # 요청 헤더를 넣는다.
        data=json.dumps(payload).encode("utf-8"),
        # payload를 JSON 문자열로 만든 뒤 바이트로 인코딩해 body에 넣는다.
        method="POST",
        # HTTP 메서드를 POST로 지정한다.
    )

    with urlopen(request, timeout=timeout) as response:
        # 지정한 timeout으로 실제 HTTP 요청을 보낸다.
        raw = response.read().decode("utf-8")
        # 응답 body 전체를 읽고 UTF-8 문자열로 디코딩한다.

    parsed = json.loads(raw)
    # 응답 문자열을 JSON으로 파싱한다.

    if not isinstance(parsed, dict):
        # 최상위 JSON이 객체가 아니면 예상한 형식이 아니라고 본다.
        raise ValueError("Expected JSON object response")

    return parsed
    # 파싱된 JSON 객체를 호출자에게 돌려준다.
