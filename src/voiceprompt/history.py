"""Local dictation history: a JSONL log of every successful refinement cycle.

Entries live next to ``config.json`` (one JSON object per line). The file is
capped at ``max_entries`` and rotated in place. Nothing is uploaded — the log
is purely a local convenience for replay, audit, and stats.

API keys and provider tokens are NEVER logged. Each entry only contains:
    {
      "ts": "2026-04-30T08:55:12.345678+00:00",   # ISO 8601 UTC
      "transcript": "...",                          # raw STT output
      "prompt":     "...",                          # AI-refined prompt
      "provider":   "claude",
      "model":      "claude-haiku-4-5-20251001",
      "language":   "auto",
      "record_secs": 4.2,
      "refine_secs": 1.1
    }
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from voiceprompt.config import config_dir

HISTORY_FILENAME = "history.jsonl"
DEFAULT_MAX_ENTRIES = 1000

# Rough heuristic for how often to bother rotating: only when the file has
# grown past this size do we count lines and trim. Avg entry is ~250 bytes,
# so 250 KB is roughly ~1k entries.
_ROTATE_THRESHOLD_BYTES = 250_000


@dataclass
class Entry:
    ts: str
    transcript: str
    prompt: str
    provider: str
    model: str
    language: str
    record_secs: float
    refine_secs: float


def history_path() -> Path:
    return config_dir() / HISTORY_FILENAME


def log(
    *,
    transcript: str,
    prompt: str,
    provider: str,
    model: str,
    language: str,
    record_secs: float,
    refine_secs: float,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> None:
    """Append one entry. Silently swallows IO errors so dictation never fails because of logging."""
    try:
        entry = Entry(
            ts=datetime.now(timezone.utc).isoformat(),
            transcript=transcript.strip(),
            prompt=prompt.strip(),
            provider=provider,
            model=model,
            language=language,
            record_secs=round(float(record_secs), 2),
            refine_secs=round(float(refine_secs), 2),
        )
        line = json.dumps(asdict(entry), ensure_ascii=False)
        path = history_path()
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        _maybe_rotate(path, max_entries)
    except OSError:
        return


def _maybe_rotate(path: Path, max_entries: int) -> None:
    """Trim the file to the last ``max_entries`` lines once it grows past the threshold."""
    try:
        if path.stat().st_size < _ROTATE_THRESHOLD_BYTES:
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) <= max_entries:
            return
        keep = lines[-max_entries:]
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")
    except OSError:
        return


def read(limit: int | None = None) -> list[Entry]:
    """Return entries newest-first, capped at ``limit`` if provided."""
    path = history_path()
    if not path.exists():
        return []
    entries: list[Entry] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                try:
                    entries.append(
                        Entry(
                            ts=str(data.get("ts", "")),
                            transcript=str(data.get("transcript", "")),
                            prompt=str(data.get("prompt", "")),
                            provider=str(data.get("provider", "")),
                            model=str(data.get("model", "")),
                            language=str(data.get("language", "")),
                            record_secs=float(data.get("record_secs", 0.0) or 0.0),
                            refine_secs=float(data.get("refine_secs", 0.0) or 0.0),
                        )
                    )
                except (TypeError, ValueError):
                    continue
    except OSError:
        return []

    entries.reverse()
    if limit is not None and limit > 0:
        return entries[:limit]
    return entries


def last() -> Entry | None:
    """Return the most recent entry, or ``None`` if the log is empty."""
    items = read(limit=1)
    return items[0] if items else None


def count() -> int:
    """Return the total number of entries in the log."""
    path = history_path()
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def clear() -> None:
    """Delete the history file. No-op if it doesn't exist."""
    with contextlib.suppress(FileNotFoundError, OSError):
        history_path().unlink()
