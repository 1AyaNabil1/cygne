<h1 align="center">🦢 Cygne</h1>

<p align="center">
  <em>A sales agent for marketing agencies: it answers new leads on Telegram, learns what
  they need, scores them, drafts proposals a person approves, and books the call.</em>
</p>

<p align="center">
  <a href="https://github.com/1AyaNabil1/cygne/actions/workflows/test.yml"><img alt="test" src="https://github.com/1AyaNabil1/cygne/actions/workflows/test.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
</p>

---

A prospect writes to the agency's Telegram bot. Cygne holds the conversation, asks for one
missing detail at a time, and keeps the lead's record up to date as it goes. When it knows
what the prospect wants and what they can spend, it drafts a proposal, which goes to a
person at the agency for approval before the prospect sees it. Then it offers real open
times and books the call, with a calendar invite.

What makes it more than a chatbot:

- **Facts are checked against the prospect's words.** Every detail the extraction model
  pulls out must come with the exact words it was taken from, and is kept only if those
  words are really in the prospect's messages and agree with the value. A guessed budget
  or an email the model made up has no quote to point to, so it never reaches the CRM.
- **The lead score explains itself.** Need, budget (against the agency's minimum),
  timeline, authority and reachability each earn part of 100 points, and the dashboard
  shows the breakdown, so "why is this lead hot?" has an answer.
- **A person approves every proposal.** Quotes wait in the operator's Telegram chat with
  Approve and Reject buttons; only the operator chat can decide.
- **The agent never does date arithmetic.** It books by the exact slot label it was
  offered, and only after the prospect agreed, picked a time and gave an email.
- **Any model.** Qwen out of the box, or any OpenAI-compatible API (OpenAI, Gemini, Groq,
  a local server) with two settings.
- **Production details:** tools bound to one prospect per turn, a reply guaranteed even
  when a model ends its turn after a tool call, a password-protected dashboard, a non-root
  Docker image, and CI that tests the code and the running stack.

## How it works

```
Prospect ─▶ Telegram ─▶ orchestrator ─▶ agent (tool loop) ─▶ LLM (Qwen or any OpenAI-compatible)
                            │              │
                            │              ├─ update_lead_context
                            │              ├─ draft_quote ─▶ operator chat: Approve / Reject
                            │              ├─ check_availability / schedule_meeting ─▶ Google Calendar + email invite
                            │              └─ escalate_to_human
                            │
                            ├─ grounded extraction ─▶ fit score + breakdown
                            └─ conversation notes
                                          │
                                          ▼
                                     PostgreSQL ─▶ dashboard (password)
```

The full picture, and the reasoning behind each decision, is in
[docs/architecture.md](docs/architecture.md).

## Quick start

You need a Telegram bot token (from [@BotFather](https://t.me/BotFather)), the chat ID of
the operator who approves quotes, and an API key for Qwen or another model.

```bash
cp .env.example .env    # then fill in the tokens, the API key and CYGNE_DASHBOARD_PASSWORD
docker compose up -d    # Postgres, the bot and the dashboard
```

Message your bot on Telegram, and open the dashboard at http://localhost:8000 (user
`operator`, the password you set). The bot uses long polling, so it needs no public URL.

Without Docker:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt -e .
python -m cygne.channels.telegram                # the bot
uvicorn cygne.dashboard.app:app --port 8000      # the dashboard
```

Google Calendar and the email invite are optional; without them, meetings are booked in
the database only. Setup: [docs/integrations.md](docs/integrations.md).

## Configuration

All settings are environment variables; [.env.example](.env.example) lists them with
comments. The main ones:

| Setting | |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OPERATOR_CHAT_ID` | The bot, and the chat where quotes are approved |
| `CYGNE_LLM_PROVIDER` | `qwen` (with `QWEN_API_KEY`) or `openai-compatible` (with `LLM_API_KEY`, `LLM_BASE_URL`) |
| `CYGNE_MAIN_MODEL`, `CYGNE_SUMMARY_MODEL` | The conversation model, and a cheaper one for extraction and notes |
| `CYGNE_DASHBOARD_PASSWORD` | Required: the dashboard stays closed without it |
| `CYGNE_MIN_MONTHLY_BUDGET` | The agency's smallest engagement; budgets are scored against it |
| `CYGNE_AGENCY_NAME`, `CYGNE_TIMEZONE` | Who the agent speaks for, and the timezone for slots |
| `DATABASE_URL` | Postgres (async); tables are created on start |

## Development

```bash
pytest                                      # 56 tests, on SQLite; no API keys needed
ruff check . && ruff format --check src tests scripts
python -m scripts.smoke                     # checks the configured model answers
```

The tests cover the evidence check, scoring, the prompt, tools, booking, the agent's reply
handling, the dashboard's password, and the operator-only quote approval. CI also builds
the Docker stack and checks it starts.

## License

[MIT](LICENSE) © 2026 Ayatullah Nabil
