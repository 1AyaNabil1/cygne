"""Branded HTML for the meeting-invitation email."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape
from urllib.parse import quote


def invitation_subject(agency: str, when: datetime) -> str:
    return f"Your strategy call with {agency} — {when.strftime('%A %d %b, %H:%M')}"


def google_calendar_link(summary: str, description: str, start: datetime, minutes: int) -> str:
    """Build a 'click to add to Google Calendar' link for the meeting."""
    end = start + timedelta(minutes=minutes)
    fmt = lambda d: d.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    params = (
        f"action=TEMPLATE&text={quote(summary)}"
        f"&dates={fmt(start)}/{fmt(end)}&details={quote(description)}"
    )
    return f"https://calendar.google.com/calendar/render?{params}"


def invitation_html(
    *,
    agency: str,
    prospect_name: str | None,
    when: datetime,
    duration_minutes: int,
    organizer_email: str,
    add_to_calendar_url: str,
) -> str:
    """Render the branded invitation email body."""
    greeting = f"Hi {escape(prospect_name)}," if prospect_name else "Hi there,"
    when_str = when.strftime("%A, %d %B %Y at %H:%M")
    return f"""<!doctype html>
<html><body style="margin:0;background:#f4f5f7;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1f2937">
  <div style="max-width:520px;margin:0 auto;padding:32px 16px">
    <div style="background:#fff;border-radius:14px;overflow:hidden;border:1px solid #e5e7eb">
      <div style="background:#0b1020;color:#fff;padding:24px 28px">
        <div style="font-size:22px;font-weight:700">🦢 {escape(agency)}</div>
      </div>
      <div style="padding:28px">
        <p style="font-size:16px">{greeting}</p>
        <p>Your strategy call is confirmed. We're looking forward to speaking with you.</p>
        <div style="background:#f4f5f7;border-radius:10px;padding:16px 18px;margin:20px 0">
          <div style="font-size:13px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em">When</div>
          <div style="font-size:17px;font-weight:600;margin-top:2px">{when_str}</div>
          <div style="color:#6b7280;margin-top:4px">{duration_minutes} minutes</div>
        </div>
        <div style="margin:24px 0">
          <a href="{escape(add_to_calendar_url)}" target="_blank"
             style="display:inline-block;background:#0b1020;color:#fff;text-decoration:none;
                    padding:12px 22px;border-radius:8px;font-weight:600;font-size:15px">
            📅 Add to Google Calendar
          </a>
        </div>
        <p style="color:#6b7280;font-size:13px">Or open the attached invite (.ics) to add it to any calendar.</p>
        <p style="color:#6b7280;font-size:13px;margin-top:24px">
          Questions? Just reply to this email ({escape(organizer_email)}).
        </p>
      </div>
    </div>
    <p style="text-align:center;color:#9ca3af;font-size:12px;margin-top:16px">
      Sent by {escape(agency)}
    </p>
  </div>
</body></html>"""
