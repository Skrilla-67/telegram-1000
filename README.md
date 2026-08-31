# Кости «1000» — Telegram Mini App

Классическая игра в кости на 1000 очков: открытие с 50, ямы, болты, обгон, самосвал 555, бочка с 880. Сейчас — партии против ботов.

Правила: https://selosovetov.ru/2016/11/25/igra-v-1000/

## Стек

- **API / движок**: Python, FastAPI
- **Бот**: aiogram 3
- **Mini App**: Vite + React + TypeScript

## Быстрый старт (локально)

```bash
# 1. Python
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # или cp .env.example .env

# 2. API (порт 8000)
python -m server.main

# 3. Web (другой терминал)
cd web
npm install
npm run dev
```

Открой http://localhost:5173 — в `DEV_MODE=true` можно играть без Telegram.

После `npm run build` в `web/` API также отдаёт мини-приложение с http://localhost:8000/.

Тесты движка:

```bash
pytest
```

## Telegram

1. Создай бота у [@BotFather](https://t.me/BotFather), получи токен.
2. Подними HTTPS-туннель на web (и при необходимости API):

```bash
# пример: cloudflared
cloudflared tunnel --url http://localhost:5173
```

3. В `.env`:

```env
BOT_TOKEN=...
WEBAPP_URL=https://xxxx.trycloudflare.com
DEV_MODE=false
```

4. Если API не на том же origin, что и web, задай во фронте:

```env
# web/.env
VITE_API_BASE=https://your-api-host
```

Либо проксируй `/api` через тот же туннель/nginx.

5. Запусти бота:

```bash
python -m bot.main
```

6. В BotFather: Bot Settings → Menu Button / Configure Mini App → URL = `WEBAPP_URL`.

7. Открой бота → `/start` → **Играть**.

## API

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/games` | `{ "bots": 1..3 }` — новая игра |
| GET | `/api/games/{id}` | состояние |
| POST | `/api/games/{id}/actions` | `{ "type": "roll" \| "bank" }` |

Заголовок авторизации: `X-Telegram-Init-Data` (или в dev `X-Dev-User`).

## Структура

```
bot/           Telegram-бот
server/        FastAPI + игровой движок
web/           Mini App
data/          сохранённые партии (создаётся автоматически)
```


## Telegram: Main Mini App + Login Widget

1. [@BotFather](https://t.me/BotFather) → Bot Settings → **Configure Mini App** / **Main Mini App** → URL = `WEBAPP_URL`.
2. Bot Settings → **Menu Button** → Configure menu button → Web App URL = `WEBAPP_URL` (код также выставляет menu button при старте).
3. BotFather → `/setdomain` → домен вашего `WEBAPP_URL` (нужен для **Login Widget** на сайте).
4. Env на Render: `BOT_TOKEN`, `BOT_USERNAME` (без `@`), `WEBAPP_URL`.

Профили пишутся в `data/users/`, история партий — в `data/history/`. На free Render диск эфемерный: после рестарта данные могут пропасть (для продакшена нужен Disk/БД).


## Native iOS / Android login

Mobile apps use official SDKs and exchange `idToken` (JWT) with this backend:

- [telegram-login-ios](https://github.com/TelegramMessenger/telegram-login-ios) → `POST /api/auth/native` `{ "id_token": "...", "platform": "ios" }`
- [telegram-login-android](https://github.com/TelegramMessenger/telegram-login-android) → same with `"android"`

Set `BOT_CLIENT_ID` from BotFather (numeric Client ID). Tokens are verified via Telegram JWKS ([docs](https://core.telegram.org/bots/telegram-login#validating-id-tokens)).

See `mobile/ios/README.md` and `mobile/android/README.md`.
