# Один сервис Render — один URL

## Канонический сервис

Используйте **только** сервис из Blueprint: **`telegram-1000-web`**.

- Primary URL: `https://telegram-1000-web.onrender.com`
- В Environment этого сервиса: `WEBAPP_URL=https://telegram-1000-web.onrender.com` (без слэша в конце или с — не важно, код обрежет)
- `DEV_MODE=false`
- `BOT_TOKEN`, `BOT_USERNAME=igraV1000_bot`

## Почему URL «меняется»

На Render **каждый новый Web Service** получает новый адрес (`telegram-1000`, `telegram-1000-1`, `telegram-1000-web`, …).

Если в Dashboard открыт **`telegram-1000-1`** — это **другой**, обычно устаревший инстанс (старый коммит, без `web/dist`, другой `WEBAPP_URL`). Его нужно **Suspend** или **Delete**.

Не нажимайте «New Web Service» / не применяйте Blueprint повторно как новый сервис. Нужен **Manual Deploy** на уже существующем `telegram-1000-web`.

## После каждого деплоя

1. Откройте `https://telegram-1000-web.onrender.com/api/health`
2. Должно быть `"web_index": true` и `"webapp_host_ok": true`
3. Там же `"bot_mode": "webhook"` — значит бот получает апдейты через webhook
4. BotFather → Main Mini App / Menu Button / `/setdomain` → домен `telegram-1000-web.onrender.com`

## Режим бота и ошибка `Conflict: terminated by other getUpdates`

Эта ошибка возникает, когда **два процесса** одновременно опрашивают Telegram
методом `getUpdates` с одним `BOT_TOKEN` (пересечение старого и нового
контейнера при деплое, дубль-сервис или локально запущенный `python -m bot.main`).

Чтобы этого не было, в проде бот работает **через webhook** — Telegram сам шлёт
апдейты на `POST /api/telegram/<secret>`, `getUpdates` не вызывается вообще.
Режим выбирается переменной `BOT_MODE`:

- `auto` (по умолчанию) — webhook в проде (`DEV_MODE=false` + публичный https
  `WEBAPP_URL`), long polling локально.
- `webhook` / `polling` — принудительно.
- `off` — не запускать бота (напр. если бот вынесен в отдельный сервис).

Проверить активный режим: `GET /api/health` → поле `bot_mode`.

## Дубликаты

В списке Services оставьте один live-сервис. Всё остальное с этим репо — Suspend.
С webhook несколько инстансов уже не конфликтуют, но лишние сервисы всё равно
лучше погасить.
