"""Local speech-to-text via faster-whisper or mlx-whisper.

Two engines are supported:
  - faster-whisper  (CTranslate2): cross-platform, CPU int8 or CUDA float16.
  - mlx-whisper     (Apple MLX):   macOS Apple Silicon only, runs on the Neural
                                   Engine — 4-5× faster than CPU on M-chips.

MLX models are identified by the ``mlx-`` prefix (e.g. ``mlx-large-v3-turbo``).
All other model names are routed through faster-whisper.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

import warnings  # noqa: E402
from pathlib import Path  # noqa: E402
from threading import Lock  # noqa: E402

from huggingface_hub import snapshot_download  # noqa: E402

DEFAULT_MODEL = "distil-large-v3"

# ── faster-whisper models ─────────────────────────────────────────────────────

_FW_MODELS: list[tuple[str, str]] = [
    ("distil-large-v3", "distilled large-v3 — fast, English only"),
    ("large-v3",        "best accuracy, multilingual, slower on CPU"),
    ("medium",          "good balance, multilingual"),
    ("small",           "fast, multilingual, decent accuracy"),
    ("base",            "very fast, multilingual, basic accuracy"),
    ("tiny",            "fastest, multilingual, lowest accuracy"),
]

_FW_HF_REPO: dict[str, str] = {
    "tiny":          "Systran/faster-whisper-tiny",
    "base":          "Systran/faster-whisper-base",
    "small":         "Systran/faster-whisper-small",
    "medium":        "Systran/faster-whisper-medium",
    "large-v3":      "Systran/faster-whisper-large-v3",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
}

_FW_SIZES: dict[str, str] = {
    "tiny":          "~75 MB",
    "base":          "~145 MB",
    "small":         "~480 MB",
    "medium":        "~1.5 GB",
    "large-v3":      "~3.0 GB",
    "distil-large-v3": "~1.5 GB",
}

# ── mlx-whisper models (Apple Silicon only) ───────────────────────────────────

_MLX_HF_REPO: dict[str, str] = {
    "mlx-large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "mlx-large-v3":       "mlx-community/whisper-large-v3-mlx",
    "mlx-small":          "mlx-community/whisper-small-mlx",
}

_MLX_SIZES: dict[str, str] = {
    "mlx-large-v3-turbo": "~810 MB",
    "mlx-large-v3":       "~1.5 GB",
    "mlx-small":          "~250 MB",
}

_MLX_DESCRIPTIONS: dict[str, str] = {
    "mlx-large-v3-turbo": "Apple Silicon · multilingual · fast (recommended)",
    "mlx-large-v3":       "Apple Silicon · multilingual · highest accuracy",
    "mlx-small":          "Apple Silicon · multilingual · very fast, lighter",
}

# ── Combined public lists ─────────────────────────────────────────────────────

def _build_models_list() -> list[tuple[str, str]]:
    models = list(_FW_MODELS)
    if sys.platform == "darwin":
        mlx_entries = [(k, v) for k, v in _MLX_DESCRIPTIONS.items()]
        # Insert MLX models at the top so they're the first choice on macOS
        models = mlx_entries + models
    return models


MODELS: list[tuple[str, str]] = _build_models_list()

ENGLISH_ONLY_MODELS: frozenset[str] = frozenset({"distil-large-v3"})

MODEL_SIZES: dict[str, str] = {**_FW_SIZES, **_MLX_SIZES}


def is_english_only(model_name: str) -> bool:
    return model_name in ENGLISH_ONLY_MODELS


def is_mlx_model(model_name: str) -> bool:
    return model_name in _MLX_HF_REPO


VALID_MODELS: tuple[str, ...] = tuple(name for name, _ in MODELS)

# ── Errors ────────────────────────────────────────────────────────────────────

class TranscriptionError(Exception):
    """Base error for STT failures."""


class ModelDownloadError(TranscriptionError):
    """Model weights couldn't be downloaded (no network on first run)."""

# ── faster-whisper engine ─────────────────────────────────────────────────────

_fw_model_cache: dict[str, object] = {}
_fw_cache_lock = Lock()


def _import_faster_whisper():  # noqa: ANN202
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
    except ImportError as e:
        raise TranscriptionError(
            f"faster-whisper is not installed. Install with `pip install faster-whisper`. Error: {e}"
        ) from e
    return WhisperModel


def _select_compute() -> tuple[str, str]:
    try:
        import ctranslate2  # noqa: PLC0415
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:  # noqa: BLE001
        pass
    return "cpu", "int8"


def _load_fw_model(model_name: str):  # noqa: ANN202
    with _fw_cache_lock:
        if model_name not in _fw_model_cache:
            WhisperModel = _import_faster_whisper()
            device, compute_type = _select_compute()
            try:
                _fw_model_cache[model_name] = WhisperModel(
                    model_name, device=device, compute_type=compute_type,
                )
            except Exception as e:  # noqa: BLE001
                msg = str(e).lower()
                if any(t in msg for t in ("download", "connection", "huggingface", "resolve", "network")):
                    raise ModelDownloadError(f"Could not download Whisper model '{model_name}': {e}") from e
                raise TranscriptionError(f"Could not load Whisper '{model_name}': {e}") from e
        return _fw_model_cache[model_name]


def _transcribe_fw(wav_path: Path, *, model_name: str, language: str) -> str:
    model = _load_fw_model(model_name)
    lang_hint = None if language in ("auto", "", None) else language
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
            return " ".join(seg.text for seg in segments).strip()
    except Exception as e:  # noqa: BLE001
        raise TranscriptionError(f"Transcription failed: {e}") from e

# ── mlx-whisper engine ────────────────────────────────────────────────────────

def _transcribe_mlx(wav_path: Path, *, model_name: str, language: str) -> str:
    import contextlib  # noqa: PLC0415
    import io  # noqa: PLC0415

    try:
        import mlx_whisper  # noqa: PLC0415
    except ImportError as e:
        raise TranscriptionError(
            "mlx-whisper is not installed. Run: pip install mlx-whisper"
        ) from e

    hf_repo = _MLX_HF_REPO.get(model_name, model_name)
    lang_hint = None if language in ("auto", "", None) else language

    try:
        # mlx_whisper prints tqdm bars to stderr; suppress them.
        with contextlib.redirect_stderr(io.StringIO()):
            result = mlx_whisper.transcribe(
                str(wav_path),
                path_or_hf_repo=hf_repo,
                language=lang_hint,
                verbose=False,
            )
    except Exception as e:  # noqa: BLE001
        raise TranscriptionError(f"MLX transcription failed: {e}") from e

    return (result.get("text") or "").strip()

# ── Public API ────────────────────────────────────────────────────────────────

def transcribe(wav_path: Path, *, model_name: str, language: str) -> str:
    """Transcribe a WAV file. Routes to mlx-whisper or faster-whisper based on model name."""
    if is_mlx_model(model_name):
        if sys.platform != "darwin":
            raise TranscriptionError(
                f"Model '{model_name}' requires Apple Silicon (macOS). "
                "Change the transcription model in Settings → Transcription → Model."
            )
        return _transcribe_mlx(wav_path, model_name=model_name, language=language)
    return _transcribe_fw(wav_path, model_name=model_name, language=language)


def is_model_cached(model_name: str) -> bool:
    """True if the model is loaded in memory in this process."""
    with _fw_cache_lock:
        return model_name in _fw_model_cache


def is_model_on_disk(model_name: str) -> bool:
    """True if model weights are already in the HuggingFace cache."""
    if is_mlx_model(model_name):
        if sys.platform != "darwin":
            return False
        repo = _MLX_HF_REPO.get(model_name)
    else:
        repo = _FW_HF_REPO.get(model_name)
    if not repo:
        return False
    try:
        snapshot_download(repo, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def model_download_size(model_name: str) -> str:
    return MODEL_SIZES.get(model_name, "")


def download_model(model_name: str) -> Path:
    """Download model weights from HuggingFace. Returns local path."""
    if is_mlx_model(model_name):
        repo = _MLX_HF_REPO.get(model_name)
    else:
        repo = _FW_HF_REPO.get(model_name)
    if not repo:
        raise ModelDownloadError(
            f"Unknown model '{model_name}'. Valid options: {', '.join(VALID_MODELS)}."
        )
    try:
        return Path(snapshot_download(repo))
    except Exception as e:  # noqa: BLE001
        raise ModelDownloadError(f"Could not download model '{model_name}': {e}") from e
