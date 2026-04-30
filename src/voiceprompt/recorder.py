"""Cross-platform audio recording to a WAV file using sounddevice + soundfile."""

from __future__ import annotations

import contextlib
import os
import queue
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


@contextlib.contextmanager
def _silence_native_stderr():
    """Temporarily redirect the C-level stderr (fd 2) to /dev/null.

    Used to mute PortAudio / CoreAudio's noisy 'AUHAL Warning' lines while we
    probe sample-rate fallbacks. Python-side stderr writes still go through
    `sys.stderr`, so application logging is unaffected.
    """
    try:
        saved = os.dup(2)
    except OSError:
        yield
        return
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, 2)
            yield
        finally:
            os.dup2(saved, 2)
            os.close(devnull)
    finally:
        os.close(saved)

# How many recent RMS samples to keep for the live waveform UI.
LEVEL_BUFFER_SIZE = 64


class NoInputDeviceError(RuntimeError):
    """Raised when PortAudio cannot find a usable default input device."""

    def __init__(self) -> None:
        super().__init__("No audio input found.")


def _is_no_input_device_error(exc: Exception) -> bool:
    """Return True for sounddevice/PortAudio errors caused by missing input."""
    message = " ".join(str(exc).lower().split())
    return (
        "error querying device -1" in message
        or "input device -1" in message
        or "no default input device" in message
        or "default input device unavailable" in message
        or "default input device not available" in message
    )


class Recorder:
    """Records mono PCM audio at the configured sample rate, streamed to a WAV file.

    Lifecycle: instantiate -> start() (returns immediately) -> stop() (returns Path).
    Exposes streaming meters: `latest_peak()`, `get_levels()`, `elapsed()`, `pause()/resume()`.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._writer_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._path: Path | None = None
        self._started_at: float | None = None
        self._levels: deque[int] = deque([0] * LEVEL_BUFFER_SIZE, maxlen=LEVEL_BUFFER_SIZE)
        self._latest_peak: int = 0
        self._paused = threading.Event()

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            # Drop frames silently rather than crash; status is just a warning here
            pass
        # Always update the live meters so the visualizer keeps moving even if paused.
        chunk = indata
        peak = int(np.abs(chunk).max()) if chunk.size else 0
        if chunk.size:
            f = chunk.astype(np.float32)
            rms = int(np.sqrt(np.mean(f * f)))
        else:
            rms = 0
        self._latest_peak = peak
        self._levels.append(rms)
        # Only persist frames to the WAV when not paused.
        if not self._paused.is_set():
            self._queue.put(indata.copy())

    def _writer(self, path: Path) -> None:
        with sf.SoundFile(
            str(path),
            mode="x",
            samplerate=self.sample_rate,
            channels=self.channels,
            subtype="PCM_16",
        ) as fh:
            while not self._stop_event.is_set() or not self._queue.empty():
                try:
                    chunk = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                fh.write(chunk)

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("recording already in progress")

        # Resolve a sample rate the input device actually supports BEFORE we
        # spin up the writer thread (so the WAV header matches reality).
        self.sample_rate = self._resolve_sample_rate(self.sample_rate)

        # Path must be unique even when two recordings start within the same
        # wall-clock second (e.g. rapid hotkey toggles, recovered daemon).
        # Nanosecond resolution + PID guarantees no collision with mode="x".
        tmp_dir = Path(tempfile.gettempdir())
        self._path = tmp_dir / f"voiceprompt-{os.getpid()}-{time.time_ns()}.wav"
        self._stop_event.clear()

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=self._callback,
        )
        self._writer_thread = threading.Thread(
            target=self._writer, args=(self._path,), daemon=True
        )
        self._writer_thread.start()
        self._stream.start()
        self._started_at = time.monotonic()

    def _resolve_sample_rate(self, requested: int) -> int:
        """Return a sample rate the default input device accepts.

        On macOS many devices (especially Bluetooth headsets / AirPods in HFP)
        reject 16 kHz with PortAudio error -9986 / CoreAudio -10851. We try the
        requested rate, then the device's native rate, then a list of common
        rates as last resort. faster-whisper resamples internally so the exact
        rate does not matter for transcription quality.
        """
        candidates: list[int] = [requested]
        try:
            info = sd.query_devices(kind="input")
            native = int(info.get("default_samplerate") or 0)
            if native and native not in candidates:
                candidates.append(native)
        except Exception as e:  # noqa: BLE001
            if _is_no_input_device_error(e):
                raise NoInputDeviceError() from e
        for fallback in (48000, 44100, 32000, 22050, 16000, 8000):
            if fallback not in candidates:
                candidates.append(fallback)

        last_error: Exception | None = None
        with _silence_native_stderr():
            for rate in candidates:
                try:
                    sd.check_input_settings(
                        samplerate=rate, channels=self.channels, dtype="int16"
                    )
                    return rate
                except Exception as e:  # noqa: BLE001
                    if _is_no_input_device_error(e):
                        raise NoInputDeviceError() from e
                    last_error = e
                    continue
        raise RuntimeError(
            f"No sample rate accepted by default input device "
            f"(tried {candidates}). Last error: {last_error}"
        )

    def stop(self) -> tuple[Path, float, int] | None:
        """Stop and return (wav_path, duration_seconds, peak_amplitude).

        peak_amplitude is the max absolute int16 sample (0..32767). 0 means total silence
        (mic muted or no permission). Returns None if too short or file missing.
        """
        if self._stream is None:
            return None

        duration = time.monotonic() - (self._started_at or time.monotonic())
        self._stream.stop()
        self._stream.close()
        self._stream = None

        self._stop_event.set()
        if self._writer_thread is not None:
            self._writer_thread.join(timeout=2)
            self._writer_thread = None

        path = self._path
        self._path = None
        self._started_at = None

        if path is None or not path.exists():
            return None

        if duration < 0.4:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
            return None

        # Inspect peak amplitude (cheap — read once back from the WAV we just wrote)
        peak = 0
        try:
            data, _ = sf.read(str(path), dtype="int16")
            if data.size:
                peak = int(np.abs(data).max())
        except Exception:  # noqa: BLE001
            pass

        return path, duration, peak


    def latest_peak(self) -> int:
        return self._latest_peak

    def get_levels(self) -> list[int]:
        """Recent RMS levels (oldest -> newest), used to render the live waveform."""
        return list(self._levels)

    def elapsed(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.monotonic() - self._started_at

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def is_paused(self) -> bool:
        return self._paused.is_set()


def list_input_devices() -> list[dict]:
    """List available input devices for diagnostics / config."""
    devs = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devs.append(
                {
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": int(dev["default_samplerate"]),
                    "default": idx == sd.default.device[0],
                }
            )
    return devs
