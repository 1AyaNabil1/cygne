"""Build an iCalendar (.ics) invitation payload.

Hand-rolled to avoid an extra dependency; produces a single VEVENT with METHOD:REQUEST
so mail clients render it as a real meeting invitation.
"""

from __future__ import annotations

from datetime import UTC, datetime


def _stamp(dt: datetime) -> str:
    """Format a datetime as a UTC iCalendar timestamp (YYYYMMDDTHHMMSSZ)."""
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def build_ics(
    *,
    uid: str,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    organizer_email: str,
    attendee_email: str,
    now: datetime,
) -> str:
    """Return an .ics document for a single meeting invitation."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Cygne//Lead Agent//EN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_stamp(now)}",
        f"DTSTART:{_stamp(start)}",
        f"DTEND:{_stamp(end)}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        f"ORGANIZER:mailto:{organizer_email}",
        f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{attendee_email}",
        "STATUS:CONFIRMED",
        "SEQUENCE:0",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"
