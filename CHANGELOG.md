# Changelog

All notable changes to voiceprompt are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Subpackage layout: `audio/` (recorder, transcriber), `providers/` (Claude,
  Ollama, Gemini, GitHub Models), `system/` (hotkey, inject, clipboard,
  proctitle), `ui/` (menu, viz, styles, select). Top-level entry points
  (`cli`, `config`, `reformulator`, `history`) are unchanged.
- `CHANGELOG.md`, `CONTRIBUTING.md`, GitHub issue and pull-request templates,
  Dependabot configuration.

### Changed
- **Cross-platform local STT.** Replaced `parakeet-mlx` (Apple Silicon only)
  with `faster-whisper`, which runs on macOS (Intel + Apple Silicon), Linux,
  and Windows from a single code path. Default model is `distil-large-v3`
  (~95 % of `large-v3` quality at roughly 2× the speed). Compute precision is
  selected automatically: CUDA `float16` when an NVIDIA GPU is present,
  otherwise CPU `int8`.
- Configs that still reference a Parakeet model id (`mlx-community/parakeet-*`)
  are migrated to the new default on load.

### Removed
- `parakeet-mlx` dependency and the Apple-Silicon-only platform marker in
  `pyproject.toml`.

## [0.2.0] — 2026-04

### Added
- Background daemon: `voiceprompt start`, `voiceprompt stop`,
  `voiceprompt status`.
- Local history (`history`, `replay`) stored as JSONL.
- GitHub Models provider.

## [0.1.0] — 2026-03

### Added
- Initial release: global hotkey, local Parakeet STT, Claude / Ollama / Gemini
  reformulation, AppleScript / xdotool / SendInput paste injection.
