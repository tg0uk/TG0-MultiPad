#!/usr/bin/env python3
import argparse
import math
import sys
import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray


REQUIRED_KEYS = {
    "input_mode",
    "input_path",
    "serial_open",
    "publish_raw",
    "total_frames",
    "crc_errors",
    "resync_count",
    "sample_count",
    "total_bytes",
    "frame_rate_hz",
    "bytes_per_sec",
    "last_frame_age_ms",
    "last_error_text",
}
INTEGER_VALUE_KEYS = {
    "total_frames",
    "crc_errors",
    "resync_count",
    "sample_count",
    "total_bytes",
    "last_frame_age_ms",
}
FLOAT_VALUE_KEYS = {
    "frame_rate_hz",
    "bytes_per_sec",
}


def values_by_key(status):
    return {item.key: item.value for item in status.values}


def level_to_int(level):
    if isinstance(level, (bytes, bytearray)):
        return level[0] if level else 0
    return int(level)


def parse_int_value(value):
    if value in (None, ""):
        return 0, value
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0, value
    if parsed < 0:
        return 0, value
    return parsed, None


def parse_float_value(value):
    if value in (None, ""):
        return 0.0, value
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0, value
    if not math.isfinite(parsed) or parsed < 0.0:
        return 0.0, value
    return parsed, None


def diagnostic_status_errors(status, args):
    values = values_by_key(status)
    errors = []
    if status.name != args.expect_name:
        errors.append(f"unexpected diagnostic name: {status.name}")
    if status.hardware_id != args.expect_hardware_id:
        errors.append(f"unexpected hardware_id: {status.hardware_id}")
    try:
        level = level_to_int(status.level)
        if level != 0:
            errors.append(f"unexpected diagnostic level: {level}")
    except (TypeError, ValueError):
        errors.append(f"invalid diagnostic level: {status.level}")

    missing = sorted(REQUIRED_KEYS.difference(values))
    if missing:
        errors.append(f"missing diagnostic keys: {missing}")

    for key in sorted(INTEGER_VALUE_KEYS.difference(missing)):
        _, invalid = parse_int_value(values.get(key))
        if invalid is not None:
            errors.append(f"invalid numeric {key}: {invalid}")
    for key in sorted(FLOAT_VALUE_KEYS.difference(missing)):
        _, invalid = parse_float_value(values.get(key))
        if invalid is not None:
            errors.append(f"invalid numeric {key}: {invalid}")

    expected_values = {
        "input_mode": args.expect_input_mode,
        "input_path": args.expect_input_path,
        "publish_raw": args.expect_publish_raw,
    }
    for key, expected in expected_values.items():
        if expected is not None and values.get(key) != expected:
            errors.append(f"unexpected {key}: {values.get(key, 'MISSING')}")

    minimum_values = {
        "total_frames": args.min_total_frames,
        "sample_count": args.min_sample_count,
        "total_bytes": args.min_total_bytes,
    }
    for key, minimum in minimum_values.items():
        actual, invalid = parse_int_value(values.get(key, "0"))
        if invalid is not None:
            continue
        if actual < minimum:
            errors.append(f"{key} below minimum: {actual} < {minimum}")

    last_error_text = values.get("last_error_text", "")
    if last_error_text:
        errors.append(f"last_error_text is not empty: {last_error_text}")

    return errors


def diagnostic_status_relevance(status, args):
    score = 0
    if status.name == args.expect_name:
        score += 2
    if status.hardware_id == args.expect_hardware_id:
        score += 1
    return score


def matching_diagnostic_status(message, args):
    if not message.status:
        return None, ["empty diagnostic status"]

    best_errors = []
    best_score = -1
    for status in message.status:
        errors = diagnostic_status_errors(status, args)
        if not errors:
            return status, []
        score = diagnostic_status_relevance(status, args)
        if score > best_score:
            best_score = score
            best_errors = errors
    return None, best_errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-name", default="tg0_multipad/raw_stream")
    parser.add_argument("--expect-hardware-id", required=True)
    parser.add_argument("--expect-input-mode")
    parser.add_argument("--expect-input-path")
    parser.add_argument("--expect-publish-raw", choices=("true", "false"))
    parser.add_argument("--min-total-frames", type=int, default=0)
    parser.add_argument("--min-sample-count", type=int, default=0)
    parser.add_argument("--min-total-bytes", type=int, default=0)
    parser.add_argument("--timeout-sec", type=float, default=8.0)
    args = parser.parse_args()

    rclpy.init()
    node = rclpy.create_node("tg0_diagnostics_smoke_listener")
    received = []
    last_errors = []
    matched_status = None

    def callback(msg: DiagnosticArray) -> None:
        received.append(msg)

    node.create_subscription(DiagnosticArray, "/diagnostics", callback, 10)
    deadline = time.time() + args.timeout_sec
    while time.time() < deadline and matched_status is None:
        rclpy.spin_once(node, timeout_sec=0.1)
        while received:
            msg = received.pop(0)
            status, last_errors = matching_diagnostic_status(msg, args)
            if status is not None:
                matched_status = status
                break

    node.destroy_node()
    rclpy.shutdown()

    if matched_status is None and not last_errors:
        print("DIAGNOSTICS_TOPIC_SMOKE_NO_MESSAGE", file=sys.stderr)
        return 2

    if matched_status is None:
        for error in last_errors:
            print(error, file=sys.stderr)
        return 4

    status = matched_status
    values = values_by_key(status)
    print(f"name={status.name}")
    print(f"hardware_id={status.hardware_id}")
    print(f"level={status.level}")
    print(f"message={status.message}")
    for key in (
        "input_mode",
        "input_path",
        "publish_raw",
        "total_frames",
        "crc_errors",
        "resync_count",
        "sample_count",
        "total_bytes",
        "frame_rate_hz",
        "bytes_per_sec",
        "last_frame_age_ms",
        "last_error_text",
    ):
        print(f"{key}={values.get(key, 'MISSING')}")

    print("DIAGNOSTICS_TOPIC_SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
