#!/usr/bin/env bash
set -euo pipefail

BINARY_NAME="voiceprompt"
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="$HOME/.config/voiceprompt"
MODEL_DIR="$CONFIG_DIR/models"
MODEL_FILE="ggml-small-q5_1.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL_FILE"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENT_DIR/com.noel.voiceprompt.plist"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Installing voiceprompt"

# 1. Dependencies
echo "--> Checking whisper-cpp..."
if ! command -v whisper-cli &>/dev/null; then
    echo "    Installing whisper-cpp via Homebrew..."
    brew install whisper-cpp
else
    echo "    whisper-cli already installed."
fi

# 2. Config dir
mkdir -p "$MODEL_DIR"

# 3. Download Whisper model
if [ ! -f "$MODEL_DIR/$MODEL_FILE" ]; then
    echo "--> Downloading Whisper model (~180MB)..."
    curl -L --progress-bar -o "$MODEL_DIR/$MODEL_FILE" "$MODEL_URL"
else
    echo "--> Whisper model already present."
fi

# 4. API key
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo ""
    echo "    Enter your Gemini API key (free at https://aistudio.google.com/app/apikey):"
    read -r -s GEMINI_KEY
    echo "{\"gemini_api_key\":\"$GEMINI_KEY\"}" > "$CONFIG_DIR/config.json"
    chmod 600 "$CONFIG_DIR/config.json"
    echo "    Saved to $CONFIG_DIR/config.json"
else
    echo "--> config.json already exists, skipping API key setup."
fi

# 5. Write custom system prompt
cat > "$CONFIG_DIR/system_prompt.md" << 'EOF'
You are a prompt reformulator for coding assistants like Claude Code.
You receive a voice-dictated transcript that may contain filler words,
repetitions, or ambiguous phrasing. Return a single, clear, direct,
well-structured prompt in the same language as the user, ready to send
to a coding assistant. Output ONLY the final prompt — no preamble,
no explanation, no meta-commentary.
EOF

# 6. Build
echo "--> Building voiceprompt..."
cd "$REPO_DIR"
swift build -c release 2>&1

# 7. Install binary
echo "--> Installing binary to $INSTALL_DIR..."
sudo cp "$REPO_DIR/.build/release/$BINARY_NAME" "$INSTALL_DIR/$BINARY_NAME"
sudo chmod +x "$INSTALL_DIR/$BINARY_NAME"

# 8. LaunchAgent plist
GEMINI_KEY_VALUE=""
if [ -f "$CONFIG_DIR/config.json" ]; then
    GEMINI_KEY_VALUE=$(python3 -c "import json,sys; print(json.load(open('$CONFIG_DIR/config.json')).get('gemini_api_key',''))" 2>/dev/null || true)
fi

mkdir -p "$LAUNCH_AGENT_DIR"
cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.noel.voiceprompt</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/$BINARY_NAME</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>GEMINI_API_KEY</key>
        <string>$GEMINI_KEY_VALUE</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/voiceprompt.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/voiceprompt.log</string>
</dict>
</plist>
EOF

# 9. Load LaunchAgent
if launchctl list | grep -q "com.noel.voiceprompt"; then
    launchctl unload "$PLIST" 2>/dev/null || true
fi
launchctl load "$PLIST"

echo ""
echo "✓ voiceprompt installed and running as LaunchAgent."
echo ""
echo "REQUIRED: Grant permissions in System Settings:"
echo "  1. System Settings → Privacy & Security → Microphone → enable voiceprompt"
echo "  2. System Settings → Privacy & Security → Accessibility → add voiceprompt"
echo ""
echo "Log: tail -f /tmp/voiceprompt.log"
echo "Usage: hold ⌥Space (Option+Space) to record, release to process."
