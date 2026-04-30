"""Local speech-to-text via parakeet-mlx (NVIDIA Parakeet on Apple Silicon).

Default model is ``mlx-community/parakeet-tdt-0.6b-v3`` -- a 600M-parameter
Token-and-Duration Transducer that transcribes 25+ European languages with
automatic language detection. Requires MLX, so this code path is Apple Silicon
only.
"""

from __future__ import annotations

import os

# Enable hf-transfer (Rust-based parallel downloader) before huggingface_hub loads.
# Substantially faster on first download; opt out with HF_HUB_ENABLE_HF_TRANSFER=0.
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

import warnings  # noqa: E402
from pathlib import Path  # noqa: E402
from threading import Lock  # noqa: E402

from huggingface_hub import snapshot_download  # noqa: E402

DEFAULT_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"

# Curated list shown in the settings menu.
PARAKEET_MODELS: list[tuple[str, str]] = [
    ("mlx-community/parakeet-tdt-0.6b-v3", "multilingual v3, 25 European langs (recommended)"),
    ("mlx-community/parakeet-tdt-0.6b-v2", "English only, similar size"),
    ("mlx-community/parakeet-rnnt-1.1b", "English only, larger and slightly more accurate"),
]

# Approximate on-disk sizes after download (bfloat16 weights + tokenizer).
PARAKEET_SIZES: dict[str, str] = {
    "mlx-community/parakeet-tdt-0.6b-v3": "~1.2 GB",
    "mlx-community/parakeet-tdt-0.6b-v2": "~1.2 GB",
    "mlx-community/parakeet-rnnt-1.1b": "~2.3 GB",
}


class TranscriptionError(Exception):
    """Base error for STT failures."""


class ModelDownloadError(TranscriptionError):
    """Model weights couldn't be downloaded (no network on first run)."""


_model_cache: dict[str, object] = {}
_cache_lock = Lock()


def _import_parakeet():  # noqa: ANN202 -- runtime guard, return type unused
    """Import parakeet-mlx lazily so non-Apple-Silicon installs fail gracefully."""
    try:
        from parakeet_mlx import from_pretrained  # noqa: PLC0415
    except ImportError as e:
        raise TranscriptionError(
            "parakeet-mlx is not available. Parakeet requires Apple Silicon (MLX). "
            f"Install with `pip install parakeet-mlx`. Underlying error: {e}"
        ) from e
    return from_pretrained


def _load_model(model_name: str):  # noqa: ANN202
    """Lazy-load and cache the Parakeet model."""
    with _cache_lock:
        if model_name not in _model_cache:
            from_pretrained = _import_parakeet()
            try:
                _model_cache[model_name] = from_pretrained(model_name)
            except Exception as e:  # noqa: BLE001
                msg = str(e).lower()
                if "download" in msg or "connection" in msg or "huggingface" in msg or "resolve" in msg:
                    raise ModelDownloadError(
                        f"Could not download Parakeet model '{model_name}': {e}"
                    ) from e
                raise TranscriptionError(
                    f"Could not load Parakeet '{model_name}': {e}"
                ) from e
        return _model_cache[model_name]


def transcribe(wav_path: Path, *, model_name: str, language: str) -> str:
    """Transcribe a WAV file. Returns plain text.

    ``language`` is accepted for API compatibility but Parakeet-TDT v3 detects
    the speaker's language automatically; this argument is currently ignored at
    the STT level (the reformulator still uses it as a hint to Claude/Ollama).
    """
    del language  # Parakeet auto-detects; kept for API parity with prior whisper path.
    model = _load_model(model_name)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            result = model.transcribe(str(wav_path))
    except Exception as e:  # noqa: BLE001
        raise TranscriptionError(f"Transcription failed: {e}") from e

    text = getattr(result, "text", "") or ""
    return text.strip()


def is_model_cached(model_name: str) -> bool:
    """Check if the model has been loaded into memory in this process."""
    with _cache_lock:
        return model_name in _model_cache


def is_model_on_disk(model_name: str) -> bool:
    """Return True if the model weights are already in the HuggingFace cache."""
    try:
        snapshot_download(model_name, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def model_download_size(model_name: str) -> str:
    """Human-readable approximate download size, or empty string if unknown."""
    return PARAKEET_SIZES.get(model_name, "")


def download_model(model_name: str) -> Path:
    """Download model weights from HuggingFace to the local cache. Returns path."""
    try:
        return Path(snapshot_download(model_name))
    except Exception as e:  # noqa: BLE001
        raise ModelDownloadError(
            f"Could not download Parakeet model '{model_name}': {e}"
        ) from e
