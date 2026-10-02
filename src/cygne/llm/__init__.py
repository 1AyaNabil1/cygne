"""Provider-agnostic LLM layer for Cygne."""

from cygne.llm.base import LLMProvider, ModelSpec
from cygne.llm.openai_compatible import OpenAICompatibleProvider
from cygne.llm.qwen import QwenProvider

__all__ = [
    "LLMProvider",
    "ModelSpec",
    "OpenAICompatibleProvider",
    "QwenProvider",
    "build_provider",
]


def build_provider(name: str, **kwargs: str) -> LLMProvider:
    """Construct an :class:`LLMProvider` by name.

    Args:
        name: Provider identifier: ``"qwen"`` or ``"openai-compatible"``.
        **kwargs: Provider-specific keyword arguments (e.g. ``api_key``, ``base_url``).

    Returns:
        A ready-to-use provider instance.

    Raises:
        ValueError: If the provider name is not recognized.
    """
    providers: dict[str, type[LLMProvider]] = {
        "qwen": QwenProvider,
        "openai-compatible": OpenAICompatibleProvider,
    }
    try:
        provider_cls = providers[name.lower()]
    except KeyError:
        raise ValueError(
            f"Unknown LLM provider {name!r}. Available: {', '.join(sorted(providers))}."
        ) from None
    return provider_cls(**kwargs)
