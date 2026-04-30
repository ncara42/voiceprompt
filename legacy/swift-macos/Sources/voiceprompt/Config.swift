import Foundation

struct Config {
    let geminiAPIKey: String
    let modelPath: String
    let systemPrompt: String

    static func load() throws -> Config {
        let configDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".config/voiceprompt")

        let apiKey = try resolveAPIKey(configDir: configDir)
        let modelPath = configDir.appendingPathComponent("models/ggml-small-q5_1.bin").path
        let systemPrompt = resolveSystemPrompt(configDir: configDir)

        return Config(geminiAPIKey: apiKey, modelPath: modelPath, systemPrompt: systemPrompt)
    }

    private static func resolveAPIKey(configDir: URL) throws -> String {
        if let env = ProcessInfo.processInfo.environment["GEMINI_API_KEY"], !env.isEmpty {
            return env
        }
        let jsonURL = configDir.appendingPathComponent("config.json")
        if let data = try? Data(contentsOf: jsonURL),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: String],
           let key = json["gemini_api_key"], !key.isEmpty {
            return key
        }
        throw ConfigError.missingAPIKey
    }

    private static func resolveSystemPrompt(configDir: URL) -> String {
        let promptURL = configDir.appendingPathComponent("system_prompt.md")
        if let content = try? String(contentsOf: promptURL, encoding: .utf8), !content.isEmpty {
            return content
        }
        return defaultSystemPrompt
    }

    static let defaultSystemPrompt = """
    You are a prompt reformulator for coding assistants like Claude Code. \
    You receive a voice-dictated transcript that may contain filler words, \
    repetitions, or ambiguous phrasing. Return a single, clear, direct, \
    well-structured prompt in the same language as the user, ready to send \
    to a coding assistant. Output ONLY the final prompt — no preamble, \
    no explanation, no meta-commentary.
    """

    enum ConfigError: LocalizedError {
        case missingAPIKey
        var errorDescription: String? {
            "GEMINI_API_KEY not set. Run: echo '{\"gemini_api_key\":\"YOUR_KEY\"}' > ~/.config/voiceprompt/config.json"
        }
    }
}
