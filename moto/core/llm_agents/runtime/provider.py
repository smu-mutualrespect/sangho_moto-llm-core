from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen

_DOTENV_LOADED = False


def call_gpt_api(prompt: str, *, model: Optional[str] = None, timeout: float = 20.0) -> str:
    text, _ = call_gpt_api_with_meta(prompt, model=model, timeout=timeout)
    return text


def call_gpt_api_with_meta(prompt: str, *, model: Optional[str] = None, timeout: float = 20.0) -> tuple[str, dict[str, Any]]:
    _load_dotenv_if_present()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    payload = {
        "model": model or os.getenv("MOTO_LLM_OPENAI_MODEL", "gpt-5-mini"),
        "max_output_tokens": int(os.getenv("MOTO_LLM_OPENAI_MAX_OUTPUT_TOKENS", "80")),
        "reasoning": {"effort": os.getenv("MOTO_LLM_OPENAI_REASONING_EFFORT", "minimal")},
        "input": [{"role": "user", "content": prompt}],
    }
    started = time.perf_counter()
    response = _post_json(url="https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, payload=payload, timeout=timeout)
    parts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text = content.get("text")
                if text:
                    parts.append(text)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return "\n".join(parts).strip(), {"provider": "openai", "model": payload["model"], "usage": response.get("usage"), "duration_ms": round(elapsed_ms, 3), "response_id": response.get("id")}


def _post_json(*, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(url=url, headers=headers, data=json.dumps(payload).encode("utf-8"), method="POST")
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object response")
    return parsed


def _load_dotenv_if_present() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    env_file = os.getenv("MOTO_LLM_ENV_FILE")
    if env_file:
        _load_env_file(Path(env_file))
        _DOTENV_LOADED = True
        return
    cwd = Path.cwd()
    for candidate_dir in [cwd, *cwd.parents]:
        candidate = candidate_dir / ".env"
        if candidate.exists():
            _load_env_file(candidate)
            _DOTENV_LOADED = True
            return
    _DOTENV_LOADED = True


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))
