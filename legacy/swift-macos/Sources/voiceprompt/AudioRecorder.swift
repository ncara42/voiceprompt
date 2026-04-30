import AVFoundation
import Foundation

class AudioRecorder {
    private var recorder: AVAudioRecorder?
    private var currentURL: URL?

    func requestPermission(completion: @escaping (Bool) -> Void) {
        AVCaptureDevice.requestAccess(for: .audio) { completion($0) }
    }

    func start() {
        let ts = Int(Date().timeIntervalSince1970)
        let url = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("vp-\(ts).wav")
        currentURL = url

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
        ]

        do {
            recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder?.record()
        } catch {
            print("[voiceprompt] AVAudioRecorder error: \(error)")
        }
    }

    func stop() -> URL? {
        guard let rec = recorder, rec.isRecording else { return currentURL }
        let duration = rec.currentTime
        rec.stop()
        recorder = nil

        guard duration >= 0.5 else {
            print("[voiceprompt] Recording too short (\(String(format: "%.1f", duration))s), ignoring.")
            if let url = currentURL { try? FileManager.default.removeItem(at: url) }
            return nil
        }

        print("[voiceprompt] Recorded \(String(format: "%.1f", duration))s")
        return currentURL
    }
}
