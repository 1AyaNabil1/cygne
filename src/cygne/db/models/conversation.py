"""Conversation and message models."""

from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cygne.db.models.base import Base, TimestampMixin
from cygne.db.models.enums import ConversationStatus, MessageRole


class Conversation(Base, TimestampMixin):
    """A chat session with a prospect, with a rolling summary for long histories."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prospect_id: Mapped[int] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ConversationStatus] = mapped_column(
        SAEnum(ConversationStatus), default=ConversationStatus.ACTIVE, nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(Base, TimestampMixin):
    """A single message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
