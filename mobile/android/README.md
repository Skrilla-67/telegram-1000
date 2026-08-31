# Android native login (до запуска игры)

Official SDK: [telegram-login-android](https://github.com/TelegramMessenger/telegram-login-android)

API / WebApp: `https://telegram-1000-web.onrender.com`

## Поток

1. `TelegramLogin.startLogin` — пользователь входит.
2. `BackendAuth.exchangeNativeIdToken(idToken)`.
3. Открыть WebView: `BackendAuth.gameUrlWithToken(idToken)` **или** `openGameAfterLogin`.

Игровое меню в SPA разблокируется только после обмена токена.

## BotFather

Package name + SHA-256 (`./gradlew signingReport`).

## Пример

```kotlin
TelegramLogin.handleLoginResponse(uri, onSuccess = { loginData ->
    lifecycleScope.launch {
        val auth = BackendAuth.exchangeNativeIdToken(loginData.idToken)
        prefs.edit().putString("session_token", auth.token).apply()
        webView.loadUrl(BackendAuth.gameUrlWithToken(loginData.idToken))
    }
}, onError = { })
```

См. `BackendAuth.kt`.
