# Integrations: Google Calendar & Email Invitations

Both are **optional**. Without them, Cygne books meetings in its own database and skips
the email. With them, bookings land on a real Google Calendar and the prospect receives
a branded invitation email with an `.ics` attachment.

## Google Calendar

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create (or
   select) a project.
2. **APIs & Services → Library →** enable the **Google Calendar API**.
3. **APIs & Services → OAuth consent screen:** configure it (External is fine), and add
   your own Google account under **Test users**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID →**
   application type **Desktop app**. Download the JSON.
5. Mint a refresh token (browser consent opens once):

   ```bash
   .venv/bin/python scripts/google_auth.py ~/Downloads/client_secret_xxx.json
   ```

6. Paste the printed values into `.env`:

   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REFRESH_TOKEN=...
   GOOGLE_CALENDAR_ID=primary
   ```

## Email invitation (Gmail SMTP)

1. Enable **2-Step Verification** on your Google account.
2. Create an **App password** (Google Account → Security → App passwords).
3. Add to `.env`:

   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=465
   SMTP_USER=you@gmail.com
   SMTP_PASSWORD=the-16-char-app-password
   CYGNE_AGENCY_NAME=Your Agency
   CYGNE_ORGANIZER_EMAIL=you@gmail.com
   ```

Once configured, `check_availability` reflects your real calendar, and booking a meeting
creates the event and emails the prospect a branded invitation with a calendar file.
