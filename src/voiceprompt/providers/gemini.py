"""Google Gemini client. Reformulates a transcribed text into a clean prompt.

Uses the official ``google-genai`` SDK (not the legacy ``google-generativeai``).
The free tier of ``gemini-2.5-flash`` is generous enough for personal voice
dictation: as of this writing, 15 RPM and 1500 RPD. All public errors raised
here are sanitized -- they never include the API key or the raw request body.
"""

from __future__ import annotations

import re
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from voiceprompt.config import Config
from voiceprompt.reformulator import AuthError, ProviderError, QuotaExceededError

# Curated list shown in the settings menu. ``gemini-2.5-flash`` is the closest
# Haiku 4.5 analog: fast, multilingual, free tier covers personal use.
MODELS: list[tuple[str, str]] = [
    ("gemini-2.5-flash", "fast and multilingual (recommended, free tier)"),
    ("gemini-2.5-flash-lite", "even cheaper and faster"),
    ("gemini-2.5-pro", "higher quality, more limited free tier"),
]

DEFAULT_MAX_RETRIES = 3
MAX_RETRY_SLEEP_SECS = 10.0
INITIAL_BACKOFF_SECS = 1.0
MAX_BACKOFF_SECS = 8.0

# Heuristic: Gemini API keys distributed by AI Studio start with "AIza" today.
# We warn (not reject) if the value doesn't match.
GEMINI_KEY_PREFIX = "AIza"

_SECRET_PATTERNS = (
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r'"[Xx]-goog-api-key"\s*:\s*"[^"]+"'),
)


class GeminiError(ProviderError):
    """Base error for Gemini-specific failures."""


def looks_like_gemini_key(value: str) -> bool:
    """Best-effort sanity check for a Gemini / AI Studio API key."""
    v = value.strip()
    return v.startswith(GEMINI_KEY_PREFIX) and len(v) > len(GEMINI_KEY_PREFIX) + 10


def _redact(message: str) -> str:
    out = message
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("***", out)
    return out


def _client(cfg: Config) -> genai.Client:
    if not cfg.gemini_api_key:
        raise AuthError("Gemini API key is not configured.")
    return genai.Client(api_key=cfg.gemini_api_key)


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


def _extract_text(response) -> str:  # noqa: ANN001 -- google-genai response shape
    text = getattr(response, "text", None)
    return text.strip() if text else ""


def _retry_after(err: BaseException) -> float | None:
    response = getattr(err, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _classify(err: BaseException) -> ProviderError:
    """Map a google-genai exception to one of our sanitized provider errors."""
    msg = _redact(str(err))
    code = getattr(err, "code", None) or getattr(err, "status_code", None)
    if code in (401, 403):
        return AuthError(msg)
    if code == 429:
        return QuotaExceededError(msg, retry_after=_retry_after(err))
    return GeminiError(msg)


def reformulate_text(
    transcript: str,
    cfg: Config,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    """Send transcript to Gemini. Returns the reformulated prompt."""
    client = _client(cfg)
    user_text = _user_message(transcript, cfg.language)
    config = genai_types.GenerateContentConfig(
        system_instruction=cfg.system_prompt,
        temperature=cfg.temperature,
        max_output_tokens=cfg.max_output_tokens,
    )

    delay = INITIAL_BACKOFF_SECS
    last_error: BaseException | None = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=cfg.gemini_model,
                contents=user_text,
                config=config,
            )
            text = _extract_text(response)
            if not text:
                raise GeminiError("Gemini returned an empty response.")
            return text

        except genai_errors.ClientError as e:
            last_error = e
            classified = _classify(e)
            if isinstance(classified, AuthError):
                raise classified from e
            if isinstance(classified, QuotaExceededError):
                if attempt == max_retries - 1:
                    raise classified from e
                time.sleep(min(classified.retry_after or delay, MAX_RETRY_SLEEP_SECS))
            else:
                # Other 4xx are not retriable.
                raise classified from e
        except genai_errors.ServerError as e:
            last_error = e
            if attempt == max_retries - 1:
                raise GeminiError(
                    f"Gemini transient server error after retries: {_redact(str(e))}"
                ) from e
            time.sleep(delay)
        except genai_errors.APIError as e:
            # Catch-all for network / unknown SDK errors.
            last_error = e
            if attempt == max_retries - 1:
                raise GeminiError(
                    f"Gemini transient error after retries: {_redact(str(e))}"
                ) from e
            time.sleep(delay)

        delay = min(delay * 2, MAX_BACKOFF_SECS)

    raise GeminiError(_redact(str(last_error)) if last_error else "Unknown Gemini failure.")


def reformulate_text_stream(transcript: str, cfg: Config):
    """Yield incremental text chunks from Gemini."""
    client = _client(cfg)
    user_text = _user_message(transcript, cfg.language)
    config = genai_types.GenerateContentConfig(
        system_instruction=cfg.system_prompt,
        temperature=cfg.temperature,
        max_output_tokens=cfg.max_output_tokens,
    )
    delay = INITIAL_BACKOFF_SECS
    last_error: BaseException | None = None
    for attempt in range(DEFAULT_MAX_RETRIES):
        try:
            for chunk in client.models.generate_content_stream(
                model=cfg.gemini_model,
                contents=user_text,
                config=config,
            ):
                text = getattr(chunk, "text", None)
                if text:
                    yield text
            return
        except genai_errors.ClientError as e:
            last_error = e
            classified = _classify(e)
            if isinstance(classified, AuthError):
                raise classified from e
            if isinstance(classified, QuotaExceededError):
                if attempt == DEFAULT_MAX_RETRIES - 1:
                    raise classified from e
                time.sleep(min(classified.retry_after or delay, MAX_RETRY_SLEEP_SECS))
            else:
                raise classified from e
        except (genai_errors.ServerError, genai_errors.APIError) as e:
            last_error = e
            if attempt == DEFAULT_MAX_RETRIES - 1:
                raise GeminiError(f"Gemini transient error after retries: {_redact(str(e))}") from e
            time.sleep(delay)
        delay = min(delay * 2, MAX_BACKOFF_SECS)
    raise GeminiError(_redact(str(last_error)) if last_error else "Unknown Gemini failure.")


def quick_test(cfg: Config) -> str:
    """Tiny round-trip to verify the API key/model work. Returns Gemini's response."""
    client = _client(cfg)
    try:
        response = client.models.generate_content(
            model=cfg.gemini_model,
            contents="Reply with exactly the word: OK",
            config=genai_types.GenerateContentConfig(max_output_tokens=20),
        )
    except (genai_errors.ClientError, genai_errors.ServerError, genai_errors.APIError) as e:
        raise _classify(e) from e

    return _extract_text(response)
