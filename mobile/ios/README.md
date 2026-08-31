# iOS native login (до запуска игры)

Official SDK: [telegram-login-ios](https://github.com/TelegramMessenger/telegram-login-ios)

API / WebApp: `https://telegram-1000-web.onrender.com`

## Поток

1. Пользователь жмёт «Войти через Telegram» в приложении.
2. SDK отдаёт `idToken`.
3. `BackendAuth.exchangeNativeIdToken` → session token на сервере.
4. Только потом открывается WebView с игрой (токен инжектится до UI).

Без шагов 1–3 кнопки игры на сайте скрыты.

## BotFather

Bot Settings → **Login Widget** → Bundle ID + Team ID, redirect URI (например `https://app{appid}-login.tg.dev`).

## Код

См. `BackendAuth.swift`.

```swift
TelegramLogin.login { result in
  switch result {
  case .success(let loginData):
    Task {
      try await BackendAuth.openGame(in: webView, idToken: loginData.idToken)
    }
  case .failure(let error):
    print(error)
  }
}
```

Universal Link: `TelegramLogin.handle(url)` в `.onOpenURL`.

JWT: [Telegram OIDC](https://core.telegram.org/bots/telegram-login#validating-id-tokens).
