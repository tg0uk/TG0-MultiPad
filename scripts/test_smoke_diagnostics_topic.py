#!/usr/bin/env python3
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import types
import unittest


def load_module():
    rclpy_module = types.ModuleType("rclpy")
    diagnostic_msgs_module = types.ModuleType("diagnostic_msgs")
    diagnostic_msgs_msg_module = types.ModuleType("diagnostic_msgs.msg")
    diagnostic_msgs_msg_module.DiagnosticArray = object
    sys.modules["rclpy"] = rclpy_module
    sys.modules["diagnostic_msgs"] = diagnostic_msgs_module
    sys.modules["diagnostic_msgs.msg"] = diagnostic_msgs_msg_module

    script_path = Path(__file__).with_name("smoke_diagnostics_topic.py")
    spec = importlib.util.spec_from_file_location("smoke_diagnostics_topic", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeKeyValue:
    def __init__(self, key, value):
        self.key = key
        self.value = value


class FakeStatus:
    def __init__(
        self,
        *,
        name="tg0_multipad/raw_stream",
        hardware_id="/tmp/input.bin",
        level=0,
        values=None,
    ):
        self.name = name
        self.hardware_id = hardware_id
        self.level = level
        self.message = "running"
        self.values = [FakeKeyValue(key, value) for key, value in (values or {}).items()]


class FakeDiagnosticArray:
    def __init__(self, statuses):
        self.status = statuses


def complete_values(**overrides):
    values = {
        "input_mode": "file",
        "input_path": "/tmp/input.bin",
        "serial_open": "false",
        "publish_raw": "false",
        "total_frames": "1",
        "crc_errors": "0",
        "resync_count": "0",
        "sample_count": "1",
        "total_bytes": "10",
        "frame_rate_hz": "1.0",
        "bytes_per_sec": "10.0",
        "last_frame_age_ms": "250",
        "last_error_text": "",
    }
    values.update(overrides)
    return values


class SmokeDiagnosticsTopicTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_reports_publish_raw_mismatch(self):
        status = FakeStatus(values=complete_values(publish_raw="true"))
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=0,
            min_sample_count=0,
            min_total_bytes=0,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("unexpected publish_raw: true", errors)

    def test_accepts_matching_expected_diagnostics(self):
        status = FakeStatus(values=complete_values())
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=0,
            min_sample_count=0,
            min_total_bytes=0,
        )

        self.assertEqual(self.module.diagnostic_status_errors(status, args), [])

    def test_reports_counters_below_minimum(self):
        status = FakeStatus(values=complete_values(total_frames="0", sample_count="0", total_bytes="0"))
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("total_frames below minimum: 0 < 1", errors)
        self.assertIn("sample_count below minimum: 0 < 1", errors)
        self.assertIn("total_bytes below minimum: 0 < 10", errors)

    def test_reports_malformed_numeric_counter_value(self):
        status = FakeStatus(values=complete_values(total_frames="not-a-number"))
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("invalid numeric total_frames: not-a-number", errors)

    def test_reports_malformed_required_numeric_values(self):
        status = FakeStatus(
            values=complete_values(
                crc_errors="bad-crc",
                frame_rate_hz="bad-rate",
            )
        )
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("invalid numeric crc_errors: bad-crc", errors)
        self.assertIn("invalid numeric frame_rate_hz: bad-rate", errors)

    def test_reports_empty_required_numeric_values(self):
        status = FakeStatus(
            values=complete_values(
                crc_errors="",
                frame_rate_hz="",
            )
        )
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("invalid numeric crc_errors: ", errors)
        self.assertIn("invalid numeric frame_rate_hz: ", errors)

    def test_reports_negative_required_numeric_values(self):
        status = FakeStatus(
            values=complete_values(
                crc_errors="-1",
                frame_rate_hz="-1.0",
                last_frame_age_ms="-5",
            )
        )
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("invalid numeric crc_errors: -1", errors)
        self.assertIn("invalid numeric frame_rate_hz: -1.0", errors)
        self.assertIn("invalid numeric last_frame_age_ms: -5", errors)

    def test_reports_missing_runtime_health_fields(self):
        values = complete_values()
        del values["serial_open"]
        del values["last_frame_age_ms"]
        status = FakeStatus(values=values)
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("missing diagnostic keys: ['last_frame_age_ms', 'serial_open']", errors)

    def test_reports_malformed_last_frame_age(self):
        status = FakeStatus(values=complete_values(last_frame_age_ms="unknown"))
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("invalid numeric last_frame_age_ms: unknown", errors)

    def test_reports_non_finite_required_rate_values(self):
        status = FakeStatus(
            values=complete_values(
                frame_rate_hz="nan",
                bytes_per_sec="inf",
            )
        )
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("invalid numeric bytes_per_sec: inf", errors)
        self.assertIn("invalid numeric frame_rate_hz: nan", errors)

    def test_selects_matching_status_from_diagnostic_array(self):
        unrelated = FakeStatus(
            name="other/status",
            hardware_id="other",
            values=complete_values(input_path="other"),
        )
        expected = FakeStatus(values=complete_values())
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        matched_status, errors = self.module.matching_diagnostic_status(
            FakeDiagnosticArray([unrelated, expected]),
            args,
        )

        self.assertIs(matched_status, expected)
        self.assertEqual(errors, [])

    def test_reports_errors_from_most_relevant_status_when_none_match(self):
        relevant = FakeStatus(
            values=complete_values(publish_raw="true"),
        )
        unrelated = FakeStatus(
            name="other/status",
            hardware_id="other",
            values=complete_values(input_path="other"),
        )
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        matched_status, errors = self.module.matching_diagnostic_status(
            FakeDiagnosticArray([relevant, unrelated]),
            args,
        )

        self.assertIsNone(matched_status)
        self.assertIn("unexpected publish_raw: true", errors)
        self.assertNotIn("unexpected diagnostic name: other/status", errors)

    def test_reports_non_ok_diagnostic_level(self):
        status = FakeStatus(level=1, values=complete_values())
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("unexpected diagnostic level: 1", errors)

    def test_reports_malformed_diagnostic_level(self):
        status = FakeStatus(level="not-a-level", values=complete_values())
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("invalid diagnostic level: not-a-level", errors)

    def test_reports_non_empty_last_error_text(self):
        status = FakeStatus(values=complete_values(last_error_text="serial read failed"))
        args = SimpleNamespace(
            expect_name="tg0_multipad/raw_stream",
            expect_hardware_id="/tmp/input.bin",
            expect_input_mode="file",
            expect_input_path="/tmp/input.bin",
            expect_publish_raw="false",
            min_total_frames=1,
            min_sample_count=1,
            min_total_bytes=10,
        )

        errors = self.module.diagnostic_status_errors(status, args)

        self.assertIn("last_error_text is not empty: serial read failed", errors)


if __name__ == "__main__":
    unittest.main()
