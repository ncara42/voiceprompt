"""Cross-platform configuration: load/save JSON in the OS's user-config dir."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from platformdirs import user_config_path

APP_NAME = "voiceprompt"

DEFAULT_SYSTEM_PROMPT = (
    "You rewrite dictated voice transcripts into clean prompts for coding assistants "
    "like Claude Code. The transcript may contain filler words, repetitions, or "
    "ambiguous phrasing. Return ONE clear, direct, well-structured prompt in the "
    "same language as the user, ready to send to a coding assistant. Return ONLY "
    "the final prompt — no preamble, no explanations, no meta-commentary."
)
LEGACY_DEFAULT_SYSTEM_PROMPT_SHA256 = (
    "5717dd3d149bd5f982549a476bb4b9319da7fa80bc3e6c3bdebe02bcb06c6d50"
)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OLLAMA_MODEL = "gpt-oss:120b"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GITHUB_MODELS_MODEL = "openai/gpt-4o-mini"
DEFAULT_PROVIDER = "claude"
DEFAULT_TRANSCRIPTION_MODEL = "distil-large-v3"

VALID_PROVIDERS = ("claude", "ollama", "gemini", "github_models")


@dataclass
class Config:
    anthropic_api_key: str = ""
    ollama_api_key: str = ""
    gemini_api_key: str = ""
    github_models_token: str = ""
    provider: str = DEFAULT_PROVIDER  # 'claude' | 'ollama' | 'gemini' | 'github_models'
    model: str = DEFAULT_MODEL
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    gemini_model: str = DEFAULT_GEMINI_MODEL
    github_models_model: str = DEFAULT_GITHUB_MODELS_MODEL
    transcription_model: str = DEFAULT_TRANSCRIPTION_MODEL
    language: str = "auto"  # 'auto' | 'es' | 'en' | ...
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    temperature: float = 0.3
    max_output_tokens: int = 2048
    sample_rate: int = 16000
    auto_copy_clipboard: bool = True
    hotkey: str = "ctrl+space"
    history_enabled: bool = True
    history_max_entries: int = 1000

    @property
    def is_configured(self) -> bool:
        if self.provider == "ollama":
            return bool(self.ollama_api_key.strip())
        if self.provider == "gemini":
            return bool(self.gemini_api_key.strip())
        if self.provider == "github_models":
            return bool(self.github_models_token.strip())
        return bool(self.anthropic_api_key.strip())

    @property
    def active_api_key(self) -> str:
        if self.provider == "ollama":
            return self.ollama_api_key.strip()
        if self.provider == "gemini":
            return self.gemini_api_key.strip()
        if self.provider == "github_models":
            return self.github_models_token.strip()
        return self.anthropic_api_key.strip()


def config_dir() -> Path:
    """Return the OS-appropriate config directory, creating it if needed."""
    p = user_config_path(APP_NAME, appauthor=False, ensure_exists=True)
    return Path(p)


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> Config:
    """Load config from disk, falling back to env var ANTHROPIC_API_KEY for the key."""
    path = config_path()
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}

    # Migrate from pre-0.2 (Gemini) configs: drop incompatible model id.
    if isinstance(data.get("model"), str) and not data["model"].startswith("claude"):
        data.pop("model", None)

    # Migrate from pre-Whisper configs that stored a Parakeet model id
    # ("mlx-community/parakeet-..."). Drop it so the new Whisper default kicks
    # in -- Parakeet model ids don't map to a faster-whisper variant.
    legacy_model = data.get("transcription_model")
    if isinstance(legacy_model, str) and (
        legacy_model.startswith("mlx-community/")
        or "parakeet" in legacy_model.lower()
    ):
        data.pop("transcription_model", None)
    # Also clear the older key if a very old config still has it.
    if "whisper_model" in data and "transcription_model" not in data:
        data.pop("whisper_model", None)

    # Migrate the previous Spanish default prompt to the new English default.
    # User-customized prompts are preserved.
    system_prompt = data.get("system_prompt")
    if (
        isinstance(system_prompt, str)
        and hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
        == LEGACY_DEFAULT_SYSTEM_PROMPT_SHA256
    ):
        data["system_prompt"] = DEFAULT_SYSTEM_PROMPT

    # Allow env var overrides / first-run convenience for both providers.
    env_anthropic = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env_anthropic and not data.get("anthropic_api_key"):
        data["anthropic_api_key"] = env_anthropic

    env_ollama = os.environ.get("OLLAMA_API_KEY", "").strip()
    if env_ollama and not data.get("ollama_api_key"):
        data["ollama_api_key"] = env_ollama

    env_gemini = (
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
    )
    if env_gemini and not data.get("gemini_api_key"):
        data["gemini_api_key"] = env_gemini

    env_github_models = (
        os.environ.get("GITHUB_MODELS_TOKEN", "").strip()
        or os.environ.get("GITHUB_TOKEN", "").strip()
    )
    if env_github_models and not data.get("github_models_token"):
        data["github_models_token"] = env_github_models

    # Drop any unknown provider value so we always boot to a valid one.
    if data.get("provider") not in VALID_PROVIDERS:
        data.pop("provider", None)

    cfg = Config()
    for k, v in data.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def save(cfg: Config) -> Path:
    """Persist config as JSON atomically with 0600 permissions.

    Writes to a sibling tmpfile created with mode 0o600 (so the key never sits
    on disk world-readable, not even momentarily) and then ``os.replace``s it
    over the real path -- atomic on POSIX, near-atomic on Windows.
    """
    path = config_path()
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(asdict(cfg), indent=2, ensure_ascii=False)

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(tmp), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        # On POSIX the open(0o600) already enforces this; on systems where the
        # mode bit was ignored, a chmod attempt is a defensive best-effort.
        with contextlib.suppress(OSError, NotImplementedError):
            os.chmod(str(tmp), 0o600)
        os.replace(str(tmp), str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(str(tmp))
        raise
    return path
