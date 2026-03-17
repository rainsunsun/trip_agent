"""LLM service (LangChain ChatOpenAI)."""

import os
from typing import Optional

from langchain_openai import ChatOpenAI

from ..config import get_settings

_llm_instance: Optional[ChatOpenAI] = None


def get_llm() -> ChatOpenAI:
    global _llm_instance

    if _llm_instance is None:
        settings = get_settings()

        api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key or None
        base_url = os.getenv("OPENAI_BASE_URL") or settings.openai_base_url or None
        model = os.getenv("OPENAI_MODEL") or settings.openai_model

        kwargs = {"model": model}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url

        _llm_instance = ChatOpenAI(**kwargs)

        print("[llm] initialized")
        print(f"[llm] model: {model}")
        if base_url:
            print(f"[llm] base_url: {base_url}")

    return _llm_instance


def reset_llm():
    global _llm_instance
    _llm_instance = None
