package com.example.telegram1000.auth

import android.webkit.WebView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

object BackendAuth {
    private const val API_BASE = "https://telegram-1000-web.onrender.com"
    private val http = OkHttpClient()
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    data class AuthResult(
        val token: String,
        val userId: String,
        val username: String?,
    )

    suspend fun exchangeNativeIdToken(idToken: String): AuthResult = withContext(Dispatchers.IO) {
        val payload = JSONObject()
            .put("id_token", idToken)
            .put("platform", "android")
        val request = Request.Builder()
            .url("$API_BASE/api/auth/native")
            .post(payload.toString().toRequestBody(jsonMedia))
            .build()
        http.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw IllegalStateException("Auth failed (${response.code}): $body")
            }
            val json = JSONObject(body)
            val user = json.getJSONObject("user")
            AuthResult(
                token = json.getString("token"),
                userId = user.getString("id"),
                username = user.optString("username").takeIf { it.isNotBlank() },
            )
        }
    }

    fun authorizedGet(path: String, sessionToken: String): Request =
        Request.Builder()
            .url("$API_BASE$path")
            .header("Authorization", "Bearer $sessionToken")
            .get()
            .build()

    /**
     * Call after Telegram Login SDK success — exchanges idToken, then opens the game WebView
     * with the token injected so the SPA unlocks only after auth.
     */
    suspend fun openGameAfterLogin(webView: WebView, idToken: String) {
        val auth = exchangeNativeIdToken(idToken)
        val escaped = JSONObject.quote(idToken)
        withContext(Dispatchers.Main) {
            webView.evaluateJavascript(
                """
                window.__NATIVE_ID_TOKEN__ = $escaped;
                window.__NATIVE_PLATFORM__ = "android";
                if (window.TelegramNativeAuth) {
                  window.TelegramNativeAuth.submit($escaped, "android");
                }
                """.trimIndent(),
                null,
            )
            webView.loadUrl(gameUrlWithToken(idToken))
        }
        // Prefer loading with query if WebView was empty — inject at document start via WebViewClient
        // when possible; evaluateJavascript after loadUrl also works if bridge is installed.
        Unit
    }

    /** Preferred: load URL with token so SPA bootstraps auth before showing game buttons. */
    fun gameUrlWithToken(idToken: String): String {
        val enc = java.net.URLEncoder.encode(idToken, Charsets.UTF_8.name())
        return "$API_BASE/?native_id_token=$enc&platform=android"
    }
}
