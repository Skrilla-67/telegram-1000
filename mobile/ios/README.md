# iOS native login (Telegram Login SDK)

Official SDK: [telegram-login-ios](https://github.com/TelegramMessenger/telegram-login-ios)

Production API base: `https://telegram-1000-1.onrender.com` (replace if your Render URL differs).

## 1. BotFather

Bot Settings → **Login Widget** → register **Bundle ID** and **Team ID**, configure redirect URI from BotFather (e.g. `https://app{appid}-login.tg.dev`).

## 2. Configure SDK

```swift
import TelegramLogin

TelegramLogin.configure(
    clientId: "YOUR_BOT_CLIENT_ID",
    redirectUri: "https://app123456-login.tg.dev",
    scopes: ["profile", "phone"]
)
```

## 3. Login + send idToken to backend

```swift
import Foundation

enum BackendAuth {
    static let apiBase = URL(string: "https://telegram-1000-1.onrender.com")!

    struct AuthResponse: Decodable {
        struct User: Decodable {
            let id: String
            let first_name: String
            let username: String?
            let photo_url: String?
            let phone_number: String?
        }
        let token: String
        let user: User
    }

    static func exchangeNativeIdToken(_ idToken: String) async throws -> AuthResponse {
        var request = URLRequest(url: apiBase.appendingPathComponent("/api/auth/native"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: String] = [
            "id_token": idToken,
            "platform": "ios",
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let text = String(data: data, encoding: .utf8) ?? ""
            throw URLError(.badServerResponse, userInfo: [NSLocalizedDescriptionKey: text])
        }
        return try JSONDecoder().decode(AuthResponse.self, from: data)
    }

    static func authorizedRequest(path: String, token: String) -> URLRequest {
        var request = URLRequest(url: apiBase.appendingPathComponent(path))
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        return request
    }
}

// Usage after TelegramLogin.login:
TelegramLogin.login { result in
    switch result {
    case .success(let loginData):
        Task {
            do {
                let auth = try await BackendAuth.exchangeNativeIdToken(loginData.idToken)
                UserDefaults.standard.set(auth.token, forKey: "session_token")
                print("Logged in as", auth.user.username ?? auth.user.first_name)
            } catch {
                print("Backend auth failed:", error)
            }
        }
    case .failure(let error):
        print(error)
    }
}
```

## 4. Universal Link callback

```swift
ContentView()
    .onOpenURL { url in
        if url.host?.contains("-login.tg.dev") == true {
            TelegramLogin.handle(url)
        }
    }
```

## 5. Game API

Use the session token from step 3:

```swift
var req = BackendAuth.authorizedRequest(path: "/api/me", token: sessionToken)
let (data, _) = try await URLSession.shared.data(for: req)
```

Server validates JWT per [Telegram OIDC docs](https://core.telegram.org/bots/telegram-login#validating-id-tokens).

Full sample: `BackendAuth.swift` in this folder.