# Android native login (Telegram Login SDK)

Official SDK: [telegram-login-android](https://github.com/TelegramMessenger/telegram-login-android)

Production API base: `https://telegram-1000-1.onrender.com` (replace if your Render URL differs).

## 1. BotFather

Bot Settings → **Login Widget** → **package name** + **SHA-256** signing certificate (`./gradlew signingReport`).

## 2. Initialize SDK

```kotlin
import org.telegram.login.TelegramLogin

TelegramLogin.init(
    clientId = "YOUR_BOT_CLIENT_ID",
    redirectUri = "https://app123456-login.tg.dev/tglogin",
    scopes = listOf("profile", "phone")
)
```

## 3. Login + exchange idToken

```kotlin
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

object BackendAuth {
    private const val API_BASE = "https://telegram-1000-1.onrender.com"
    private val client = OkHttpClient()
    private val json = "application/json; charset=utf-8".toMediaType()

    data class AuthResult(val token: String, val userId: String)

    suspend fun exchangeNativeIdToken(idToken: String): AuthResult = withContext(Dispatchers.IO) {
        val payload = JSONObject()
            .put("id_token", idToken)
            .put("platform", "android")
        val req = Request.Builder()
            .url("`https://telegram-1000-1.onrender.com`/api/auth/native")
            .post(payload.toString().toRequestBody(json))
            .build()
        client.newCall(req).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) error(body)
            val json = JSONObject(body)
            AuthResult(
                token = json.getString("token"),
                userId = json.getJSONObject("user").getString("id"),
            )
        }
    }

    fun authorizedRequest(path: String, sessionToken: String): Request =
        Request.Builder()
            .url("`https://telegram-1000-1.onrender.com`")
            .header("Authorization", "Bearer ")
            .get()
            .build()
}

// In Activity after TelegramLogin.handleLoginResponse:
TelegramLogin.handleLoginResponse(uri, onSuccess = { loginData ->
    lifecycleScope.launch {
        try {
            val auth = BackendAuth.exchangeNativeIdToken(loginData.idToken)
            getSharedPreferences("auth", MODE_PRIVATE)
                .edit()
                .putString("session_token", auth.token)
                .apply()
        } catch (e: Exception) {
            Log.e("Auth", "Backend failed", e)
        }
    }
}, onError = { ... })

TelegramLogin.startLogin(this)
```

Add dependency: `implementation("com.squareup.okhttp3:okhttp:4.12.0")` and coroutines.

## 4. AndroidManifest App Link

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="https"
          android:host="app123456-login.tg.dev"
          android:pathPrefix="/tglogin" />
</intent-filter>
```

See `BackendAuth.kt` in this folder.

JWT validation: [Telegram docs](https://core.telegram.org/bots/telegram-login#validating-id-tokens).