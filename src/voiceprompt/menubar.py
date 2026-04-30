"""macOS menu bar app for voiceprompt.

Runs as a background process with a status indicator in the macOS menu bar.
The icon changes to reflect recording / processing state.
Requires: pip install rumps  (macOS only)

Launch with: voiceprompt menubar
"""

from __future__ import annotations

import contextlib
import sys
import threading
from typing import Any

if sys.platform != "darwin":
    raise RuntimeError("The menu bar app is only supported on macOS.")

try:
    import rumps  # type: ignore[import-not-found]
except ImportError as e:
    raise ImportError(
        "rumps is required for the menu bar app. "
        "Install it with: pip install rumps"
    ) from e

from voiceprompt import config as cfg_mod
from voiceprompt import history, reformulator
from voiceprompt.audio import recorder as rec_mod
from voiceprompt.audio import transcriber
from voiceprompt.system import clipboard as cb_mod
from voiceprompt.system import inject

# ── Icon states ───────────────────────────────────────────────────────────────
# Using text symbols so no image files are needed. These show in the menu bar.
_ICON_IDLE = "VP"
_ICON_RECORDING = "⏺ VP"
_ICON_PROCESSING = "⟳ VP"
_ICON_DONE = "✓ VP"


class VoicepromptMenuBar(rumps.App):
    """Menu bar application. Runs the hotkey daemon and dictation cycle."""

    def __init__(self) -> None:
        super().__init__(title=_ICON_IDLE, quit_button=None)
        self._config = cfg_mod.load()
        self._lock = threading.Lock()
        self._state = "idle"
        self._hotkey_listener: Any = None
        self._ctx: Any = None

        self.menu = [
            rumps.MenuItem("voiceprompt", callback=None),
            None,
            rumps.MenuItem("Dictate Once", callback=self._dictate_once_cb),
            None,
            rumps.MenuItem("Listening for hotkey", callback=None),
            None,
            rumps.MenuItem("Quit", callback=self._quit_cb),
        ]

        self._update_status_item()
        self._start_hotkey_listener()

    # ── State management ──────────────────────────────────────────────────────

    def _set_state(self, state: str) -> None:
        icons = {
            "idle": _ICON_IDLE,
            "recording": _ICON_RECORDING,
            "processing": _ICON_PROCESSING,
            "done": _ICON_DONE,
        }
        self._state = state
        self.title = icons.get(state, _ICON_IDLE)

    def _update_status_item(self) -> None:
        combo = self._config.hotkey
        mode = "push-to-talk" if self._config.hotkey_mode == "push_to_talk" else "toggle"
        self.menu["Listening for hotkey"].title = f"Listening · {combo} ({mode})"

    # ── Hotkey listener ───────────────────────────────────────────────────────

    def _start_hotkey_listener(self) -> None:
        from voiceprompt.system import hotkey as hk  # noqa: PLC0415

        if not hk.is_supported():
            return

        self._ctx = hk.HotkeyContext()
        combo = self._config.hotkey
        push_to_talk = self._config.hotkey_mode == "push_to_talk"

        with contextlib.suppress(hk.HotkeyError):
            if push_to_talk:
                self._hotkey_listener = hk.listen_hold(combo, self._ctx)
            else:
                self._hotkey_listener = hk.listen(combo, self._ctx)

        t = threading.Thread(target=self._hotkey_loop, daemon=True)
        t.start()

    def _hotkey_loop(self) -> None:
        while True:
            if self._ctx is None:
                return
            self._ctx.start_event.wait()
            self._ctx.start_event.clear()
            if self._state == "idle":
                self._run_cycle(paste=True)

    # ── Dictation cycle ───────────────────────────────────────────────────────

    def _dictate_once_cb(self, _: Any) -> None:
        if self._state != "idle":
            rumps.notification("voiceprompt", "", "Already recording or processing.")
            return
        threading.Thread(target=self._run_cycle, kwargs={"paste": False}, daemon=True).start()

    def _run_cycle(self, *, paste: bool) -> None:
        config = cfg_mod.load()  # reload in case settings changed
        self._config = config

        if not config.is_configured:
            rumps.notification("voiceprompt", "Not configured", "Run `voiceprompt set-key` first.")
            return

        # 1. Download model if needed (silent check only — no interactive prompt)
        if not transcriber.is_model_on_disk(config.transcription_model):
            rumps.notification(
                "voiceprompt",
                "Model not downloaded",
                "Open a terminal and run `voiceprompt dictate` once to download it.",
            )
            return

        # 2. Record
        self._set_state("recording")
        rec = rec_mod.Recorder(sample_rate=config.sample_rate)
        try:
            rec.start()
        except rec_mod.NoInputDeviceError:
            rumps.notification("voiceprompt", "No microphone found", "Check your audio input.")
            self._set_state("idle")
            return
        except Exception as exc:  # noqa: BLE001
            rumps.notification("voiceprompt", "Recording failed", str(exc))
            self._set_state("idle")
            return

        # Wait for hotkey stop signal (ctx.trigger_stop → app.exit) or a fixed max time.
        # Since we're not running the prompt_toolkit viz here, we just wait until
        # trigger_stop fires (recorded by the start_event being set again with push-to-talk)
        # or a stop event we manage ourselves.
        stop_event = threading.Event()
        if self._ctx is not None:
            # Intercept the ctx so trigger_stop wakes us up.
            self._ctx.set_running_app(_StopAdapter(stop_event))
        stop_event.wait(timeout=120)
        if self._ctx is not None:
            self._ctx.clear_running_app()

        result = rec.stop()

        if result is None:
            rumps.notification("voiceprompt", "Recording too short", "Try holding longer.")
            self._set_state("idle")
            return

        wav_path, _duration, peak = result
        if peak < 50:
            with contextlib.suppress(OSError):
                wav_path.unlink(missing_ok=True)
            rumps.notification("voiceprompt", "Silent audio", "Check your microphone.")
            self._set_state("idle")
            return

        # 3. Transcribe
        self._set_state("processing")
        try:
            transcript = transcriber.transcribe(
                wav_path,
                model_name=config.transcription_model,
                language=config.language,
            )
        except Exception as exc:  # noqa: BLE001
            with contextlib.suppress(OSError):
                wav_path.unlink(missing_ok=True)
            rumps.notification("voiceprompt", "Transcription failed", str(exc))
            self._set_state("idle")
            return
        finally:
            with contextlib.suppress(OSError):
                wav_path.unlink(missing_ok=True)

        if not transcript or not transcript.strip():
            rumps.notification("voiceprompt", "No speech detected", "Try again.")
            self._set_state("idle")
            return

        # 4. Refine (non-streaming for the menu bar — no TUI to display to)
        try:
            prompt = reformulator.reformulate_text(transcript, config)
        except reformulator.AuthError:
            rumps.notification("voiceprompt", "Auth failed", "Check your API key.")
            self._set_state("idle")
            return
        except reformulator.QuotaExceededError:
            rumps.notification("voiceprompt", "Quota exceeded", "Try again in a moment.")
            self._set_state("idle")
            return
        except reformulator.ProviderError as exc:
            rumps.notification("voiceprompt", "Provider error", str(exc)[:80])
            self._set_state("idle")
            return

        if not prompt or not prompt.strip():
            rumps.notification("voiceprompt", "Empty response", "The AI returned nothing.")
            self._set_state("idle")
            return

        # 5. Deliver
        self._set_state("done")
        copied = cb_mod.copy(prompt)
        if copied and paste:
            inject.paste()

        word_count = len(prompt.split())
        rumps.notification(
            "voiceprompt",
            "Prompt ready" + (" — pasted" if copied and paste else " — copied"),
            f"{word_count} words",
        )

        if config.history_enabled:
            with contextlib.suppress(Exception):
                history.log(
                    transcript=transcript,
                    prompt=prompt,
                    provider=reformulator.active_provider(config),
                    model=reformulator.active_model(config),
                    language=config.language,
                    record_secs=0.0,
                    refine_secs=0.0,
                )

        import time  # noqa: PLC0415
        time.sleep(1.5)
        self._set_state("idle")

    # ── Quit ─────────────────────────────────────────────────────────────────

    def _quit_cb(self, _: Any) -> None:
        if self._hotkey_listener is not None:
            with contextlib.suppress(Exception):
                self._hotkey_listener.stop()
        rumps.quit_application()


class _StopAdapter:
    """Minimal adapter that lets HotkeyContext.trigger_stop() wake a threading.Event."""

    def __init__(self, event: threading.Event) -> None:
        self._event = event

    def exit(self, result: Any = None) -> None:  # noqa: ARG002
        self._event.set()


def run() -> None:
    """Entry point for `voiceprompt menubar`."""
    VoicepromptMenuBar().run()
