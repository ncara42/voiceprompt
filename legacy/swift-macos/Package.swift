// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "voiceprompt",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "voiceprompt",
            path: "Sources/voiceprompt",
            swiftSettings: [
                .swiftLanguageMode(.v5)
            ]
        )
    ]
)
