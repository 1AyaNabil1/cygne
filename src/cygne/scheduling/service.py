"""Scheduling service: availability and booking, with Google Calendar + email.

When Google Calendar is configured, availability reflects the real calendar and a
booking creates a calendar event. When email is configured, a branded invitation with
an .ics attachment is sent to the prospect. Either integration degrades gracefully: a
booking is always recorded in the database regardless.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, time, timedelta

from sqlalchemy import select

from cygne.calendar.google_calendar import GoogleCalendarClient
from cygne.config import Settings
from cygne.db.helpers import create_appointment
from cygne.db.models import Appointment, AppointmentStatus, Prospect
from cygne.db.session import session_scope
from cygne.mailer.ics import build_ics
from cygne.mailer.sender import send_invitation
from cygne.mailer.templates import google_calendar_link, invitation_html, invitation_subject

logger = logging.getLogger(__name__)

SLOT_HOURS = (10, 13, 16)
DAYS_AHEAD = 7
MEETING_MINUTES = 30
SLOT_LABEL_FMT = "%A, %B %d at %H:%M"


def slot_label(dt: datetime) -> str:
    """Canonical human label for a slot, e.g. 'Tuesday, June 23 at 16:00'."""
    return dt.strftime(SLOT_LABEL_FMT)


class SchedulingService:
    """Produces availability and books meetings across calendar, email and database."""

    def __init__(self, settings: Settings, calendar: GoogleCalendarClient | None) -> None:
        self._settings = settings
        self._calendar = calendar
        self._tz = settings.tzinfo

    def _candidate_slots(self, now: datetime) -> list[datetime]:
        tz = self._tz
        slots: list[datetime] = []
        for day_offset in range(1, DAYS_AHEAD + 1):
            day = (now + timedelta(days=day_offset)).date()
            if day.weekday() >= 5:
                continue
            for hour in SLOT_HOURS:
                slots.append(datetime.combine(day, time(hour=hour), tzinfo=tz))
        return slots

    async def available_slots(self) -> list[datetime]:
        """Return up to six open upcoming slots, honoring the real calendar if present."""
        now = datetime.now(self._tz)
        candidates = self._candidate_slots(now)
        if self._calendar is not None:
            busy = await self._calendar.busy_intervals(now, now + timedelta(days=DAYS_AHEAD))
            free = [slot for slot in candidates if not any(b.start <= slot < b.end for b in busy)]
        else:
            free = await self._filter_against_db(candidates)
        return free[:6]

    async def _filter_against_db(self, candidates: list[datetime]) -> list[datetime]:
        async with session_scope() as session:
            rows = await session.execute(
                select(Appointment.scheduled_for).where(
                    Appointment.status == AppointmentStatus.BOOKED
                )
            )
            # Compare on naive wall-clock time: SQLite drops tz info on round-trip.
            taken = {r[0].replace(tzinfo=None) for r in rows.all()}
        return [s for s in candidates if s.replace(tzinfo=None) not in taken]

    async def labeled_slots(self) -> list[tuple[str, datetime]]:
        """Return open slots paired with their canonical labels."""
        return [(slot_label(s), s) for s in await self.available_slots()]

    async def book_by_label(self, prospect_id: int, label: str) -> str:
        """Book the slot matching a label shown by check_availability.

        The agent never computes dates; it echoes a label, and we resolve it to the
        real datetime. An unrecognized label returns the current list to re-offer.
        """
        wanted = " ".join(label.lower().split())
        for slot in await self.available_slots():
            if " ".join(slot_label(slot).lower().split()) == wanted:
                return await self.book(prospect_id, slot)
        options = "; ".join(slot_label(s) for s in await self.available_slots())
        return f"That slot isn't on the list. Offer the prospect one of: {options}."

    async def book(self, prospect_id: int, when: datetime) -> str:
        """Book a meeting: calendar event (if enabled), branded email (if enabled), DB record."""
        if when.tzinfo is None:
            when = when.replace(tzinfo=self._tz)
        if when <= datetime.now(self._tz):
            return "That time is in the past. Please pick an upcoming slot."

        async with session_scope() as session:
            prospect = await session.get(Prospect, prospect_id)
            if prospect is None:
                return "Could not find the prospect record."
            if not prospect.email:
                return "I need your email before booking. Could you share it?"
            email, name = prospect.email, prospect.name

        # Backstop: only ever book a real, currently-open slot.
        available = await self.available_slots()
        if not any(slot.replace(tzinfo=None) == when.replace(tzinfo=None) for slot in available):
            options = ", ".join(s.strftime("%a %d %b %H:%M") for s in available[:4])
            return f"That slot isn't available. Please offer the prospect one of: {options}."

        end = when + timedelta(minutes=MEETING_MINUTES)
        summary = f"Strategy call with {self._settings.agency_name}"
        description = "Marketing strategy call booked via Cygne."

        if self._calendar is not None:
            try:
                await self._calendar.create_event(summary, description, when, end, email)
            except Exception as error:  # noqa: BLE001
                logger.error("Calendar event creation failed: %s", error)

        emailed = await self._maybe_email(email, name, when)

        async with session_scope() as session:
            await create_appointment(session, prospect_id, when, notes=summary)

        slot_str = when.strftime("%A %Y-%m-%d at %H:%M")
        if emailed:
            return f"Booked your strategy call for {slot_str}. I've emailed you a calendar invite."
        return f"Booked your strategy call for {slot_str}."

    async def _maybe_email(self, email: str, name: str | None, when: datetime) -> bool:
        if not self._settings.email_enabled:
            return False
        organizer = self._settings.meeting_organizer_email or self._settings.smtp_user
        now = datetime.now().astimezone()
        ics = build_ics(
            uid=f"{uuid.uuid4()}@cygne",
            summary=f"Strategy call with {self._settings.agency_name}",
            description="Marketing strategy call booked via Cygne.",
            start=when,
            end=when + timedelta(minutes=MEETING_MINUTES),
            organizer_email=organizer,
            attendee_email=email,
            now=now,
        )
        summary = f"Strategy call with {self._settings.agency_name}"
        html = invitation_html(
            agency=self._settings.agency_name,
            prospect_name=name,
            when=when,
            duration_minutes=MEETING_MINUTES,
            organizer_email=organizer,
            add_to_calendar_url=google_calendar_link(
                summary, "Marketing strategy call booked via Cygne.", when, MEETING_MINUTES
            ),
        )
        subject = invitation_subject(self._settings.agency_name, when)
        return await send_invitation(self._settings, email, subject, html, ics)
