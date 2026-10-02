"""Smoke test: verify config, the LLM provider layer, and the data model load and work.

Run from the repo root with the project venv:

    .venv/bin/python -m scripts.smoke
"""

from __future__ import annotations

import asyncio

from langchain_core.messages import HumanMessage

from cygne.config import get_settings
from cygne.db.models import Base
from cygne.llm import build_provider


async def main() -> None:
    settings = get_settings()
    print(f"provider   : {settings.llm_provider}")
    print(f"main model : {settings.main_model}")

    # Data model registers cleanly.
    tables = ", ".join(sorted(Base.metadata.tables))
    print(f"tables     : {tables}")

    # LLM provider layer talks to the live backend.
    provider = build_provider(settings.llm_provider, **settings.provider_kwargs())
    model = provider.main_model(settings.main_model, temperature=0)
    reply = await model.ainvoke([HumanMessage(content="Reply with exactly: CYGNE LLM OK")])
    print(f"llm reply  : {reply.content}")


if __name__ == "__main__":
    asyncio.run(main())
