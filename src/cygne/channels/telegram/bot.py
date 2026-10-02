"""Telegram channel adapter.

Bridges Telegram and the orchestrator: inbound messages become conversation turns,
and the human-in-the-loop quote approval is rendered as inline buttons in the operator
chat. Approving a quote sends it to the prospect and marks it sent; rejecting drops it.

Uses long polling, so no public URL or TLS is required to run it.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from cygne.config import Settings
from cygne.db.models import Prospect, Quote, QuoteStatus
from cygne.db.session import create_all, session_scope
from cygne.llm import LLMProvider
from cygne.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

WELCOME = (
    "Hi! I'm Cygne, an account manager for our marketing agency. "
    "Tell me a bit about your business and what you're hoping to improve."
)


class CygneBot:
    """A Telegram bot front-end for the Cygne agent."""

    def __init__(self, settings: Settings, provider: LLMProvider) -> None:
        self._settings = settings
        self._app = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .post_init(self._post_init)
            .build()
        )
        self._operator_chat = settings.telegram_operator_chat_id
        self._orchestrator = Orchestrator(
            provider,
            settings,
            quote_notifier=self._notify_quote,
            escalation_notifier=self._notify_escalation,
        )
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CallbackQueryHandler(self._on_quote_decision, pattern=r"^q:"))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

    def run(self) -> None:
        """Start long-polling. Blocks until interrupted."""
        logger.info("Cygne Telegram bot starting (polling).")
        self._app.run_polling()

    async def _post_init(self, _app: Application) -> None:
        """Ensure database tables exist before serving (idempotent)."""
        await create_all()

    # ── inbound prospect messages ───────────────────────────────────────────
    async def _on_start(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(WELCOME)

    def _is_operator_chat(self, chat_id: object) -> bool:
        return bool(self._operator_chat) and str(chat_id) == str(self._operator_chat)

    async def _on_message(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = str(update.effective_chat.id)
        if self._is_operator_chat(chat_id):
            return  # the operator chat is for approvals, not a prospect conversation
        await update.effective_chat.send_action("typing")
        try:
            reply = await self._orchestrator.handle("telegram", chat_id, update.message.text)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to handle message")
            reply = "Sorry, something went wrong on my side. Could you say that again?"
        await update.message.reply_text(reply)

    # ── human-in-the-loop quote approval ────────────────────────────────────
    async def _notify_quote(self, quote_id: int, _prospect_id: int, body: str) -> None:
        if not self._operator_chat:
            logger.warning("No operator chat configured; quote %s not surfaced.", quote_id)
            return
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"q:approve:{quote_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"q:reject:{quote_id}"),
                ]
            ]
        )
        await self._app.bot.send_message(
            chat_id=self._operator_chat,
            text=f"📝 Quote #{quote_id} awaiting approval:\n\n{body}",
            reply_markup=keyboard,
        )

    async def _on_quote_decision(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        # Callback data comes from the client and can be forged, so only clicks in the
        # operator chat may approve or reject a quote
        if query.message is None or not self._is_operator_chat(query.message.chat.id):
            logger.warning("Ignored a quote decision from chat %s", query.from_user.id)
            await query.answer("Only the operator chat can decide quotes.", show_alert=True)
            return
        await query.answer()
        try:
            _, action, raw_id = query.data.split(":")
            quote_id = int(raw_id)
        except ValueError:
            return
        if action not in ("approve", "reject"):
            return

        async with session_scope() as session:
            quote = await session.get(Quote, quote_id)
            if quote is None or quote.status != QuoteStatus.PENDING:
                await query.edit_message_text("This quote was already handled.")
                return
            prospect = await session.get(Prospect, quote.prospect_id)
            if action == "approve":
                quote.status = QuoteStatus.SENT
                target_chat, body = prospect.channel_chat_id, quote.body
            else:
                quote.status = QuoteStatus.REJECTED
                target_chat, body = None, None

        if action == "approve" and target_chat:
            await self._app.bot.send_message(
                chat_id=target_chat, text=f"Here's the proposal we put together for you:\n\n{body}"
            )
            await query.edit_message_text(f"✅ Approved and sent to the prospect.\n\n{body}")
        else:
            await query.edit_message_text("❌ Rejected. The prospect was not contacted.")

    # ── escalation ──────────────────────────────────────────────────────────
    async def _notify_escalation(self, prospect_id: int, reason: str) -> None:
        if not self._operator_chat:
            return
        await self._app.bot.send_message(
            chat_id=self._operator_chat,
            text=f"🙋 Prospect #{prospect_id} asked for a human.\nReason: {reason}",
        )
