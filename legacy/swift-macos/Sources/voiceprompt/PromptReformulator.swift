import Foundation

struct PromptReformulator {
    let apiKey: String
    let systemPrompt: String

    private let endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

    func reformulate(_ transcript: String) async throws -> String {
        guard var comps = URLComponents(string: endpoint) else {
            throw ReformulatorError.invalidURL
        }
        comps.queryItems = [URLQueryItem(name: "key", value: apiKey)]
        guard let url = comps.url else { throw ReformulatorError.invalidURL }

        var request = URLRequest(url: url, timeoutInterval: 20)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "systemInstruction": ["parts": [["text": systemPrompt]]],
            "contents": [["parts": [["text": transcript]]]],
            "generationConfig": [
                "temperature": 0.3,
                "maxOutputTokens": 1024,
            ],
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            let msg = String(data: data, encoding: .utf8) ?? "HTTP \(http.statusCode)"
            throw ReformulatorError.apiError(msg)
        }

        guard
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let candidates = json["candidates"] as? [[String: Any]],
            let content = candidates.first?["content"] as? [String: Any],
            let parts = content["parts"] as? [[String: Any]],
            let text = parts.first?["text"] as? String
        else {
            throw ReformulatorError.invalidResponse(String(data: data, encoding: .utf8) ?? "")
        }

        return text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    enum ReformulatorError: LocalizedError {
        case invalidURL
        case apiError(String)
        case invalidResponse(String)
        var errorDescription: String? {
            switch self {
            case .invalidURL: return "Invalid Gemini API URL"
            case .apiError(let m): return "Gemini API error: \(m)"
            case .invalidResponse(let m): return "Unexpected Gemini response: \(m)"
            }
        }
    }
}
