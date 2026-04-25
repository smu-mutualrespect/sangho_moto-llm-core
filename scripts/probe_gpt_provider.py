#!/usr/bin/env python3
from __future__ import annotations

import os

from moto.core.llm_agents.runtime.provider import (
    _load_dotenv_if_present,
    call_gpt_api_with_meta,
)


def main() -> int:
    os.environ["MOTO_LLM_ENV_FILE"] = ".env"
    _load_dotenv_if_present()

    text, meta = call_gpt_api_with_meta('Return only {"ok": true}.', timeout=10.0)
    print(meta)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
