"""Tests for the Telegram channel's operator checks, with Telegram stubbed out."""

from __future__ import annotations

from types import SimpleNamespace

from cygne.channels.telegram.bot import CygneBot
from cygne.db import session_scope
from cygne.db.helpers import create_quote
from cygne.db.models import Quote, QuoteStatus

OPERATOR = "999"


class StubBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **_):
        self.sent.append((str(chat_id), text))


class StubQuery:
    def __init__(self, chat_id, data):
        self.message = SimpleNamespace(chat=SimpleNamespace(id=chat_id))
        self.from_user = SimpleNamespace(id=chat_id)
        self.data = data
        self.answers = []
        self.edits = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append(text)

    async def edit_message_text(self, text):
        self.edits.append(text)


class StubOrchestrator:
    def __init__(self):
        self.handled = []

    async def handle(self, channel, chat_id, text):
        self.handled.append((chat_id, text))
        return "reply"


def make_bot():
    bot = CygneBot.__new__(CygneBot)  # skip building a real Telegram application
    bot._operator_chat = OPERATOR
    bot._app = SimpleNamespace(bot=StubBot())
    bot._orchestrator = StubOrchestrator()
    return bot


async def _pending_quote(prospect_id: int) -> int:
    async with session_scope() as session:
        return (await create_quote(session, prospect_id, "SEO + ads, $2,000/month")).id


async def _status(quote_id: int) -> QuoteStatus:
    async with session_scope() as session:
        return (await session.get(Quote, quote_id)).status


async def test_a_quote_decision_from_outside_the_operator_chat_is_ignored(prospect_id) -> None:
    bot, quote_id = make_bot(), await _pending_quote(prospect_id)
    query = StubQuery(chat_id=12345, data=f"q:approve:{quote_id}")
    await bot._on_quote_decision(SimpleNamespace(callback_query=query), None)
    assert await _status(quote_id) == QuoteStatus.PENDING
    assert bot._app.bot.sent == []
    assert "Only the operator chat" in query.answers[0]


async def test_the_operator_approves_and_the_prospect_gets_the_quote(prospect_id) -> None:
    bot, quote_id = make_bot(), await _pending_quote(prospect_id)
    query = StubQuery(chat_id=int(OPERATOR), data=f"q:approve:{quote_id}")
    await bot._on_quote_decision(SimpleNamespace(callback_query=query), None)
    assert await _status(quote_id) == QuoteStatus.SENT
    assert bot._app.bot.sent == [
        ("test-chat-1", "Here's the proposal we put together for you:\n\nSEO + ads, $2,000/month")
    ]


async def test_malformed_callback_data_is_ignored(prospect_id) -> None:
    bot = make_bot()
    for data in ("q:approve", "q:approve:abc", "q:delete:1"):
        query = StubQuery(chat_id=int(OPERATOR), data=data)
        await bot._on_quote_decision(SimpleNamespace(callback_query=query), None)
        assert query.edits == []


async def test_messages_in_the_operator_chat_are_not_a_prospect_conversation() -> None:
    bot = make_bot()
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=int(OPERATOR)), message=None)
    await bot._on_message(update, None)
    assert bot._orchestrator.handled == []
