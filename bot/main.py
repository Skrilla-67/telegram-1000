from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import MenuButtonWebApp, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

START_TEXT = (
    "Кости «1000» — классика.\n\n"
    "5 кубиков, цель — 1000 очков.\n"
    "Открытие с 50, ямы, болты, обгон, самосвал 555, бочка с 880.\n\n"
    "Играй против ботов или создай комнату и зови друзей."
)

def webapp_keyboard(start_param: str | None = None):
    url = settings.webapp_url.rstrip("/")
    if start_param:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}tgWebAppStartParam={quote(start_param)}"
    builder = InlineKeyboardBuilder()
    builder.button(text="Играть", web_app=WebAppInfo(url=url))
    return builder.as_markup()


def build_dispatcher(bot: Bot) -> Dispatcher:
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        payload = None
        if message.text and " " in message.text:
            payload = message.text.split(maxsplit=1)[1].strip()
        start_param = payload if payload and payload.lower().startswith("join") else None
        text = START_TEXT
        if start_param:
            text = (
                "Тебя пригласили в комнату «1000».\n"
                "Нажми кнопку, чтобы присоединиться."
            )
        await message.answer(text, reply_markup=webapp_keyboard(start_param))

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
            "Чтобы поделиться комнатой, напиши: код ABC123",
            reply_markup=webapp_keyboard(),
        )

    return dp


async def run_bot() -> None:
    """Long-polling loop; safe to run as a FastAPI background task."""
    if not settings.bot_token:
        logger.warning("BOT_TOKEN is not set; Telegram bot polling disabled")
        return

    bot = Bot(token=settings.bot_token)
    dp = build_dispatcher(bot)
    await bot.delete_webhook(drop_pending_updates=False)
    # Main Mini App / menu button — enable Main App also in BotFather.
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Играть",
            web_app=WebAppInfo(url=settings.webapp_url.rstrip("/")),
        )
    )
    logger.info("Bot starting. WEBAPP_URL=%s", settings.webapp_url)
    await dp.start_polling(bot)


async def main() -> None:
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example -> .env")
    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())
