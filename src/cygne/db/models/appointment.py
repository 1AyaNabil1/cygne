"""Quote and appointment models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from cygne.db.models.base import Base, TimestampMixin
from cygne.db.models.enums import AppointmentStatus, QuoteStatus


class Quote(Base, TimestampMixin):
    """A drafted proposal that must pass the human-in-the-loop gate before sending."""

    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prospect_id: Mapped[int] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[QuoteStatus] = mapped_column(
        SAEnum(QuoteStatus), default=QuoteStatus.PENDING, nullable=False
    )


class Appointment(Base, TimestampMixin):
    """A meeting booked with a prospect."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prospect_id: Mapped[int] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus), default=AppointmentStatus.BOOKED, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
