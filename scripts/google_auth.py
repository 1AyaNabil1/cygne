"""One-time helper to mint a Google Calendar refresh token.

Prerequisite: a Google Cloud OAuth *Desktop* client. Download its JSON and run:

    .venv/bin/python scripts/google_auth.py path/to/client_secret.json

A browser window opens for consent; on success the script prints the client id,
client secret, and refresh token to paste into your .env.
"""

from __future__ import annotations

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/google_auth.py <client_secret.json>")
        raise SystemExit(1)

    secrets_path = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(secrets_path) as handle:
        installed = json.load(handle)["installed"]

    print("\nAdd these to your .env:\n")
    print(f"GOOGLE_CLIENT_ID={installed['client_id']}")
    print(f"GOOGLE_CLIENT_SECRET={installed['client_secret']}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
