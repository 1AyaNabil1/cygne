"""Data-access helpers.

All persistence goes through these functions rather than raw queries, so callers
(agent, tools, channel) never construct SQL and the storage layer stays swappable.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cygne.db.models import (
    Appointment,
    Conversation,
    ConversationStatus,
    LeadContext,
    Message,
    MessageRole,
    Prospect,
    Quote,
)
from cygne.leads.dedup import deduplicate


async def get_or_create_prospect(
    session: AsyncSession, channel: str, channel_chat_id: str
) -> Prospect:
    """Return the prospect for a channel chat id, creating it (with lead) if needed."""
    result = await session.execute(
        select(Prospect)
        .where(Prospect.channel == channel, Prospect.channel_chat_id == channel_chat_id)
        .options(selectinload(Prospect.lead))
    )
    prospect = result.scalar_one_or_none()
    if prospect is None:
        prospect = Prospect(channel=channel, channel_chat_id=channel_chat_id)
        prospect.lead = LeadContext()
        session.add(prospect)
        await session.flush()
    return prospect


async def get_or_create_active_conversation(
    session: AsyncSession, prospect_id: int
) -> Conversation:
    """Return the prospect's active conversation, creating one if none is open."""
    result = await session.execute(
        select(Conversation).where(
            Conversation.prospect_id == prospect_id,
            Conversation.status == ConversationStatus.ACTIVE,
        )
    )
    conversation = result.scalars().first()
    if conversation is None:
        conversation = Conversation(prospect_id=prospect_id)
        session.add(conversation)
        await session.flush()
    return conversation


async def add_message(
    session: AsyncSession, conversation: Conversation, role: MessageRole, content: str
) -> Message:
    """Append a message to a conversation and bump its message count."""
    message = Message(conversation_id=conversation.id, role=role, content=content)
    session.add(message)
    conversation.message_count += 1
    await session.flush()
    return message


async def recent_messages(
    session: AsyncSession, conversation_id: int, limit: int = 10
) -> list[Message]:
    """Return the most recent messages in a conversation, oldest first."""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def save_lead_context(
    session: AsyncSession, lead: LeadContext, fields: dict[str, object]
) -> LeadContext:
    """Update known lead fields; other keys land in the ``extra`` JSON bag, where lists
    are merged with what is already there rather than replaced."""
    columns = {"industry", "ad_budget", "business_stage", "timeline"}
    extra = dict(lead.extra)
    for key, value in fields.items():
        if value is None:
            continue
        if key in columns:
            setattr(lead, key, value)
        elif isinstance(value, list) and isinstance(extra.get(key), list):
            extra[key] = deduplicate([*extra[key], *value])
        else:
            extra[key] = value
    lead.extra = extra
    await session.flush()
    return lead


async def create_quote(session: AsyncSession, prospect_id: int, body: str) -> Quote:
    """Persist a drafted quote in the pending state."""
    quote = Quote(prospect_id=prospect_id, body=body)
    session.add(quote)
    await session.flush()
    return quote


async def create_appointment(
    session: AsyncSession, prospect_id: int, scheduled_for: datetime, notes: str | None = None
) -> Appointment:
    """Book an appointment for a prospect."""
    appointment = Appointment(prospect_id=prospect_id, scheduled_for=scheduled_for, notes=notes)
    session.add(appointment)
    await session.flush()
    return appointment


async def list_qualified_leads(session: AsyncSession, min_score: int = 1) -> list[LeadContext]:
    """Return leads at or above a score threshold, highest first (for the dashboard)."""
    result = await session.execute(
        select(LeadContext)
        .where(LeadContext.score >= min_score)
        .order_by(LeadContext.score.desc())
        .options(selectinload(LeadContext.prospect))
    )
    return list(result.scalars().all())
