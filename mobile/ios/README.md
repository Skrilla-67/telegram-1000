# iOS native login (Telegram Login SDK)

Official SDK: [telegram-login-ios](https://github.com/TelegramMessenger/telegram-login-ios)

## BotFather

Bot Settings -> Login Widget -> register Bundle ID and Team ID.

## Backend exchange

POST `/api/auth/native` with JSON `{"id_token":"...","platform":"ios"}`.

Docs: [Validating ID tokens](https://core.telegram.org/bots/telegram-login#validating-id-tokens)
