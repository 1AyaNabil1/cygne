"""Provider-agnostic LLM interface.

The agent depends only on :class:`LLMProvider`, never on a concrete vendor SDK.
Adding a new backend (Qwen, OpenAI, a local model, ...) means implementing this
interface once; no agent or tool code changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel


@dataclass(frozen=True)
class ModelSpec:
    """Identifies a model and the role it plays in the system.

    Attributes:
        name: Provider-specific model identifier (e.g. ``"qwen-max"``).
        role: Logical role, ``"main"`` for reasoning or ``"summary"`` for cheap
            summarization.
        temperature: Sampling temperature for this model.
    """

    name: str
    role: str = "main"
    temperature: float = 0.5


class LLMProvider(ABC):
    """A source of chat models.

    Implementations wrap a vendor SDK and expose it as LangChain
    :class:`~langchain_core.language_models.BaseChatModel` instances, so the agent
    can stay vendor-neutral.
    """

    #: Human-readable provider name, e.g. ``"qwen"``.
    name: str

    @abstractmethod
    def chat_model(self, spec: ModelSpec) -> BaseChatModel:
        """Return a chat model for the given spec.

        Args:
            spec: Which model to build and how it should behave.

        Returns:
            A configured LangChain chat model ready for tool-calling.
        """

    def main_model(self, name: str, temperature: float = 0.5) -> BaseChatModel:
        """Convenience: build a primary reasoning model."""
        return self.chat_model(ModelSpec(name=name, role="main", temperature=temperature))

    def summary_model(self, name: str, temperature: float = 0.2) -> BaseChatModel:
        """Convenience: build a cheaper model for summarization."""
        return self.chat_model(ModelSpec(name=name, role="summary", temperature=temperature))
