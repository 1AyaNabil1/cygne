"""Qwen Cloud provider.

Qwen Cloud (DashScope) exposes an OpenAI-compatible endpoint, so we reuse the
well-supported ``ChatOpenAI`` client and simply point it at Qwen's base URL. The
rest of the system only sees the :class:`~cygne.llm.base.LLMProvider` interface.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from cygne.llm.base import LLMProvider, ModelSpec


class QwenProvider(LLMProvider):
    """LLM provider backed by Qwen models on Qwen Cloud."""

    name = "qwen"

    def __init__(self, api_key: str, base_url: str) -> None:
        """Initialize the provider.

        Args:
            api_key: DashScope / Qwen Cloud API key.
            base_url: OpenAI-compatible base URL for Qwen Cloud.
        """
        self._api_key = api_key
        self._base_url = base_url

    def chat_model(self, spec: ModelSpec) -> BaseChatModel:
        return ChatOpenAI(
            model=spec.name,
            temperature=spec.temperature,
            api_key=self._api_key,
            base_url=self._base_url,
        )
