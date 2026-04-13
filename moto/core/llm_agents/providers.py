from __future__ import annotations
# 미래형 타입 힌트를 문자열 평가 없이 사용할 수 있게 한다.

import json
# HTTP 요청/응답 body를 JSON으로 직렬화/역직렬화할 때 사용한다.

import os
# API 키와 기본 모델명을 환경변수에서 읽기 위해 사용한다.

import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

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

    if os.getenv("MOTO_LLM_OPENAI_TRANSPORT", "opencode").lower() == "opencode":
        return _call_opencode(prompt, model=model, timeout=timeout)

    start = time.monotonic()
    _log_fallback_transport("api", "start", prompt)
    try:
        result = _call_openai_responses_api(prompt, model=model, timeout=timeout)
    except Exception:
        _log_fallback_transport("api", "error", prompt, start)
        raise
    _log_fallback_transport("api", "done", prompt, start)
    return result


def _call_openai_responses_api(
    prompt: str,
    *,
    model: Optional[str] = None,
    timeout: float = 20.0,
) -> str:
    # OpenAI Responses API를 직접 호출해서 텍스트 응답을 받아오는 함수다.

    api_key = os.getenv("OPENAI_API_KEY")
    # OpenAI API 키를 환경변수에서 읽는다.

    if not api_key:
        # API 키가 없으면 바로 예외를 발생시킨다.
        raise ValueError("OPENAI_API_KEY is not set")

    payload = {
        # OpenAI API에 보낼 JSON 요청 body를 만든다.
        "model": _api_model_name(
            model or os.getenv("MOTO_LLM_OPENAI_MODEL", "gpt-5.4")
        ),
        # 호출에 사용할 모델명을 정한다. 인자가 없으면 환경변수, 그것도 없으면 기본값을 쓴다.
        "instructions": _agent_instructions(),
        # OpenCode agent와 동일한 agent 지침을 직접 API 호출에도 적용한다.
        "input": [
            # Responses API의 공식 message 배열 형태로 입력을 보낸다.
            {
                "role": "user",
                # 이 메시지가 사용자 입력이라는 뜻이다.
                "content": _runtime_prompt(prompt),
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


def _call_opencode(
    prompt: str,
    *,
    model: Optional[str] = None,
    timeout: float,
) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    start = time.monotonic()
    _log_fallback_transport("opencode", "start", prompt)
    command = [
        os.getenv("MOTO_LLM_OPENCODE_BIN", "opencode"),
        "run",
        "--agent",
        os.getenv("MOTO_LLM_OPENCODE_AGENT", "moto-fallback"),
        "--model",
        model or os.getenv("MOTO_LLM_OPENCODE_MODEL", "openai/gpt-5.4"),
        "--variant",
        os.getenv("MOTO_LLM_OPENCODE_VARIANT", "fast"),
        "--format",
        "json",
        _runtime_prompt(prompt),
    ]

    completed = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )

    if completed.returncode != 0:
        _log_fallback_transport("opencode", "error", prompt, start)
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())

    parts: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") == "text":
            text = event.get("part", {}).get("text")
            if text:
                parts.append(text)

    result = "\n".join(parts).strip()
    if not result:
        _log_fallback_transport("opencode", "error", prompt, start)
        raise ValueError("OpenCode returned no text")

    _log_fallback_transport("opencode", "done", prompt, start)
    return result


def _runtime_prompt(prompt: str) -> str:
    return (
        "Runtime Moto LLM fallback request.\n"
        "Return only the HTTP response body for the AWS CLI caller.\n"
        "Use the compact request context below. "
        "Do not edit files, do not run tools, do not wrap the answer in Markdown.\n\n"
        f"{_compact_runtime_context(prompt)}"
    )


@lru_cache(maxsize=1)
def _agent_instructions() -> str:
    prompt_path = Path(__file__).with_name("agent.md")
    return prompt_path.read_text(encoding="utf-8")


def _compact_runtime_context(prompt: str) -> str:
    ordered_keys = (
        "service",
        "action",
        "source",
        "reason",
        "method",
        "url",
        "region",
        "read_only",
        "expected_format",
        "headers",
        "body",
    )
    parsed: dict[str, str] = {}

    for line in prompt.splitlines():
        stripped = line.strip()
        if not stripped or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        parsed[key.strip()] = _compact_prompt_value(key.strip(), value.strip())

    lines: list[str] = []
    for key in ordered_keys:
        value = parsed.get(key)
        if value:
            lines.append(f"{key}={value}")

    for key, value in parsed.items():
        if key not in ordered_keys:
            lines.append(f"{key}={value}")

    return "\n".join(lines)


def _compact_prompt_value(key: str, value: str) -> str:
    compacted = " ".join(value.split())

    if key == "headers":
        compacted = _compact_headers(compacted)
        return _truncate(compacted, 1200)

    if key == "body":
        return _truncate(compacted, 1800)

    if key == "reason":
        return _truncate(compacted, 240)

    return _truncate(compacted, 320)


def _compact_headers(value: str) -> str:
    hidden_tokens = (
        "authorization",
        "x-amz-security-token",
        "x-amz-date",
        "x-amzn-trace-id",
        "x-forwarded-for",
        "cookie",
    )
    lowered = value.lower()

    if not any(token in lowered for token in hidden_tokens):
        return value

    sanitized = value
    for token in hidden_tokens:
        sanitized = _replace_header_value(sanitized, token)
    return sanitized


def _replace_header_value(headers_text: str, header_name: str) -> str:
    marker = f"'{header_name}'"
    lowered = headers_text.lower()
    start = lowered.find(marker)
    if start == -1:
        return headers_text

    colon = headers_text.find(":", start)
    if colon == -1:
        return headers_text

    quote_start = headers_text.find("'", colon)
    if quote_start == -1:
        return headers_text

    quote_end = headers_text.find("'", quote_start + 1)
    if quote_end == -1:
        return headers_text

    return (
        headers_text[: quote_start + 1]
        + "<redacted>"
        + headers_text[quote_end:]
    )


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 15]}...[truncated]"


def _api_model_name(model: str) -> str:
    if model.startswith("openai/"):
        return model.split("/", 1)[1]
    return model


def _log_fallback_transport(
    transport: str,
    event: str,
    prompt: str,
    start: Optional[float] = None,
) -> None:
    source = None
    service = None
    action = None
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("source="):
            source = stripped.split("=", 1)[1]
        elif stripped.startswith("service="):
            service = stripped.split("=", 1)[1]
        elif stripped.startswith("action="):
            action = stripped.split("=", 1)[1]

    details = " ".join(
        part
        for part in (
            f"service={service}" if service else None,
            f"action={action}" if action else None,
            f"source={source}" if source else None,
        )
        if part
    )
    elapsed = ""
    if start is not None:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        elapsed = f" elapsed_ms={elapsed_ms}"

    print(
        f"[llm-fallback {transport} {event}] {details}{elapsed}",
        file=sys.stderr,
        flush=True,
    )


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
