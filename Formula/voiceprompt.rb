class Voiceprompt < Formula
  include Language::Python::Virtualenv

  desc "Speak. AI refines. Paste. Voice-to-prompt CLI with local Whisper STT"
  homepage "https://github.com/noelcaravaca/voiceprompt-cli"
  url "https://files.pythonhosted.org/packages/source/v/voiceprompt-cli/voiceprompt_cli-0.3.0.tar.gz"
  # Update sha256 after publishing to PyPI:
  #   curl -sL <url> | sha256sum
  sha256 "PLACEHOLDER_UPDATE_AFTER_PYPI_PUBLISH"
  license "MIT"

  bottle :unneeded

  depends_on "python@3.12"
  depends_on "portaudio"  # required by sounddevice

  # To regenerate the resource list after a version bump:
  #   pip install homebrew-pypi-poet && poet voiceprompt-cli
  #
  # Core resources are listed below. faster-whisper and its ML dependencies
  # (ctranslate2, huggingface-hub, etc.) are large and download model weights
  # at first run, so they are installed via pip rather than as static resources.

  def install
    # Create a virtualenv and install the package plus all dependencies.
    # We rely on pip's dependency resolver here rather than listing every
    # transitive resource, which keeps the formula maintainable as deps evolve.
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install buildpath
    bin.install_symlink libexec/"bin/voiceprompt"
  end

  def post_install
    ohai "First run will download the Whisper transcription model (~500 MB)."
    ohai "Run `voiceprompt dictate` once to trigger the download."
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/voiceprompt --version")
  end
end
