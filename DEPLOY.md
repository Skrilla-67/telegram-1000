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
3. BotFather → Main Mini App / Menu Button / `/setdomain` → домен `telegram-1000-web.onrender.com`
4. Оставьте **один** процесс с `BOT_TOKEN` (иначе Conflict getUpdates)

## Дубликаты

В списке Services оставьте один live-сервис. Всё остальное с этим репо — Suspend.
