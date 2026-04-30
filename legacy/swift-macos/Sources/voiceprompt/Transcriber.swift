import Foundation

struct Transcriber {
    let modelPath: String

    private static let whisperCLI = "/opt/homebrew/bin/whisper-cli"

    func transcribe(wavURL: URL) throws -> String {
        let outputBase = wavURL.deletingPathExtension().path

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: Self.whisperCLI)
        proc.arguments = [
            "-m", modelPath,
            "-l", "auto",
            "-f", wavURL.path,
            "-otxt",
            "-of", outputBase,
            "--no-prints",
            "--no-timestamps",
        ]
        proc.standardOutput = Pipe()
        proc.standardError = Pipe()

        try proc.run()
        proc.waitUntilExit()

        defer {
            try? FileManager.default.removeItem(at: wavURL)
        }

        let txtURL = URL(fileURLWithPath: outputBase + ".txt")
        defer { try? FileManager.default.removeItem(at: txtURL) }

        guard proc.terminationStatus == 0 else {
            let errData = (proc.standardError as! Pipe).fileHandleForReading.readDataToEndOfFile()
            let errMsg = String(data: errData, encoding: .utf8) ?? "unknown error"
            throw TranscriberError.processFailed(errMsg)
        }

        let text = (try? String(contentsOf: txtURL, encoding: .utf8))?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return text
    }

    enum TranscriberError: LocalizedError {
        case processFailed(String)
        var errorDescription: String? {
            if case .processFailed(let msg) = self { return "whisper-cli failed: \(msg)" }
            return nil
        }
    }
}
