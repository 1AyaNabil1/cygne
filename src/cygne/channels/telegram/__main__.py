"""Run the Cygne Telegram bot: ``python -m cygne.channels.telegram``."""

from __future__ import annotations

import logging

from cygne.channels.telegram import CygneBot
from cygne.config import get_settings
from cygne.llm import build_provider


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    provider = build_provider(settings.llm_provider, **settings.provider_kwargs())
    CygneBot(settings, provider).run()


if __name__ == "__main__":
    main()
