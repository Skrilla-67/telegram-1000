# Android native login (Telegram Login SDK)

Official SDK: [telegram-login-android](https://github.com/TelegramMessenger/telegram-login-android)

## BotFather

Bot Settings -> Login Widget -> package name + SHA-256 fingerprint.

## Backend exchange

POST `/api/auth/native` with JSON `{"id_token":"...","platform":"android"}`.

Docs: [Validating ID tokens](https://core.telegram.org/bots/telegram-login#validating-id-tokens)
