"""Any provider with an OpenAI-compatible chat API.

OpenAI itself, Gemini (https://generativelanguage.googleapis.com/v1beta/openai/), Groq,
Together, OpenRouter, a local vLLM or Ollama server: they all accept the same requests,
so one provider with a configurable base URL covers them.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from cygne.llm.base import LLMProvider, ModelSpec


class OpenAICompatibleProvider(LLMProvider):
    """LLM provider for any OpenAI-compatible endpoint."""

    name = "openai-compatible"

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url

    def chat_model(self, spec: ModelSpec) -> BaseChatModel:
        return ChatOpenAI(
            model=spec.name,
            temperature=spec.temperature,
            api_key=self._api_key,
            base_url=self._base_url or None,
        )
