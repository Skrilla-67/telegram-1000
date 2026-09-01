from __future__ import annotations

import asyncio
import hashlib
import logging
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    InlineKeyboardMarkup,
    InputRichMessage,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.description import (  # noqa: E402
    DESCRIPTION,
    SHORT_DESCRIPTION,
    build_rich_description_html,
)
from server import runtime  # noqa: E402
from server.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")


def webapp_keyboard(start_param: str | None = None) -> InlineKeyboardMarkup:
    url = settings.webapp_url.rstrip("/")
    if start_param:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}tgWebAppStartParam={quote(start_param)}"
    builder = InlineKeyboardBuilder()
    builder.button(text="Играть", web_app=WebAppInfo(url=url))
    return builder.as_markup()


def rich_about() -> InputRichMessage:
    return InputRichMessage(html=build_rich_description_html(settings.webapp_url))


async def send_game_about(message: Message, *, start_param: str | None = None) -> None:
    """Send the full Rich Message intro (rules + scoring + images)."""
    try:
        await message.answer_rich(
            rich_message=rich_about(),
            reply_markup=webapp_keyboard(start_param),
        )
    except Exception:
        logger.exception("sendRichMessage failed; falling back to plain text")
        await message.answer(
            "Кости «1000» — классика.\n\n"
            "5 кубиков, цель — 1000 очков.\n"
            "Открытие с 50, ямы, болты, обгон, самосвал 555, бочка с 880.\n\n"
            "После партии: победы/поражения всегда, а с 1-го по 1-е — банк в ₽ "
            "(каждый проигравший человек платит победителю 1000 − свои очки).\n\n"
            "Играй против ботов или создай комнату и зови друзей.",
            reply_markup=webapp_keyboard(start_param),
        )


def build_dispatcher(bot: Bot) -> Dispatcher:
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        payload = None
        if message.text and " " in message.text:
            payload = message.text.split(maxsplit=1)[1].strip()
        start_param = payload if payload and payload.lower().startswith("join") else None
        if start_param:
            await message.answer(
                "Тебя пригласили в комнату «1000».\n"
                "Нажми кнопку, чтобы присоединиться.",
                reply_markup=webapp_keyboard(start_param),
            )
            return
        await send_game_about(message)

    @dp.message(Command("rules", "help", "about"))
    async def rules(message: Message) -> None:
        await send_game_about(message)

    @dp.message(F.text.regexp(r"(?i)^код\s+[A-Fa-f0-9]{6}$"))
    async def share_code(message: Message) -> None:
        code = message.text.split()[-1].upper()
        param = f"join_{code}"
        me = await bot.get_me()
        username = me.username or "bot"
        link = f"https://t.me/{username}?start={param}"
        await message.answer(
            f"Ссылка в комнату {code}:\n{link}\n\nИли открой мини-приложение:",
            reply_markup=webapp_keyboard(param),
        )

    @dp.message(F.text)
    async def fallback(message: Message) -> None:
        await message.answer(
            "Открой мини-приложение кнопкой.\n"
            "Правила: /rules\n"
            "Поделиться комнатой: код ABC123",
            reply_markup=webapp_keyboard(),
        )

    return dp


async def configure_bot_profile(bot: Bot) -> None:
    """Sync BotFather-style description + command menu on startup."""
    try:
        await bot.set_my_short_description(short_description=SHORT_DESCRIPTION)
        await bot.set_my_description(description=DESCRIPTION)
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Описание игры и кнопка «Играть»"),
                BotCommand(command="rules", description="Правила, зоны и как ведётся счёт"),
                BotCommand(command="help", description="Краткая справка"),
            ]
        )
        logger.info("Bot description / short description / commands updated")
    except Exception:
        logger.exception("Failed to update bot profile texts")


def create_bot() -> Bot:
    return Bot(token=settings.bot_token)


def resolve_bot_mode() -> str:
    """Decide how the bot receives updates.

    Explicit BOT_MODE wins. In ``auto`` we prefer webhooks whenever we run in
    production behind a public https URL, and fall back to long polling for
    local development. Webhooks avoid the ``getUpdates`` conflict that occurs
    when two processes poll the same token (e.g. Render's zero-downtime deploy
    overlap or a leftover duplicate service).
    """
    mode = (settings.bot_mode or "auto").strip().lower()
    if mode in {"webhook", "polling", "off"}:
        return mode
    host = urlparse((settings.webapp_url or "").strip()).hostname or ""
    is_public_https = (
        settings.webapp_url.strip().lower().startswith("https://")
        and host not in {"", "localhost", "127.0.0.1"}
    )
    if not settings.dev_mode and is_public_https:
        return "webhook"
    return "polling"


def webhook_secret() -> str:
    """Stable, unguessable path/secret-token derived from the bot token."""
    digest = hashlib.sha256(f"{settings.bot_token}::tg-1000-webhook".encode()).hexdigest()
    return digest[:48]


def webhook_path() -> str:
    return f"/api/telegram/{webhook_secret()}"


def webhook_url() -> str:
    return f"{settings.webapp_url.rstrip('/')}{webhook_path()}"


async def _apply_bot_profile(bot: Bot) -> None:
    me = await bot.get_me()
    if me.username:
        runtime.bot_username = me.username
    await configure_bot_profile(bot)
    # Main Mini App / menu button — enable Main App also in BotFather.
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Играть",
            web_app=WebAppInfo(url=settings.webapp_url.rstrip("/")),
        )
    )


async def setup_webhook(bot: Bot, dp: Dispatcher) -> str:
    """Register a Telegram webhook so updates are pushed over HTTP.

    Returns the secret token that guards the webhook endpoint.
    """
    await _apply_bot_profile(bot)
    secret = webhook_secret()
    url = webhook_url()
    await bot.set_webhook(
        url=url,
        secret_token=secret,
        drop_pending_updates=False,
        allowed_updates=dp.resolve_used_update_types(),
    )
    logger.info("Bot webhook registered. url=%s", url)
    return secret


async def run_bot() -> None:
    """Long-polling loop; safe to run as a FastAPI background task."""
    if not settings.bot_token:
        logger.warning("BOT_TOKEN is not set; Telegram bot polling disabled")
        return

    bot = create_bot()
    dp = build_dispatcher(bot)
    await _apply_bot_profile(bot)
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Bot starting (long polling). WEBAPP_URL=%s", settings.webapp_url)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def main() -> None:
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example -> .env")
    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())
