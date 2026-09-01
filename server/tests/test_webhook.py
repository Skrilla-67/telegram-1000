from __future__ import annotations

from aiogram import Bot
from fastapi.testclient import TestClient

from bot.main import resolve_bot_mode, webhook_secret
from server.config import settings
from server.main import app

FAKE_TOKEN = "123456:AAaaBBbbCCccDDddEEeeFFffGGggHHhhIIii"

MINIMAL_UPDATE = {"update_id": 1}


class StubDispatcher:
    def __init__(self) -> None:
        self.updates: list = []

    async def feed_update(self, bot, update):  # noqa: ANN001
        self.updates.append(update)


def _install_stub_bot(secret: str = "s3cret_webhook_token") -> StubDispatcher:
    dp = StubDispatcher()
    app.state.bot = Bot(token=FAKE_TOKEN)
    app.state.dispatcher = dp
    app.state.webhook_secret = secret
    app.state.bot_mode = "webhook"
    return dp


def test_webhook_rejects_wrong_path_secret():
    with TestClient(app) as client:
        _install_stub_bot("right-secret")
        r = client.post(
            "/api/telegram/wrong-secret",
            headers={"X-Telegram-Bot-Api-Secret-Token": "right-secret"},
            json=MINIMAL_UPDATE,
        )
        assert r.status_code == 403


def test_webhook_rejects_missing_header():
    with TestClient(app) as client:
        _install_stub_bot("right-secret")
        r = client.post("/api/telegram/right-secret", json=MINIMAL_UPDATE)
        assert r.status_code == 403


def test_webhook_accepts_valid_update():
    with TestClient(app) as client:
        dp = _install_stub_bot("right-secret")
        r = client.post(
            "/api/telegram/right-secret",
            headers={"X-Telegram-Bot-Api-Secret-Token": "right-secret"},
            json=MINIMAL_UPDATE,
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        assert len(dp.updates) == 1


def test_webhook_404_when_bot_disabled():
    with TestClient(app) as client:
        app.state.bot = None
        app.state.dispatcher = None
        app.state.webhook_secret = None
        r = client.post(
            "/api/telegram/anything",
            headers={"X-Telegram-Bot-Api-Secret-Token": "anything"},
            json=MINIMAL_UPDATE,
        )
        assert r.status_code == 404


def test_resolve_bot_mode_prefers_webhook_in_production(monkeypatch):
    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(settings, "webapp_url", "https://telegram-1000-web.onrender.com")
    monkeypatch.setattr(settings, "bot_mode", "auto")
    assert resolve_bot_mode() == "webhook"


def test_resolve_bot_mode_polling_for_local_dev(monkeypatch):
    monkeypatch.setattr(settings, "dev_mode", True)
    monkeypatch.setattr(settings, "webapp_url", "http://localhost:5173")
    monkeypatch.setattr(settings, "bot_mode", "auto")
    assert resolve_bot_mode() == "polling"


def test_resolve_bot_mode_explicit_override(monkeypatch):
    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(settings, "webapp_url", "https://telegram-1000-web.onrender.com")
    monkeypatch.setattr(settings, "bot_mode", "polling")
    assert resolve_bot_mode() == "polling"


def test_webhook_secret_is_stable_and_urlsafe(monkeypatch):
    monkeypatch.setattr(settings, "bot_token", FAKE_TOKEN)
    s1 = webhook_secret()
    s2 = webhook_secret()
    assert s1 == s2
    assert s1.isalnum()
    assert 32 <= len(s1) <= 256
