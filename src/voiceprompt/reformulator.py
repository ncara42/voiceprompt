"""Provider-agnostic dispatcher for text reformulation.

Routes ``reformulate_text`` and ``quick_test`` calls to the active provider
selected by ``Config.provider``. Currently supported: Anthropic Claude, Ollama
Cloud, and Google Gemini. Errors raised by every provider derive from
``ProviderError`` so callers can handle them uniformly.
"""

from __future__ import annotations

from voiceprompt.config import Config


class ProviderError(Exception):
    """Base error for any AI provider failure."""


class AuthError(ProviderError):
    """API key invalid or missing permissions."""


class QuotaExceededError(ProviderError):
    """Rate limit hit. ``retry_after`` is the suggested delay in seconds (if known)."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


PROVIDERS = ("claude", "ollama", "gemini")
DEFAULT_PROVIDER = "claude"

PROVIDER_LABELS = {
    "claude": "Claude (Anthropic)",
    "ollama": "Ollama Cloud",
    "gemini": "Google Gemini",
}


def normalize(provider: str) -> str:
    return provider if provider in PROVIDERS else DEFAULT_PROVIDER


def active_provider(cfg: Config) -> str:
    return normalize(cfg.provider)


def active_model(cfg: Config) -> str:
    p = active_provider(cfg)
    if p == "ollama":
        return cfg.ollama_model
    if p == "gemini":
        return cfg.gemini_model
    return cfg.model


def short_model(cfg: Config) -> str:
    """Compact, user-facing model label for the active provider."""
    p = active_provider(cfg)
    if p == "ollama":
        return cfg.ollama_model
    if p == "gemini":
        return cfg.gemini_model
    return _short_claude(cfg.model)


def _short_claude(model_id: str) -> str:
    """``claude-haiku-4-5-20251001`` -> ``haiku 4.5``; fallback to the raw id."""
    if not model_id.startswith("claude-"):
        return model_id
    parts = model_id.split("-")
    if len(parts) >= 4:
        return f"{parts[1]} {parts[2]}.{parts[3]}"
    return model_id


def reformulate_text(transcript: str, cfg: Config) -> str:
    p = active_provider(cfg)
    if p == "ollama":
        from voiceprompt import ollama as ollama_mod  # noqa: PLC0415

        return ollama_mod.reformulate_text(transcript, cfg)
    if p == "gemini":
        from voiceprompt import gemini as gemini_mod  # noqa: PLC0415

        return gemini_mod.reformulate_text(transcript, cfg)
    from voiceprompt import claude as claude_mod  # noqa: PLC0415

    return claude_mod.reformulate_text(transcript, cfg)


def quick_test(cfg: Config) -> str:
    p = active_provider(cfg)
    if p == "ollama":
        from voiceprompt import ollama as ollama_mod  # noqa: PLC0415

        return ollama_mod.quick_test(cfg)
    if p == "gemini":
        from voiceprompt import gemini as gemini_mod  # noqa: PLC0415

        return gemini_mod.quick_test(cfg)
    from voiceprompt import claude as claude_mod  # noqa: PLC0415

    return claude_mod.quick_test(cfg)
