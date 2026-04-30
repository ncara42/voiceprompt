import AppKit
import AVFoundation
import Foundation

// ── CLI test modes ────────────────────────────────────────────────────────────

let args = CommandLine.arguments
if args.count > 1 {
    switch args[1] {
    case "--test-transcribe" where args.count > 2:
        let config = try Config.load()
        let t = Transcriber(modelPath: config.modelPath)
        let text = try t.transcribe(wavURL: URL(fileURLWithPath: args[2]))
        print(text)
        exit(0)

    case "--test-llm" where args.count > 2:
        let config = try Config.load()
        let r = PromptReformulator(apiKey: config.geminiAPIKey, systemPrompt: config.systemPrompt)
        let input = args[2...].joined(separator: " ")
        let prompt = try await r.reformulate(input)
        print(prompt)
        exit(0)

    case "--help", "-h":
        print("""
        voiceprompt — hold ⌥Space to record, release to transcribe & paste

        Options:
          --test-transcribe <file.wav>   Transcribe a WAV file and print result
          --test-llm <text...>           Reformulate text via Gemini and print result
          --help                         Show this help
        """)
        exit(0)

    default:
        break
    }
}

// ── NSApplication (menu bar icon requires AppKit initialized) ─────────────────

let app = NSApplication.shared
app.setActivationPolicy(.accessory)   // background only — no Dock icon

// ── Load config ───────────────────────────────────────────────────────────────

let config: Config
do {
    config = try Config.load()
} catch {
    print("[voiceprompt] ✗ \(error.localizedDescription)")
    Notifier.notify(title: "voiceprompt error", body: error.localizedDescription)
    exit(1)
}

// ── Request microphone access ─────────────────────────────────────────────────

AVCaptureDevice.requestAccess(for: .audio) { granted in
    if !granted {
        print("[voiceprompt] ✗ Microphone access denied.")
        print("[voiceprompt]   System Settings → Privacy & Security → Microphone")
    }
}

// ── Components ────────────────────────────────────────────────────────────────

let statusBar = StatusBarController()
let audioRecorder = AudioRecorder()
let hotkeyManager = HotkeyManager()
let focusTracker = AppFocusTracker()

// ── Shared record/stop logic (used by both icon click and hotkey) ─────────────

func startRecording() {
    print("[voiceprompt] ● Recording…")
    statusBar.setRecording()
    audioRecorder.start()
}

func stopRecording() {
    guard let wavURL = audioRecorder.stop() else {
        statusBar.setIdle()
        return
    }

    // Capture target app NOW (before we lose track of it)
    let targetApp = focusTracker.lastApp

    statusBar.setProcessing()
    print("[voiceprompt] ◼ Transcribing…")

    Task {
        defer { statusBar.setIdle() }
        do {
            let transcriber = Transcriber(modelPath: config.modelPath)
            let transcript = try transcriber.transcribe(wavURL: wavURL)

            guard !transcript.isEmpty else {
                print("[voiceprompt] No speech detected.")
                Notifier.notify(title: "voiceprompt", body: "No speech detected.")
                return
            }

            print("[voiceprompt] Transcript: \(transcript)")
            print("[voiceprompt] Reformulating via Gemini…")

            let reformulator = PromptReformulator(
                apiKey: config.geminiAPIKey,
                systemPrompt: config.systemPrompt
            )

            let finalPrompt: String
            do {
                finalPrompt = try await reformulator.reformulate(transcript)
            } catch {
                print("[voiceprompt] Gemini unavailable (\(error.localizedDescription)), using transcript.")
                finalPrompt = transcript
            }

            print("[voiceprompt] → \(finalPrompt)\n")
            PasteboardManager.copyAndPaste(finalPrompt, into: targetApp)
            Notifier.notify(title: "Prompt inserted ✓", body: String(finalPrompt.prefix(100)))

        } catch {
            print("[voiceprompt] ✗ \(error.localizedDescription)")
            Notifier.notify(title: "voiceprompt error", body: error.localizedDescription)
        }
    }
}

// ── Wire callbacks ────────────────────────────────────────────────────────────

statusBar.onStartRecording = { startRecording() }
statusBar.onStopRecording  = { stopRecording() }

hotkeyManager.onStartRecording = { startRecording() }
hotkeyManager.onStopRecording  = { stopRecording() }

// ── Start hotkey listener ─────────────────────────────────────────────────────

if hotkeyManager.start() {
    print("[voiceprompt] Ready — hold ⌥Space to record. Press ^C to quit.")
} else {
    print("[voiceprompt] ✗ Could not create event tap.")
    print("[voiceprompt]   System Settings → Privacy & Security → Accessibility → add voiceprompt")
    Notifier.notify(
        title: "voiceprompt needs Accessibility",
        body: "System Settings → Privacy & Security → Accessibility → add voiceprompt"
    )
}

app.run()
