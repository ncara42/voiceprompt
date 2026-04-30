"""Anthropic Claude client. Reformulates a transcribed text into a clean prompt.

All public errors raised here are sanitized -- they never include the API key
or the raw request body, only the upstream status/code and a short message.
"""

from __future__ import annotations

import re
import time

import anthropic

from voiceprompt.config import Config
from voiceprompt.reformulator import AuthError, ProviderError, QuotaExceededError

# Curated list shown in the settings menu. Users can pick any other model id by
# editing config.json directly.
MODELS: list[tuple[str, str]] = [
    ("claude-haiku-4-5-20251001", "fast and cheap (recommended)"),
    ("claude-sonnet-4-6", "better quality, balanced"),
    ("claude-opus-4-7", "maximum quality, more expensive"),
]

# How many retries to attempt on transient failures (5xx, connection drops, 429).
DEFAULT_MAX_RETRIES = 3
# Cap the in-loop sleep so a misbehaving server can't stall a recording session.
MAX_RETRY_SLEEP_SECS = 10.0
# Initial backoff between retries; doubles each attempt up to 8s.
INITIAL_BACKOFF_SECS = 1.0
MAX_BACKOFF_SECS = 8.0

# Heuristic: Anthropic API keys currently start with "sk-ant-". We warn (not reject)
# if the value doesn't match -- the prefix may evolve and we don't want to break.
ANTHROPIC_KEY_PREFIX = "sk-ant-"

# Regex to redact anything that looks like a secret from upstream error strings.
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r'"x-api-key"\s*:\s*"[^"]+"'),
)


class ClaudeError(ProviderError):
    """Base error for Claude-specific failures."""


def looks_like_anthropic_key(value: str) -> bool:
    """Best-effort sanity check for an Anthropic API key."""
    v = value.strip()
    return v.startswith(ANTHROPIC_KEY_PREFIX) and len(v) > len(ANTHROPIC_KEY_PREFIX) + 10


def _redact(message: str) -> str:
    """Strip anything resembling an API key/token from an upstream message."""
    out = message
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("***", out)
    return out


def _client(cfg: Config) -> anthropic.Anthropic:
    if not cfg.anthropic_api_key:
        raise AuthError("Anthropic API key is not configured.")
    return anthropic.Anthropic(api_key=cfg.anthropic_api_key)


def _user_message(transcript: str, language_hint: str) -> str:
    if language_hint == "auto":
        return (
            "Rewrite the following transcription into one clean prompt, "
            "keeping the speaker's original language.\n\n"
            f"---\n{transcript}\n---"
        )
    return (
        f"Rewrite the following transcription (language: {language_hint}) into one "
        f"clean prompt.\n\n---\n{transcript}\n---"
    )


def _extract_text(response: anthropic.types.Message) -> str:
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()


def reformulate_text(
    transcript: str,
    cfg: Config,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    """Send transcript to Claude. Returns the reformulated prompt.

    Retries with exponential backoff on transient errors (429/5xx). Raises
    `AuthError`, `QuotaExceededError`, or `ClaudeError` on definitive failure.
    """
    client = _client(cfg)
    user_text = _user_message(transcript, cfg.language)

    delay = INITIAL_BACKOFF_SECS
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=cfg.model,
                max_tokens=cfg.max_output_tokens,
                temperature=cfg.temperature,
                system=cfg.system_prompt,
                messages=[{"role": "user", "content": user_text}],
            )
            text = _extract_text(response)
            if not text:
                raise ClaudeError("Claude returned an empty response.")
            return text

        except anthropic.AuthenticationError as e:
            raise AuthError(_redact(str(e))) from e
        except anthropic.PermissionDeniedError as e:
            raise AuthError(_redact(str(e))) from e
        except anthropic.RateLimitError as e:
            last_error = e
            retry_after = _retry_after_from(e)
            if attempt == max_retries - 1:
                raise QuotaExceededError(_redact(str(e)), retry_after=retry_after) from e
            time.sleep(min(retry_after or delay, MAX_RETRY_SLEEP_SECS))
        except (anthropic.APIConnectionError, anthropic.InternalServerError) as e:
            last_error = e
            if attempt == max_retries - 1:
                raise ClaudeError(
                    f"Claude transient error after retries: {_redact(str(e))}"
                ) from e
            time.sleep(delay)
        except anthropic.APIStatusError as e:
            raise ClaudeError(_redact(str(e))) from e

        delay = min(delay * 2, MAX_BACKOFF_SECS)

    raise ClaudeError(_redact(str(last_error)) if last_error else "Unknown Claude failure.")


def quick_test(cfg: Config) -> str:
    """Tiny round-trip to verify the API key/model work. Returns Claude's response."""
    client = _client(cfg)
    try:
        response = client.messages.create(
            model=cfg.model,
            max_tokens=20,
            messages=[{"role": "user", "content": "Reply with exactly the word: OK"}],
        )
    except anthropic.AuthenticationError as e:
        raise AuthError(_redact(str(e))) from e
    except anthropic.PermissionDeniedError as e:
        raise AuthError(_redact(str(e))) from e
    except anthropic.RateLimitError as e:
        raise QuotaExceededError(_redact(str(e)), retry_after=_retry_after_from(e)) from e
    except anthropic.APIStatusError as e:
        raise ClaudeError(_redact(str(e))) from e

    return _extract_text(response)


def _retry_after_from(err: anthropic.APIStatusError) -> float | None:
    """Extract retry-after from response headers if present."""
    response = getattr(err, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
