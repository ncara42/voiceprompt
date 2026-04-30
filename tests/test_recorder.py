from __future__ import annotations

import unittest
from unittest.mock import patch

from voiceprompt.audio import recorder


class FakeSoundDevice:
    def __init__(
        self,
        *,
        query_error: Exception | None = None,
        default_samplerate: int = 48000,
        check_error: Exception | None = None,
    ) -> None:
        self.query_error = query_error
        self.default_samplerate = default_samplerate
        self.check_error = check_error
        self.checked_rates: list[int] = []

    def query_devices(self, *, kind: str | None = None):
        if kind != "input":
            raise AssertionError(f"unexpected kind: {kind!r}")
        if self.query_error is not None:
            raise self.query_error
        return {"default_samplerate": self.default_samplerate}

    def check_input_settings(self, *, samplerate: int, channels: int, dtype: str) -> None:
        if channels != 1:
            raise AssertionError(f"unexpected channels: {channels!r}")
        if dtype != "int16":
            raise AssertionError(f"unexpected dtype: {dtype!r}")
        self.checked_rates.append(samplerate)
        if self.check_error is not None:
            raise self.check_error


class ResolveSampleRateTests(unittest.TestCase):
    def test_query_devices_default_minus_one_raises_no_input_device_error(self) -> None:
        fake_sd = FakeSoundDevice(query_error=RuntimeError("Error querying device -1"))

        with patch.object(recorder, "sd", fake_sd):
            rec = recorder.Recorder(sample_rate=16000)
            with self.assertRaises(recorder.NoInputDeviceError):
                rec._resolve_sample_rate(16000)

        self.assertEqual(fake_sd.checked_rates, [])

    def test_check_input_settings_default_minus_one_raises_no_input_device_error(self) -> None:
        fake_sd = FakeSoundDevice(check_error=RuntimeError("Error querying device -1"))

        with patch.object(recorder, "sd", fake_sd):
            rec = recorder.Recorder(sample_rate=16000)
            with self.assertRaises(recorder.NoInputDeviceError):
                rec._resolve_sample_rate(16000)

    def test_sample_rate_rejections_keep_technical_runtime_error(self) -> None:
        fake_sd = FakeSoundDevice(check_error=RuntimeError("Invalid sample rate"))

        with patch.object(recorder, "sd", fake_sd):
            rec = recorder.Recorder(sample_rate=16000)
            with self.assertRaises(RuntimeError) as ctx:
                rec._resolve_sample_rate(16000)

        self.assertNotIsInstance(ctx.exception, recorder.NoInputDeviceError)
        self.assertIn("No sample rate accepted by default input device", str(ctx.exception))
        self.assertIn("Invalid sample rate", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
