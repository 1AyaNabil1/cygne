"""Enumerations used across the data model."""

from __future__ import annotations

import enum


class MessageRole(str, enum.Enum):
    """Who authored a message."""

    USER = "user"
    ASSISTANT = "assistant"


class ConversationStatus(str, enum.Enum):
    """Lifecycle of a conversation."""

    ACTIVE = "active"
    CLOSED = "closed"


class QualificationStatus(str, enum.Enum):
    """Lead qualification tier, derived from the lead score."""

    UNQUALIFIED = "unqualified"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AppointmentStatus(str, enum.Enum):
    """Lifecycle of a booked meeting."""

    BOOKED = "booked"
    CANCELLED = "cancelled"


class QuoteStatus(str, enum.Enum):
    """Lifecycle of a drafted quote through the human-in-the-loop gate."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
