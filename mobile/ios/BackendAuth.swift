import Foundation

/// Exchange Telegram Login SDK idToken for a backend session.
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
        var request = URLRequest(url: apiBase.appendingPathComponent(path))
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return request
    }
}