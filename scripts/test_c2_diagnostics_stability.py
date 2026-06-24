#!/usr/bin/env python3
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout


def load_module():
    script_path = Path(__file__).with_name("c2_diagnostics_stability.py")
    spec = importlib.util.spec_from_file_location("c2_diagnostics_stability", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeKeyValue:
    def __init__(self, key, value):
        self.key = key
        self.value = value


class FakeStatus:
    def __init__(self, values, *, level=0):
        self.level = level
        self.message = "running"
        self.name = "tg0_multipad/raw_stream"
        self.values = [FakeKeyValue(key, value) for key, value in values.items()]


class FakeDiagnosticArray:
    def __init__(self, statuses):
        self.status = statuses


class C2DiagnosticsStabilityTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_passes_when_stream_is_open_and_error_growth_is_bounded(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 250,
                    "frame_rate_hz": 1000.0,
                    "bytes_per_sec": 10000.0,
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": 5,
                    "resync_count": 2,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 150,
                    "frame_rate_hz": 1000.0,
                    "bytes_per_sec": 10000.0,
                    "total_frames": 100110,
                    "sample_count": 100110,
                    "total_bytes": 1001100,
                    "crc_errors": 8,
                    "resync_count": 3,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertTrue(result["pass"], result)
        self.assertEqual(result["delta"]["total_frames"], 100010)
        self.assertEqual(result["delta"]["crc_errors"], 3)
        self.assertEqual(result["delta"]["resync_count"], 1)
        self.assertEqual(result["thresholds"]["min_frame_delta"], 100000)
        self.assertEqual(result["thresholds"]["max_crc_delta"], 10)
        self.assertEqual(result["thresholds"]["max_resync_delta"], 10)
        self.assertEqual(result["thresholds"]["min_diagnostic_samples"], 2)

    def test_fails_when_last_frame_age_is_missing(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("missing_required_fields", result["failures"])
        self.assertIn("last_frame_age_ms", result["missing_required_keys"])

    def test_fails_when_last_frame_age_is_malformed(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": "unknown",
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 100,
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("last_frame_age_ms", result["invalid_numeric_fields"])

    def test_fails_when_rate_fields_are_missing(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 10,
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 10,
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("missing_required_fields", result["failures"])
        self.assertIn("bytes_per_sec", result["missing_required_keys"])
        self.assertIn("frame_rate_hz", result["missing_required_keys"])

    def test_fails_when_rate_fields_are_malformed(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 10,
                    "frame_rate_hz": "not-a-rate",
                    "bytes_per_sec": 10000.0,
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 10,
                    "frame_rate_hz": 1000.0,
                    "bytes_per_sec": "also-not-a-rate",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("bytes_per_sec", result["invalid_numeric_fields"])
        self.assertIn("frame_rate_hz", result["invalid_numeric_fields"])

    def test_fails_when_numeric_fields_are_empty(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": "",
                    "frame_rate_hz": "",
                    "bytes_per_sec": 10000.0,
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": "",
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 10,
                    "frame_rate_hz": 1000.0,
                    "bytes_per_sec": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("bytes_per_sec", result["invalid_numeric_fields"])
        self.assertIn("crc_errors", result["invalid_numeric_fields"])
        self.assertIn("frame_rate_hz", result["invalid_numeric_fields"])
        self.assertIn("last_frame_age_ms", result["invalid_numeric_fields"])

    def test_fails_when_numeric_fields_are_negative(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": "-1",
                    "frame_rate_hz": "-1.0",
                    "bytes_per_sec": 10000.0,
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": "-1",
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 10,
                    "frame_rate_hz": 1000.0,
                    "bytes_per_sec": "-10.0",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("bytes_per_sec", result["invalid_numeric_fields"])
        self.assertIn("crc_errors", result["invalid_numeric_fields"])
        self.assertIn("frame_rate_hz", result["invalid_numeric_fields"])
        self.assertIn("last_frame_age_ms", result["invalid_numeric_fields"])

    def test_fails_when_crc_growth_exceeds_limit(self):
        result = self.module.evaluate_stability(
            [
                {
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 50,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("crc_errors_delta", result["failures"])

    def test_fails_when_raw_stream_does_not_advance(self):
        result = self.module.evaluate_stability(
            [
                {
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 10,
                    "sample_count": 10,
                    "total_bytes": 100,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 20,
                    "sample_count": 20,
                    "total_bytes": 200,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("total_frames_delta", result["failures"])

    def test_fails_when_sample_count_delta_does_not_match_frame_delta(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 200100,
                    "sample_count": 200000,
                    "total_bytes": 2001000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("sample_count_consistency", result["failures"])

    def test_fails_when_byte_delta_is_too_small_for_frame_delta(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 200100,
                    "sample_count": 200100,
                    "total_bytes": 1001,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("total_bytes_consistency", result["failures"])

    def test_clamps_zero_min_frame_delta_to_require_frame_progress(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 10,
                    "sample_count": 10,
                    "total_bytes": 100,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 10,
                    "sample_count": 10,
                    "total_bytes": 2000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=0,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertEqual(result["thresholds"]["min_frame_delta"], 1)
        self.assertIn("total_frames_delta", result["failures"])
        self.assertIn("sample_count_delta", result["failures"])

    def test_fails_when_diagnostics_level_is_not_ok(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 1,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("diagnostic_level", result["failures"])

    def test_fails_when_any_diagnostic_sample_is_not_ok(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 1,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 100000,
                    "sample_count": 100000,
                    "total_bytes": 1000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertEqual(result["max_level"], 1)
        self.assertIn("diagnostic_level", result["failures"])

    def test_fails_when_diagnostic_level_is_missing(self):
        result = self.module.evaluate_stability(
            [
                {
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertEqual(result["missing_level_count"], 2)
        self.assertIn("diagnostic_level_missing", result["failures"])

    def test_fails_when_required_diagnostic_fields_are_missing(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("missing_required_fields", result["failures"])
        self.assertIn("last_error_text", result["missing_required_keys"])
        self.assertIn("crc_errors", result["missing_required_keys"])

    def test_fails_with_structured_result_when_numeric_fields_are_malformed(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "total_frames": "not-a-number",
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("total_frames", result["invalid_numeric_fields"])

    def test_reports_missing_fields_when_numeric_parse_also_fails(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 10,
                    "frame_rate_hz": "bad-rate",
                    "bytes_per_sec": 10000.0,
                    "total_frames": 100,
                    "sample_count": 100,
                    "total_bytes": 1000,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "last_error_text": "",
                    "last_frame_age_ms": 10,
                    "frame_rate_hz": 1000.0,
                    "bytes_per_sec": 10000.0,
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("missing_required_fields", result["failures"])
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("crc_errors", result["missing_required_keys"])
        self.assertIn("frame_rate_hz", result["invalid_numeric_fields"])

    def test_fails_when_any_sample_reports_serial_closed(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "false",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 100000,
                    "sample_count": 100000,
                    "total_bytes": 1000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertEqual(result["serial_closed_count"], 1)
        self.assertIn("serial_open", result["failures"])

    def test_fails_when_any_sample_reports_error_text(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "temporary serial read failed",
                    "total_frames": 100000,
                    "sample_count": 100000,
                    "total_bytes": 1000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertFalse(result["pass"], result)
        self.assertEqual(result["error_text_count"], 1)
        self.assertIn("last_error_text", result["failures"])

    def test_fails_when_runtime_counters_decrease_mid_run(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 100000,
                    "sample_count": 100000,
                    "total_bytes": 1000000,
                    "crc_errors": 10,
                    "resync_count": 5,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 50000,
                    "sample_count": 50000,
                    "total_bytes": 500000,
                    "crc_errors": 2,
                    "resync_count": 1,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 300000,
                    "sample_count": 300000,
                    "total_bytes": 3000000,
                    "crc_errors": 12,
                    "resync_count": 6,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=100,
            max_resync_delta=100,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("counter_monotonic", result["failures"])
        self.assertIn("total_frames", result["counter_decrease_keys"])
        self.assertIn("sample_count", result["counter_decrease_keys"])
        self.assertIn("total_bytes", result["counter_decrease_keys"])
        self.assertIn("crc_errors", result["counter_decrease_keys"])
        self.assertIn("resync_count", result["counter_decrease_keys"])

    def test_fails_when_diagnostic_sample_count_is_too_low(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
            min_diagnostic_samples=3,
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("diagnostic_sample_count", result["failures"])

    def test_default_min_diagnostic_samples_scales_with_duration(self):
        self.assertEqual(
            self.module.default_min_diagnostic_samples(duration_sec=600.0, configured=None),
            480,
        )
        self.assertEqual(
            self.module.default_min_diagnostic_samples(duration_sec=5.0, configured=None),
            4,
        )
        self.assertEqual(
            self.module.default_min_diagnostic_samples(duration_sec=1.0, configured=None),
            2,
        )
        self.assertEqual(
            self.module.default_min_diagnostic_samples(duration_sec=600.0, configured=500),
            500,
        )

    def test_default_min_diagnostic_samples_clamps_invalid_configured_values(self):
        self.assertEqual(
            self.module.default_min_diagnostic_samples(duration_sec=600.0, configured=0),
            2,
        )
        self.assertEqual(
            self.module.default_min_diagnostic_samples(duration_sec=600.0, configured=-5),
            2,
        )

    def test_fails_when_publish_raw_state_does_not_match_expectation(self):
        result = self.module.evaluate_stability(
            [
                {
                    "input_mode": "serial",
                    "input_path": "/dev/ttyUSB0",
                    "serial_open": "true",
                    "publish_raw": "true",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "input_mode": "serial",
                    "input_path": "/dev/ttyUSB0",
                    "serial_open": "true",
                    "publish_raw": "true",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
            expect_publish_raw="false",
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("publish_raw", result["failures"])

    def test_fails_when_expected_fields_change_mid_run(self):
        result = self.module.evaluate_stability(
            [
                {
                    "level": 0,
                    "input_mode": "file",
                    "input_path": "/tmp/input.bin",
                    "serial_open": "true",
                    "publish_raw": "true",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "level": 0,
                    "input_mode": "serial",
                    "input_path": "/dev/ttyUSB0",
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
            expect_input_mode="serial",
            expect_input_path="/dev/ttyUSB0",
            expect_publish_raw="false",
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("input_mode", result["failures"])
        self.assertIn("input_path", result["failures"])
        self.assertIn("publish_raw", result["failures"])

    def test_fails_when_input_source_does_not_match_expectation(self):
        result = self.module.evaluate_stability(
            [
                {
                    "input_mode": "idle",
                    "input_path": "",
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 0,
                    "sample_count": 0,
                    "total_bytes": 0,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
                {
                    "input_mode": "idle",
                    "input_path": "",
                    "serial_open": "true",
                    "publish_raw": "false",
                    "last_error_text": "",
                    "total_frames": 200000,
                    "sample_count": 200000,
                    "total_bytes": 2000000,
                    "crc_errors": 0,
                    "resync_count": 0,
                },
            ],
            min_frame_delta=100000,
            max_crc_delta=10,
            max_resync_delta=10,
            expect_input_mode="serial",
            expect_input_path="/dev/ttyUSB0",
            expect_publish_raw="false",
        )

        self.assertFalse(result["pass"], result)
        self.assertIn("input_mode", result["failures"])
        self.assertIn("input_path", result["failures"])

    def test_sample_matching_filters_unexpected_input_source(self):
        expected = {
            "input_mode": "serial",
            "input_path": "/dev/ttyUSB0",
        }
        unexpected = {
            "input_mode": "idle",
            "input_path": "",
        }

        self.assertTrue(
            self.module._sample_matches_expected(
                expected,
                expect_input_mode="serial",
                expect_input_path="/dev/ttyUSB0",
            )
        )
        self.assertFalse(
            self.module._sample_matches_expected(
                unexpected,
                expect_input_mode="serial",
                expect_input_path="/dev/ttyUSB0",
            )
        )

    def test_partition_samples_reports_filtered_context(self):
        expected = {
            "input_mode": "serial",
            "input_path": "/dev/ttyUSB0",
        }
        unexpected = {
            "input_mode": "idle",
            "input_path": "",
        }

        partitioned = self.module._partition_samples_by_expected_source(
            [unexpected, expected],
            expect_input_mode="serial",
            expect_input_path="/dev/ttyUSB0",
        )

        self.assertEqual(partitioned["samples"], [expected])
        self.assertEqual(partitioned["filtered_sample_count"], 1)
        self.assertEqual(partitioned["last_filtered_sample"], unexpected)

    def test_fail_on_filtered_samples_marks_result_failed(self):
        result = {"pass": True, "failures": []}

        self.module.apply_filtered_sample_policy(
            result,
            filtered_sample_count=1,
            fail_on_filtered_samples=True,
        )

        self.assertFalse(result["pass"])
        self.assertIn("filtered_diagnostics_source", result["failures"])

    def test_write_result_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "result.json"

            with redirect_stdout(io.StringIO()):
                self.module.write_result({"pass": True}, str(output_path))

            self.assertTrue(output_path.exists())

    def test_write_result_emits_strict_json_for_non_finite_floats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "result.json"
            result = {
                "pass": False,
                "first_diag": {"frame_rate_hz": math.nan},
                "last_diag": {"bytes_per_sec": math.inf},
                "failures": ["numeric_parse"],
            }

            with redirect_stdout(io.StringIO()) as stdout:
                self.module.write_result(result, str(output_path))

            text = output_path.read_text(encoding="utf-8")
            console_json = stdout.getvalue().split("=", 1)[1]

            def reject_constant(value):
                raise ValueError(value)

            parsed_file = json.loads(text, parse_constant=reject_constant)
            parsed_console = json.loads(console_json, parse_constant=reject_constant)
            self.assertEqual(parsed_file["first_diag"]["frame_rate_hz"], "nan")
            self.assertEqual(parsed_file["last_diag"]["bytes_per_sec"], "inf")
            self.assertEqual(parsed_console["first_diag"]["frame_rate_hz"], "nan")
            self.assertEqual(parsed_console["last_diag"]["bytes_per_sec"], "inf")

    def test_sample_from_status_preserves_publish_raw_state(self):
        status = FakeStatus(
            {
                "input_mode": "serial",
                "input_path": "/dev/ttyUSB0",
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "10",
                "crc_errors": "0",
                "resync_count": "0",
                "sample_count": "10",
                "total_bytes": "100",
                "frame_rate_hz": "10.0",
                "bytes_per_sec": "100.0",
                "last_frame_age_ms": "42",
                "last_error_text": "",
            }
        )

        sample = self.module._sample_from_status(status)

        self.assertEqual(sample["input_mode"], "serial")
        self.assertEqual(sample["input_path"], "/dev/ttyUSB0")
        self.assertEqual(sample["publish_raw"], "false")
        self.assertEqual(sample["last_frame_age_ms"], 42)

    def test_sample_from_status_does_not_synthesize_missing_diagnostics_keys(self):
        status = FakeStatus(
            {
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "10",
                "resync_count": "0",
                "sample_count": "10",
                "total_bytes": "100",
                "last_error_text": "",
            }
        )

        sample = self.module._sample_from_status(status)

        self.assertNotIn("crc_errors", sample)

    def test_sample_from_status_preserves_malformed_numeric_for_structured_failure(self):
        status = FakeStatus(
            {
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "not-a-number",
                "crc_errors": "0",
                "resync_count": "0",
                "sample_count": "10",
                "total_bytes": "100",
                "last_error_text": "",
            }
        )

        sample = self.module._sample_from_status(status)
        result = self.module.evaluate_stability(
            [sample, sample],
            min_frame_delta=1,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertEqual(sample["total_frames"], "not-a-number")
        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])

    def test_sample_from_status_preserves_empty_numeric_for_structured_failure(self):
        status = FakeStatus(
            {
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "",
                "crc_errors": "0",
                "resync_count": "0",
                "sample_count": "10",
                "total_bytes": "100",
                "last_frame_age_ms": "",
                "frame_rate_hz": "",
                "bytes_per_sec": "100.0",
                "last_error_text": "",
            }
        )

        sample = self.module._sample_from_status(status)
        result = self.module.evaluate_stability(
            [sample, sample],
            min_frame_delta=1,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertEqual(sample["total_frames"], "")
        self.assertEqual(sample["last_frame_age_ms"], "")
        self.assertEqual(sample["frame_rate_hz"], "")
        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("total_frames", result["invalid_numeric_fields"])
        self.assertIn("last_frame_age_ms", result["invalid_numeric_fields"])
        self.assertIn("frame_rate_hz", result["invalid_numeric_fields"])

    def test_sample_from_status_preserves_malformed_level_for_structured_failure(self):
        status = FakeStatus(
            {
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "10",
                "crc_errors": "0",
                "resync_count": "0",
                "sample_count": "10",
                "total_bytes": "100",
                "last_error_text": "",
            },
            level="not-a-level",
        )

        sample = self.module._sample_from_status(status)
        result = self.module.evaluate_stability(
            [sample, sample],
            min_frame_delta=1,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertEqual(sample["level"], "not-a-level")
        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])

    def test_sample_from_status_preserves_malformed_rates_for_structured_failure(self):
        status = FakeStatus(
            {
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "10",
                "crc_errors": "0",
                "resync_count": "0",
                "sample_count": "10",
                "total_bytes": "100",
                "frame_rate_hz": "not-a-rate",
                "bytes_per_sec": "also-not-a-rate",
                "last_frame_age_ms": "1",
                "last_error_text": "",
            }
        )

        sample = self.module._sample_from_status(status)
        result = self.module.evaluate_stability(
            [sample, sample],
            min_frame_delta=1,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertEqual(sample["frame_rate_hz"], "not-a-rate")
        self.assertEqual(sample["bytes_per_sec"], "also-not-a-rate")
        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("frame_rate_hz", result["invalid_numeric_fields"])
        self.assertIn("bytes_per_sec", result["invalid_numeric_fields"])

    def test_sample_from_status_preserves_non_finite_rates_for_structured_failure(self):
        status = FakeStatus(
            {
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "10",
                "crc_errors": "0",
                "resync_count": "0",
                "sample_count": "10",
                "total_bytes": "100",
                "frame_rate_hz": "nan",
                "bytes_per_sec": "inf",
                "last_frame_age_ms": "1",
                "last_error_text": "",
            }
        )

        sample = self.module._sample_from_status(status)
        result = self.module.evaluate_stability(
            [sample, sample],
            min_frame_delta=1,
            max_crc_delta=10,
            max_resync_delta=10,
        )

        self.assertEqual(sample["frame_rate_hz"], "nan")
        self.assertEqual(sample["bytes_per_sec"], "inf")
        self.assertFalse(result["pass"], result)
        self.assertIn("numeric_parse", result["failures"])
        self.assertIn("frame_rate_hz", result["invalid_numeric_fields"])
        self.assertIn("bytes_per_sec", result["invalid_numeric_fields"])

    def test_samples_from_diagnostic_array_keeps_all_matching_statuses(self):
        first = FakeStatus(
            {
                "input_mode": "serial",
                "input_path": "/dev/ttyUSB1",
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "1",
                "crc_errors": "0",
                "resync_count": "0",
                "sample_count": "1",
                "total_bytes": "10",
                "last_error_text": "",
            }
        )
        second = FakeStatus(
            {
                "input_mode": "serial",
                "input_path": "/dev/ttyUSB0",
                "serial_open": "true",
                "publish_raw": "false",
                "total_frames": "2",
                "crc_errors": "0",
                "resync_count": "0",
                "sample_count": "2",
                "total_bytes": "20",
                "last_error_text": "",
            }
        )
        unrelated = FakeStatus({"total_frames": "99"})
        unrelated.name = "other/status"

        samples = self.module.samples_from_diagnostic_array(
            FakeDiagnosticArray([first, unrelated, second]),
            status_name="tg0_multipad/raw_stream",
        )

        self.assertEqual([sample["input_path"] for sample in samples], ["/dev/ttyUSB1", "/dev/ttyUSB0"])


if __name__ == "__main__":
    unittest.main()
