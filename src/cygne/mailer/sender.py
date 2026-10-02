"""Async SMTP sender for the branded meeting invitation."""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from cygne.config import Settings

logger = logging.getLogger(__name__)


async def send_invitation(
    settings: Settings, to_email: str, subject: str, html: str, ics_text: str
) -> bool:
    """Send the invitation email with an .ics attachment. Returns True on success."""
    if not settings.email_enabled:
        logger.info("Email not configured; skipping invitation to %s", to_email)
        return False

    message = EmailMessage()
    message["From"] = f"{settings.agency_name} <{settings.smtp_user}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("Your strategy call is confirmed. See the attached calendar invite.")
    message.add_alternative(html, subtype="html")
    message.add_attachment(
        ics_text.encode("utf-8"),
        maintype="text",
        subtype="calendar",
        filename="invite.ics",
        params={"method": "REQUEST"},
    )

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_port == 465,
            start_tls=settings.smtp_port == 587,
        )
        return True
    except Exception as error:  # noqa: BLE001
        logger.error("Failed to send invitation to %s: %s", to_email, error)
        return False
