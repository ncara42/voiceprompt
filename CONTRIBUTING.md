# Contributing to voiceprompt

Thanks for taking the time. This guide covers the practical bits — environment,
expectations, and the review loop.

## Quick start

```bash
git clone https://github.com/noelcaravaca/voiceprompt-cli.git
cd voiceprompt-cli
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Run the CLI from your checkout with `.venv/bin/voiceprompt …`. Any change to
`src/voiceprompt/` is picked up immediately because the install is editable.

## Project layout

```
src/voiceprompt/
├── cli.py           # Typer entry point
├── config.py        # User config (JSON, OS-appropriate dir)
├── history.py       # Local history (JSONL)
├── reformulator.py  # Provider-agnostic dispatcher
├── audio/           # Microphone capture + speech-to-text
├── providers/       # LLM providers (Claude, Ollama, Gemini, GitHub Models)
├── system/          # OS integration (hotkey, paste, clipboard, proctitle)
└── ui/              # Rich/prompt_toolkit menu + visualizer
```

Tests live in `tests/` and use the standard library `unittest`.

## Development loop

1. Open an issue first if you're planning a non-trivial change. A short note
   ("I'd like to add X because Y, here's the rough plan") avoids both duplicated
   work and abandoned PRs.
2. Branch from `main`. Keep PRs focused: one logical change per PR.
3. Run `ruff check src tests` and the test suite locally before pushing.
4. Reference the issue from the PR body and call out anything reviewers should
   pay attention to (security-sensitive code paths, new dependencies, behaviour
   changes).

## Style

- Python 3.10+, fully type-annotated where reasonable.
- Ruff handles formatting and lint (`pyproject.toml` → `[tool.ruff]`). Keep
  imports sorted by Ruff's `I` rules.
- Module docstrings explain *why* the module exists; comments explain *why*
  non-obvious code is the way it is. Don't restate what the code already says.
- New OS integration code must work on macOS, Linux, *and* Windows or fall back
  cleanly with a user-visible message. Platform-specific code lives under
  `system/`.

## Adding a new LLM provider

1. Create `src/voiceprompt/providers/<name>.py` exposing
   `reformulate_text(transcript, cfg) -> str` and
   `quick_test(cfg) -> str`. Errors should derive from
   `voiceprompt.reformulator.ProviderError` (or `AuthError` /
   `QuotaExceededError`) so the CLI can render them uniformly.
2. Register the provider in `reformulator.PROVIDERS`, `PROVIDER_LABELS`, and
   the dispatch helpers.
3. Surface a config field in `config.Config` (token + model id) and add it to
   the migration / env-var section in `config.load`.
4. Add at least one unit test in `tests/test_<name>.py`.

## Reporting bugs and asking questions

- **Bugs:** open a GitHub issue using the *Bug report* template.
- **Feature ideas:** *Feature request* template — describe the user problem,
  not the solution.
- **Security issues:** see [SECURITY.md](SECURITY.md). Do **not** file public
  issues for credential / injection / exfiltration findings.

## License

By contributing you agree that your contributions are licensed under the
repository's MIT license.
