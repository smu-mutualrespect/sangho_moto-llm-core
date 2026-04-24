from __future__ import annotations

import json
import os
import subprocess
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
    transport = _resolve_openai_transport()
    if transport == "opencode":
        return _call_opencode_with_meta(prompt, model=model, timeout=timeout)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    payload = {
        "model": model or os.getenv("MOTO_LLM_OPENAI_MODEL", "gpt-5-mini"),
        "max_output_tokens": int(os.getenv("MOTO_LLM_OPENAI_MAX_OUTPUT_TOKENS", "1500")),
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


def call_claude_api(prompt: str, *, model: Optional[str] = None, timeout: float = 20.0) -> str:
    text, _ = call_claude_api_with_meta(prompt, model=model, timeout=timeout)
    return text


def call_claude_api_with_meta(prompt: str, *, model: Optional[str] = None, timeout: float = 20.0) -> tuple[str, dict[str, Any]]:
    _load_dotenv_if_present()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set")
    payload = {"model": model or os.getenv("MOTO_LLM_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"), "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]}
    started = time.perf_counter()
    response = _post_json(url="https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, payload=payload, timeout=timeout)
    parts = [item.get("text") for item in response.get("content", []) if item.get("type") == "text" and item.get("text")]
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return "\n".join(parts).strip(), {"provider": "anthropic", "model": payload["model"], "usage": response.get("usage"), "duration_ms": round(elapsed_ms, 3), "response_id": response.get("id")}


def _resolve_openai_transport() -> str:
    return "opencode" if os.getenv("MOTO_LLM_OPENAI_TRANSPORT", "").strip().lower() == "opencode" else "api"


def _call_opencode_with_meta(prompt: str, *, model: Optional[str] = None, timeout: float = 20.0) -> tuple[str, dict[str, Any]]:
    effective_timeout = max(timeout, float(os.getenv("MOTO_LLM_OPENCODE_TIMEOUT", "30")))
    repo_root = Path(__file__).resolve().parents[3]
    command = [os.getenv("MOTO_LLM_OPENCODE_BIN", "opencode"), "run", "--agent", os.getenv("MOTO_LLM_OPENCODE_AGENT", "moto-fallback"), "--model", model or os.getenv("MOTO_LLM_OPENCODE_MODEL", "openai/gpt-5.4"), "--variant", os.getenv("MOTO_LLM_OPENCODE_VARIANT", "fast"), "--format", "json", prompt]
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, timeout=effective_timeout, check=False, env=os.environ.copy())
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "opencode failed")
    parts: list[str] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            text = event.get("part", {}).get("text")
            if text:
                parts.append(text)
    output_text = "\n".join(parts).strip()
    if not output_text:
        raise ValueError("OpenCode returned no text")
    return output_text, {"provider": "opencode", "model": command[5], "duration_ms": round(elapsed_ms, 3), "stderr": completed.stderr.strip(), "returncode": completed.returncode}


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
