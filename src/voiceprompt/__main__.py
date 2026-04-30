"""Allow `python -m voiceprompt` to launch the CLI."""

from voiceprompt.system import proctitle

proctitle.apply()

from voiceprompt.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
