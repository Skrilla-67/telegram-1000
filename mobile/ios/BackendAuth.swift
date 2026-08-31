import Foundation
import WebKit

/// Exchange Telegram Login SDK idToken for a backend session, then open the game WebView.
enum BackendAuth {
    static let apiBase = URL(string: "https://telegram-1000-web.onrender.com")!
    static let webAppURL = URL(string: "https://telegram-1000-web.onrender.com")!

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
        guard let url = URL(string: "/api/auth/native", relativeTo: apiBase)?.absoluteURL else {
            throw URLError(.badURL)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "id_token": idToken,
            "platform": "ios",
        ])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let text = String(data: data, encoding: .utf8) ?? "HTTP error"
            throw URLError(.badServerResponse, userInfo: [NSLocalizedDescriptionKey: text])
        }
        return try JSONDecoder().decode(AuthResponse.self, from: data)
    }

    static func authorizedRequest(path: String, method: String = "GET", token: String) -> URLRequest {
        var request = URLRequest(url: apiBase.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))))
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return request
    }

    /// Inject session into WebView *before* the game UI unlocks.
    static func openGame(in webView: WKWebView, idToken: String) async throws {
        let auth = try await exchangeNativeIdToken(idToken)
        UserDefaults.standard.set(auth.token, forKey: "session_token")

        let js = """
        window.__NATIVE_ID_TOKEN__ = \(jsonString(idToken));
        window.__NATIVE_PLATFORM__ = "ios";
        """
        let script = WKUserScript(source: js, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        webView.configuration.userContentController.addUserScript(script)
        await MainActor.run {
            webView.load(URLRequest(url: webAppURL))
        }
    }

    private static func jsonString(_ value: String) -> String {
        let data = try! JSONSerialization.data(withJSONObject: value)
        return String(data: data, encoding: .utf8)!
    }
}
