"""Prospect and lead-context models."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cygne.db.models.base import Base, TimestampMixin
from cygne.db.models.enums import QualificationStatus

# JSONB on PostgreSQL (production); plain JSON on SQLite (tests).
JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class Prospect(Base, TimestampMixin):
    """A person talking to the bot on a chat channel."""

    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), default="telegram", nullable=False)
    channel_chat_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))

    lead: Mapped[LeadContext] = relationship(
        back_populates="prospect", uselist=False, cascade="all, delete-orphan"
    )


class LeadContext(Base, TimestampMixin):
    """Accumulated business context and qualification for a prospect."""

    __tablename__ = "lead_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prospect_id: Mapped[int] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    industry: Mapped[str | None] = mapped_column(String(255))
    ad_budget: Mapped[str | None] = mapped_column(String(64))
    business_stage: Mapped[str | None] = mapped_column(String(64))
    timeline: Mapped[str | None] = mapped_column(String(64))

    # Flexible bag for everything else the extractor finds (challenges, goals, ...).
    extra: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qualification: Mapped[QualificationStatus] = mapped_column(
        SAEnum(QualificationStatus), default=QualificationStatus.UNQUALIFIED, nullable=False
    )

    prospect: Mapped[Prospect] = relationship(back_populates="lead")
