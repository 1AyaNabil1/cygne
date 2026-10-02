"""Conversation notes for long conversations.

Every ``threshold`` messages, the cheap model folds the latest messages into the running
notes it wrote last time, so the notes grow with the conversation while the prompt only
ever carries the notes plus the recent window. The notes are written for the agent, as
facts and an open next step, not as a message to the prospect.
"""

from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from cygne.db.helpers import recent_messages
from cygne.db.models import Conversation, MessageRole

logger = logging.getLogger(__name__)

NOTES_PROMPT = """Update the notes on a sales conversation between Cygne (the agency's \
assistant) and a prospect. Keep everything still true from the current notes, add what \
the new messages tell us, and correct anything they contradict.

Write at most five short lines, as plain facts:
Business: what they do
Wants: what they want from the agency and why
Budget and timing: if known
Concerns: objections or doubts they raised, if any
Next step: what was agreed or left open

Current notes:
{notes}

New messages:
{messages}

Updated notes:"""


async def update_notes(
    session: AsyncSession,
    model: BaseChatModel,
    conversation: Conversation,
    window: int,
) -> str | None:
    """The conversation's notes with its last ``window`` messages folded in."""
    messages = await recent_messages(session, conversation.id, limit=window)
    if len(messages) < 3:
        return None
    transcript = "\n".join(
        f"{'Prospect' if m.role == MessageRole.USER else 'Cygne'}: {m.content}" for m in messages
    )
    prompt = NOTES_PROMPT.format(notes=conversation.summary or "(none yet)", messages=transcript)
    try:
        response = await model.ainvoke(prompt)
    except Exception as error:  # noqa: BLE001 - notes must never break the chat
        logger.error("Updating conversation notes failed: %s", error)
        return None
    notes = str(response.content).strip()
    return notes or None


async def maybe_summarize(
    session: AsyncSession,
    model: BaseChatModel,
    conversation: Conversation,
    threshold: int = 50,
) -> None:
    """Every ``threshold`` messages, fold the newest ones into the notes."""
    count = conversation.message_count
    if count < threshold or count % threshold:
        return
    notes = await update_notes(session, model, conversation, window=threshold)
    if notes:
        conversation.summary = notes
