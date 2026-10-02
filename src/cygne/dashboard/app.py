"""FastAPI app serving a read-only operations dashboard.

Shows the qualified-lead pipeline and booked meetings produced by the agent. Rendered
server-side as a single self-contained page (no external assets) so it deploys cleanly.
The page lists prospects' contact details, so it is behind HTTP Basic auth and does not
open at all until CYGNE_DASHBOARD_PASSWORD is set.
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from html import escape
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from cygne.config import get_settings
from cygne.dashboard.data import DashboardData, load_dashboard
from cygne.db.session import create_all


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Ensure tables exist before serving (idempotent)."""
    await create_all()
    yield


app = FastAPI(title="Cygne Dashboard", lifespan=_lifespan)
_basic = HTTPBasic(auto_error=False)


def require_operator(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    """Allow only the operator configured in the settings."""
    settings = get_settings()
    if not settings.dashboard_password:
        raise HTTPException(503, "Set CYGNE_DASHBOARD_PASSWORD to open the dashboard.")
    valid = credentials is not None and all(
        secrets.compare_digest(given.encode(), expected.encode())
        for given, expected in (
            (credentials.username, settings.dashboard_user),
            (credentials.password, settings.dashboard_password),
        )
    )
    if not valid:
        raise HTTPException(401, "Wrong user or password.", {"WWW-Authenticate": "Basic"})


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_operator)])
async def dashboard() -> str:
    """Render the operations dashboard."""
    return _render(await load_dashboard())


_QUAL_COLORS = {"high": "#34d399", "medium": "#fbbf24", "low": "#94a3b8", "unqualified": "#64748b"}


def _stat(label: str, value: int) -> str:
    return f"""<div class="stat"><div class="num">{value}</div><div class="lbl">{escape(label)}</div></div>"""


def _lead_rows(data: DashboardData) -> str:
    if not data.leads:
        return '<tr><td colspan="6" class="empty">No leads yet.</td></tr>'
    rows = []
    for lead in data.leads:
        color = _QUAL_COLORS.get(lead.qualification, "#94a3b8")
        rows.append(
            f"<tr><td>{escape(lead.company)}</td><td>{escape(lead.industry)}</td>"
            f"<td>{escape(lead.budget)}</td><td>{lead.score}</td>"
            f'<td><span class="pill" style="background:{color}1a;color:{color}">'
            f"{escape(lead.qualification)}</span></td>"
            f'<td class="why">{escape(lead.breakdown)}</td></tr>'
        )
    return "".join(rows)


def _meeting_rows(data: DashboardData) -> str:
    if not data.meetings:
        return '<tr><td colspan="2" class="empty">No meetings booked.</td></tr>'
    return "".join(
        f"<tr><td>{escape(m.company)}</td><td>{escape(m.when)}</td></tr>" for m in data.meetings
    )


def _render(data: DashboardData) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cygne — Pipeline</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #0b1020; color: #e2e8f0; padding: 32px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: #94a3b8; margin: 0 0 24px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; margin-bottom: 28px; }}
  .stat {{ background: #141b30; border: 1px solid #1e293b; border-radius: 12px; padding: 18px; }}
  .num {{ font-size: 30px; font-weight: 700; }}
  .lbl {{ color: #94a3b8; font-size: 13px; margin-top: 2px; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: .05em; color: #94a3b8; margin: 28px 0 10px; }}
  table {{ width: 100%; border-collapse: collapse; background: #141b30; border-radius: 12px; overflow: hidden; }}
  th, td {{ text-align: left; padding: 12px 16px; border-bottom: 1px solid #1e293b; }}
  th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: #94a3b8; }}
  tr:last-child td {{ border-bottom: none; }}
  .pill {{ padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
  .empty {{ color: #64748b; text-align: center; padding: 24px; }}
  .why {{ color: #94a3b8; font-size: 12px; }}
</style></head>
<body>
  <h1>🦢 Cygne — Lead Pipeline</h1>
  <p class="sub">Autopilot lead generation. Updated live as the agent qualifies prospects.</p>
  <div class="stats">
    {_stat("Total leads", data.total_leads)}
    {_stat("Qualified", data.qualified_leads)}
    {_stat("Meetings booked", data.meetings_booked)}
    {_stat("Quotes pending", data.quotes_pending)}
  </div>
  <h2>Leads</h2>
  <table><thead><tr><th>Company</th><th>Industry</th><th>Budget</th><th>Score</th><th>Qualification</th><th>Why</th></tr></thead>
  <tbody>{_lead_rows(data)}</tbody></table>
  <h2>Upcoming meetings</h2>
  <table><thead><tr><th>Company</th><th>When</th></tr></thead>
  <tbody>{_meeting_rows(data)}</tbody></table>
</body></html>"""
