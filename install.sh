#!/usr/bin/env bash
# voiceprompt local installer
# Usage:  ./install.sh              (auto-detects uv > pipx > pip)
#         ./install.sh --uv         (force uv tool install)
#         ./install.sh --pipx       (force pipx install)
#         ./install.sh --uninstall  (remove the global binary)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PKG_DIR="$SCRIPT_DIR"
PKG_NAME="voiceprompt-cli"
BIN_NAME="voiceprompt"

color() { printf '\033[%sm%s\033[0m' "$1" "$2"; }
info()  { color "1;36" "==> "; echo "$*"; }
ok()    { color "1;32" " ok  "; echo "$*"; }
warn()  { color "1;33" "warn "; echo "$*"; }
err()   { color "1;31" "err  "; echo "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

# Run a command silently. Captures stdout+stderr; on failure the log is
# replayed to stderr so the user can see what went wrong, but on success
# nothing is printed.
run_quiet() {
    local log rc
    log=$(mktemp)
    if "$@" >"$log" 2>&1; then
        rm -f "$log"
        return 0
    fi
    rc=$?
    cat "$log" >&2
    rm -f "$log"
    return "$rc"
}

ensure_in_path() {
    if have "$BIN_NAME"; then
        return 0
    fi
    warn "'$BIN_NAME' is not in your PATH yet."
    if [[ "${PATH}" != *"$HOME/.local/bin"* ]]; then
        echo
        echo "  Add this to ~/.zshrc, ~/.bashrc, ~/.profile, or equivalent:"
        echo
        color "1;35" "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo
        echo "  Then run: source ~/.zshrc  (or open a new terminal)"
    else
        echo "  Open a new terminal or run: hash -r"
    fi
    return 1
}

install_with_uv() {
    # Clear cached wheel of this package: uv tool install --force would otherwise
    # reuse a stale build of the same version when reinstalling from a local edit.
    uv cache clean "$PKG_NAME" >/dev/null 2>&1 || true
    run_quiet uv tool install --force --reinstall --quiet "$PKG_DIR"
    uv tool update-shell >/dev/null 2>&1 || true
    ensure_in_path || true
}

install_with_pipx() {
    run_quiet pipx install --force --quiet "$PKG_DIR"
    pipx ensurepath >/dev/null 2>&1 || true
    ensure_in_path || true
}

install_with_pip() {
    run_quiet python3 -m pip install --user --upgrade --quiet "$PKG_DIR"
    ensure_in_path || true
}

uninstall() {
    if have uv; then
        info "Uninstalling with uv tool..."
        run_quiet uv tool uninstall "$PKG_NAME" || true
    fi
    if have pipx; then
        info "Uninstalling with pipx..."
        run_quiet pipx uninstall "$PKG_NAME" || true
    fi
    info "Trying pip uninstall..."
    run_quiet python3 -m pip uninstall -y "$PKG_NAME" || true
    ok "cleanup completed"
}

case "${1:-}" in
    --uninstall|-u)
        uninstall
        exit 0
        ;;
    --uv)
        if ! have uv; then err "uv is not installed. https://docs.astral.sh/uv/"; exit 1; fi
        install_with_uv
        ;;
    --pipx)
        if ! have pipx; then err "pipx is not installed. https://pipx.pypa.io"; exit 1; fi
        install_with_pipx
        ;;
    --help|-h)
        sed -n '2,7p' "$0"
        exit 0
        ;;
    "")
        # Auto-detect: prefer uv, then pipx, then pip
        if have uv; then
            install_with_uv
        elif have pipx; then
            install_with_pipx
        elif have python3; then
            warn "Could not find uv or pipx. I recommend installing one (cleaner):"
            echo "    uv:   curl -LsSf https://astral.sh/uv/install.sh | sh"
            echo "    pipx: brew install pipx     (mac)   |   apt install pipx (debian)"
            echo
            echo "Continuing with pip --user as fallback..."
            install_with_pip
        else
            err "Could not find uv, pipx, or python3. Install one and try again."
            exit 1
        fi
        ;;
    *)
        err "Unknown option: $1"
        echo "Use --help to see options."
        exit 1
        ;;
esac

echo
info "Ready. Launch the CLI with:"
echo
color "1;35" "    voiceprompt           "; echo "  -- open the interactive menu"
color "1;35" "    voiceprompt listen    "; echo "  -- background daemon: hotkey to dictate and paste anywhere"
color "1;35" "    voiceprompt --help    "; echo "  -- all commands"
echo
