"""Google Calendar client.

Wraps the (synchronous) Google API client and exposes the two operations the agent
needs — reading busy intervals and creating events — as async methods. We send our own
branded invitation email, so events are created with ``sendUpdates="none"``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime


class GoogleCalendarClient:
    """Minimal async wrapper over the Google Calendar v3 API."""

    def __init__(
        self, client_id: str, client_secret: str, refresh_token: str, calendar_id: str
    ) -> None:
        self._creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri=TOKEN_URI,
            scopes=SCOPES,
        )
        self._calendar_id = calendar_id

    def _service(self):
        return build("calendar", "v3", credentials=self._creds, cache_discovery=False)

    async def busy_intervals(self, time_min: datetime, time_max: datetime) -> list[Interval]:
        """Return busy intervals on the calendar within the window."""

        def _query() -> list[Interval]:
            body = {
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "items": [{"id": self._calendar_id}],
            }
            result = self._service().freebusy().query(body=body).execute()
            busy = result["calendars"][self._calendar_id].get("busy", [])
            return [
                Interval(
                    datetime.fromisoformat(b["start"]),
                    datetime.fromisoformat(b["end"]),
                )
                for b in busy
            ]

        return await asyncio.to_thread(_query)

    async def create_event(
        self,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        attendee_email: str,
    ) -> str:
        """Create a calendar event with the prospect as attendee. Returns the event id."""

        def _insert() -> str:
            body = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
                "attendees": [{"email": attendee_email}],
            }
            event = (
                self._service()
                .events()
                .insert(calendarId=self._calendar_id, body=body, sendUpdates="none")
                .execute()
            )
            return event["id"]

        return await asyncio.to_thread(_insert)
