"""Local speech-to-text via faster-whisper.

Cross-platform speech recognition that runs offline on CPU or GPU. Works on
macOS (Intel + Apple Silicon), Linux, and Windows without per-OS code paths.

Engine: ``faster-whisper`` (CTranslate2 reimplementation of Whisper). About
4x faster than ``openai-whisper`` and uses ~50% less memory. Models are
downloaded on demand from Hugging Face on first use.

Default model: ``distil-large-v3`` — distilled Whisper-large-v3, ~95% of
parent quality at roughly 2x the speed and half the size. Best speed/quality
tradeoff for CPU inference, which is what most users have.

Compute precision is selected automatically:
  - CUDA available → ``float16`` (best speed on NVIDIA GPUs)
  - everywhere else → ``int8`` (fastest CPU inference; minimal quality loss)
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

DEFAULT_MODEL = "distil-large-v3"

# Curated list shown in the settings menu. The values are the short names that
# faster-whisper accepts directly (it resolves them to the right HF repo).
MODELS: list[tuple[str, str]] = [
    ("distil-large-v3", "distilled large-v3 — best speed/quality balance (recommended)"),
    ("large-v3", "best accuracy, slower on CPU"),
    ("medium", "good balance, smaller than large"),
    ("small", "fast, decent accuracy"),
    ("base", "very fast, basic accuracy"),
    ("tiny", "fastest, lowest accuracy"),
]

# Approximate on-disk sizes (CTranslate2 int8 quantized weights + tokenizer).
MODEL_SIZES: dict[str, str] = {
    "tiny": "~75 MB",
    "base": "~145 MB",
    "small": "~480 MB",
    "medium": "~1.5 GB",
    "large-v3": "~3.0 GB",
    "distil-large-v3": "~1.5 GB",
}

# Hugging Face repo ids used to check on-disk presence without loading the model.
# faster-whisper resolves the same names internally; we keep this map only for
# the cache-presence check.
_HF_REPO: dict[str, str] = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
}

VALID_MODELS: tuple[str, ...] = tuple(name for name, _ in MODELS)


class TranscriptionError(Exception):
    """Base error for STT failures."""


class ModelDownloadError(TranscriptionError):
    """Model weights couldn't be downloaded (no network on first run)."""


_model_cache: dict[str, object] = {}
_cache_lock = Lock()


def _import_whisper():  # noqa: ANN202
    """Import faster-whisper lazily so the package can be inspected without it."""
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
    except ImportError as e:
        raise TranscriptionError(
            "faster-whisper is not installed. "
            f"Install with `pip install faster-whisper`. Underlying error: {e}"
        ) from e
    return WhisperModel


def _select_compute() -> tuple[str, str]:
    """Pick (device, compute_type) for the current host.

    Prefers CUDA float16 when available; otherwise falls back to CPU int8 which
    is the fastest CTranslate2 path on commodity CPUs and Apple Silicon.
    """
    try:
        import ctranslate2  # noqa: PLC0415

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:  # noqa: BLE001
        pass
    return "cpu", "int8"


def _load_model(model_name: str):  # noqa: ANN202
    """Lazy-load and cache the WhisperModel."""
    with _cache_lock:
        if model_name not in _model_cache:
            WhisperModel = _import_whisper()
            device, compute_type = _select_compute()
            try:
                _model_cache[model_name] = WhisperModel(
                    model_name, device=device, compute_type=compute_type,
                )
            except Exception as e:  # noqa: BLE001
                msg = str(e).lower()
                if any(t in msg for t in ("download", "connection", "huggingface", "resolve", "network")):
                    raise ModelDownloadError(
                        f"Could not download Whisper model '{model_name}': {e}"
                    ) from e
                raise TranscriptionError(
                    f"Could not load Whisper '{model_name}': {e}"
                ) from e
        return _model_cache[model_name]


def transcribe(wav_path: Path, *, model_name: str, language: str) -> str:
    """Transcribe a WAV file. Returns plain text.

    ``language`` of ``"auto"`` triggers Whisper's built-in language detection.
    Any other value (e.g. ``"es"``, ``"en"``) is passed as a hint, which is
    faster and more accurate than auto-detection when the language is known.
    """
    model = _load_model(model_name)
    lang_hint = None if language in ("auto", "", None) else language

    # distil-* models require condition_on_previous_text=False per the official
    # distil-whisper guidance — they were trained with that flag off.
    cond_prev = not model_name.startswith("distil-")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            segments, _info = model.transcribe(  # type: ignore[attr-defined]
                str(wav_path),
                language=lang_hint,
                condition_on_previous_text=cond_prev,
                vad_filter=True,
            )
            text = " ".join(seg.text for seg in segments).strip()
    except Exception as e:  # noqa: BLE001
        raise TranscriptionError(f"Transcription failed: {e}") from e

    return text


def is_model_cached(model_name: str) -> bool:
    """Check if the model has been loaded into memory in this process."""
    with _cache_lock:
        return model_name in _model_cache


def is_model_on_disk(model_name: str) -> bool:
    """Return True if the model weights are already in the HuggingFace cache."""
    repo = _HF_REPO.get(model_name)
    if not repo:
        return False
    try:
        snapshot_download(repo, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def model_download_size(model_name: str) -> str:
    """Human-readable approximate download size, or empty string if unknown."""
    return MODEL_SIZES.get(model_name, "")


def download_model(model_name: str) -> Path:
    """Download model weights from HuggingFace to the local cache. Returns path."""
    repo = _HF_REPO.get(model_name)
    if not repo:
        raise ModelDownloadError(
            f"Unknown Whisper model id '{model_name}'. "
            f"Valid options: {', '.join(VALID_MODELS)}."
        )
    try:
        return Path(snapshot_download(repo))
    except Exception as e:  # noqa: BLE001
        raise ModelDownloadError(
            f"Could not download Whisper model '{model_name}': {e}"
        ) from e
