"""Test fixtures: an isolated SQLite database wired into Cygne's session layer."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator

import pytest_asyncio

# Point the app at a throwaway SQLite file before any cygne.db import reads settings.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH}"

from cygne.db import session_scope  # noqa: E402
from cygne.db.helpers import get_or_create_prospect  # noqa: E402
from cygne.db.models import Base  # noqa: E402
from cygne.db.session import get_engine  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _schema() -> AsyncIterator[None]:
    """Recreate all tables fresh before each test for isolation."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def prospect_id() -> int:
    """Seed a prospect and return its id."""
    async with session_scope() as session:
        prospect = await get_or_create_prospect(session, "telegram", "test-chat-1")
        return prospect.id
