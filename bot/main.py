from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Allow running as `python bot/main.py` from repo root
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
    "Сейчас можно играть против ботов. Нажми кнопку, чтобы открыть мини-приложение."
)


def webapp_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Играть",
        web_app=WebAppInfo(url=settings.webapp_url),
    )
    return builder.as_markup()


async def main() -> None:
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example → .env")

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(START_TEXT, reply_markup=webapp_keyboard())

    @dp.message(F.text)
    async def fallback(message: Message) -> None:
        await message.answer(
            "Открой мини-приложение кнопкой ниже.",
            reply_markup=webapp_keyboard(),
        )

    logger.info("Bot starting. WEBAPP_URL=%s", settings.webapp_url)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
