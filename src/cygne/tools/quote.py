"""The ``draft_quote`` tool — the human-in-the-loop gate.

The agent drafts a proposal; it is persisted as a *pending* quote and handed to an
operator for approval. It is never sent to the prospect automatically. The operator
notification is injected as a callback so this tool stays decoupled from the channel.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from cygne.db.helpers import create_quote
from cygne.db.session import session_scope

# Called after a quote is persisted: (quote_id, prospect_id, body) -> awaitable.
QuoteNotifier = Callable[[int, int, str], Awaitable[None]]


class DraftQuoteInput(BaseModel):
    """An itemized proposal for the prospect."""

    body: str = Field(
        description=(
            "The full proposal text: scope, itemized services, and price. Written for "
            "the prospect, but pending human approval before it is sent."
        )
    )


async def _draft_quote(prospect_id: int, notifier: QuoteNotifier | None, body: str) -> str:
    async with session_scope() as session:
        quote = await create_quote(session, prospect_id, body)
        quote_id = quote.id
    if notifier is not None:
        await notifier(quote_id, prospect_id, body)
    return (
        "Quote drafted and sent to an operator for approval. Tell the prospect you are "
        "putting together a tailored proposal and will share it shortly. Do not quote a "
        "price directly yet."
    )


def build_draft_quote_tool(
    prospect_id: int, notifier: QuoteNotifier | None = None
) -> StructuredTool:
    """Build a ``draft_quote`` tool bound to a prospect and an operator notifier."""

    async def _runner(body: str) -> str:
        return await _draft_quote(prospect_id, notifier, body)

    return StructuredTool.from_function(
        coroutine=_runner,
        name="draft_quote",
        description=(
            "Draft a tailored, itemized proposal once you understand the prospect's needs "
            "and rough budget. The quote goes to a human operator for approval before it "
            "is sent — never promise a specific price in chat beforehand."
        ),
        args_schema=DraftQuoteInput,
    )
