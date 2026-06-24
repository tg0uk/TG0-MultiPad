#!/usr/bin/env python3
import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DiagnosticSample = Dict[str, Any]
MONOTONIC_COUNTER_KEYS = (
    "total_frames",
    "sample_count",
    "total_bytes",
    "crc_errors",
    "resync_count",
)
BYTES_PER_FRAME = 10
BASE_REQUIRED_KEYS = (
    "level",
    "serial_open",
    "last_error_text",
    "total_frames",
    "sample_count",
    "total_bytes",
    "crc_errors",
    "resync_count",
    "last_frame_age_ms",
    "frame_rate_hz",
    "bytes_per_sec",
)
LAST_FRAME_AGE_KEY = "last_frame_age_ms"
RATE_KEYS = ("frame_rate_hz", "bytes_per_sec")
INTEGER_NUMERIC_KEYS = ("level", LAST_FRAME_AGE_KEY) + MONOTONIC_COUNTER_KEYS
FLOAT_NUMERIC_KEYS = RATE_KEYS


def _int_value(sample: DiagnosticSample, key: str) -> int:
    value = sample.get(key, 0)
    if value in (None, ""):
        raise ValueError(value)
    parsed = int(value)
    if parsed < 0:
        raise ValueError(value)
    return parsed


def _int_or_raw_value(value: Any) -> Any:
    if value in (None, ""):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _float_value(sample: DiagnosticSample, key: str) -> float:
    value = sample.get(key, 0.0)
    if value in (None, ""):
        raise ValueError(value)
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0.0:
        raise ValueError(value)
    return parsed


def _invalid_numeric_fields(samples: Iterable[DiagnosticSample]) -> List[str]:
    invalid: List[str] = []
    for sample in samples:
        for key in INTEGER_NUMERIC_KEYS:
            if key not in sample:
                continue
            try:
                _int_value(sample, key)
            except (TypeError, ValueError):
                if key not in invalid:
                    invalid.append(key)
        for key in FLOAT_NUMERIC_KEYS:
            if key not in sample:
                continue
            try:
                _float_value(sample, key)
            except (TypeError, ValueError):
                if key not in invalid:
                    invalid.append(key)
    return invalid


def _counter_decrease_keys(samples: List[DiagnosticSample]) -> List[str]:
    decreased: List[str] = []
    for key in MONOTONIC_COUNTER_KEYS:
        previous = _int_value(samples[0], key)
        for sample in samples[1:]:
            current = _int_value(sample, key)
            if current < previous:
                decreased.append(key)
                break
            previous = current
    return decreased


def _missing_required_keys(
    samples: List[DiagnosticSample],
    expected_keys: Iterable[str],
) -> List[str]:
    missing: List[str] = []
    for key in expected_keys:
        if any(key not in sample for sample in samples):
            missing.append(key)
    return missing


def _mismatch_count(
    samples: Iterable[DiagnosticSample],
    key: str,
    expected: Optional[str],
) -> int:
    if expected is None:
        return 0
    return sum(1 for sample in samples if sample.get(key) != expected)


def default_min_diagnostic_samples(duration_sec: float, configured: Optional[int]) -> int:
    if configured is not None:
        return max(2, configured)
    return max(2, int(duration_sec * 0.8))


def evaluate_stability(
    samples: Iterable[DiagnosticSample],
    *,
    min_frame_delta: int,
    max_crc_delta: int,
    max_resync_delta: int,
    min_diagnostic_samples: int = 2,
    expect_input_mode: Optional[str] = None,
    expect_input_path: Optional[str] = None,
    expect_publish_raw: Optional[str] = None,
) -> Dict[str, Any]:
    collected = list(samples)
    min_frame_delta = max(1, min_frame_delta)
    result: Dict[str, Any] = {
        "pass": False,
        "diag_count": len(collected),
        "first_diag": collected[0] if collected else None,
        "last_diag": collected[-1] if collected else None,
        "delta": {},
        "thresholds": {
            "min_frame_delta": min_frame_delta,
            "max_crc_delta": max_crc_delta,
            "max_resync_delta": max_resync_delta,
            "min_diagnostic_samples": min_diagnostic_samples,
        },
        "failures": [],
    }

    if not collected:
        result["failures"].append("no_diagnostics")
        return result

    if len(collected) < min_diagnostic_samples:
        result["failures"].append("diagnostic_sample_count")

    required_keys = list(BASE_REQUIRED_KEYS)
    if expect_input_mode is not None:
        required_keys.append("input_mode")
    if expect_input_path is not None:
        required_keys.append("input_path")
    if expect_publish_raw is not None:
        required_keys.append("publish_raw")
    result["missing_required_keys"] = _missing_required_keys(collected, required_keys)
    result["invalid_numeric_fields"] = _invalid_numeric_fields(collected)
    if result["missing_required_keys"]:
        result["failures"].append("missing_required_fields")
    if result["invalid_numeric_fields"]:
        result["failures"].append("numeric_parse")
        return result

    first = collected[0]
    last = collected[-1]
    delta = {
        "total_frames": _int_value(last, "total_frames") - _int_value(first, "total_frames"),
        "sample_count": _int_value(last, "sample_count") - _int_value(first, "sample_count"),
        "total_bytes": _int_value(last, "total_bytes") - _int_value(first, "total_bytes"),
        "crc_errors": _int_value(last, "crc_errors") - _int_value(first, "crc_errors"),
        "resync_count": _int_value(last, "resync_count") - _int_value(first, "resync_count"),
    }
    result["delta"] = delta
    result["missing_level_count"] = sum(1 for sample in collected if "level" not in sample)
    result["max_level"] = max(_int_value(sample, "level") for sample in collected)
    result["serial_closed_count"] = sum(
        1 for sample in collected if sample.get("serial_open") != "true"
    )
    result["error_text_count"] = sum(
        1 for sample in collected if sample.get("last_error_text", "")
    )
    result["counter_decrease_keys"] = _counter_decrease_keys(collected)
    result["expected_field_mismatch_counts"] = {
        "input_mode": _mismatch_count(collected, "input_mode", expect_input_mode),
        "input_path": _mismatch_count(collected, "input_path", expect_input_path),
        "publish_raw": _mismatch_count(collected, "publish_raw", expect_publish_raw),
    }
    result["counter_consistency"] = {
        "sample_count_matches_total_frames": delta["sample_count"] == delta["total_frames"],
        "min_expected_total_bytes_delta": delta["total_frames"] * BYTES_PER_FRAME,
    }

    if result["serial_closed_count"] > 0:
        result["failures"].append("serial_open")
    if result["missing_level_count"] > 0:
        result["failures"].append("diagnostic_level_missing")
    if result["max_level"] != 0:
        result["failures"].append("diagnostic_level")
    if result["expected_field_mismatch_counts"]["input_mode"] > 0:
        result["failures"].append("input_mode")
    if result["expected_field_mismatch_counts"]["input_path"] > 0:
        result["failures"].append("input_path")
    if result["expected_field_mismatch_counts"]["publish_raw"] > 0:
        result["failures"].append("publish_raw")
    if result["error_text_count"] > 0:
        result["failures"].append("last_error_text")
    if result["counter_decrease_keys"]:
        result["failures"].append("counter_monotonic")
    if delta["total_frames"] < min_frame_delta:
        result["failures"].append("total_frames_delta")
    if delta["sample_count"] < min_frame_delta:
        result["failures"].append("sample_count_delta")
    if delta["total_bytes"] <= 0:
        result["failures"].append("total_bytes_delta")
    if not result["counter_consistency"]["sample_count_matches_total_frames"]:
        result["failures"].append("sample_count_consistency")
    if delta["total_bytes"] < result["counter_consistency"]["min_expected_total_bytes_delta"]:
        result["failures"].append("total_bytes_consistency")
    if delta["crc_errors"] > max_crc_delta:
        result["failures"].append("crc_errors_delta")
    if delta["resync_count"] > max_resync_delta:
        result["failures"].append("resync_count_delta")

    result["pass"] = len(result["failures"]) == 0
    return result


def _level_to_int(level: Any) -> int:
    if isinstance(level, (bytes, bytearray)):
        return level[0] if level else 0
    return int(level)


def _level_or_raw_value(level: Any) -> Any:
    try:
        return _level_to_int(level)
    except (TypeError, ValueError):
        return level


def _float_or_raw_value(value: Any) -> Any:
    if value in (None, ""):
        return value
    try:
        parsed = float(value or 0.0)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(parsed):
        return value
    return parsed


def _sample_from_status(status: Any) -> DiagnosticSample:
    values = {item.key: item.value for item in status.values}
    sample: DiagnosticSample = {
        "t": time.time(),
        "level": _level_or_raw_value(status.level),
        "message": status.message,
    }
    for key in (
        "input_mode",
        "input_path",
        "serial_open",
        "publish_raw",
        "last_error_text",
    ):
        if key in values:
            sample[key] = values[key]
    if LAST_FRAME_AGE_KEY in values:
        sample[LAST_FRAME_AGE_KEY] = _int_or_raw_value(values.get(LAST_FRAME_AGE_KEY))
    for key in MONOTONIC_COUNTER_KEYS:
        if key in values:
            sample[key] = _int_or_raw_value(values.get(key))
    for key in RATE_KEYS:
        if key in values:
            sample[key] = _float_or_raw_value(values.get(key))
    return sample


def samples_from_diagnostic_array(message: Any, *, status_name: str) -> List[DiagnosticSample]:
    return [
        _sample_from_status(status)
        for status in message.status
        if status.name == status_name
    ]


def _sample_matches_expected(
    sample: DiagnosticSample,
    *,
    expect_input_mode: Optional[str] = None,
    expect_input_path: Optional[str] = None,
) -> bool:
    if expect_input_mode is not None and sample.get("input_mode") != expect_input_mode:
        return False
    if expect_input_path is not None and sample.get("input_path") != expect_input_path:
        return False
    return True


def _partition_samples_by_expected_source(
    samples: Iterable[DiagnosticSample],
    *,
    expect_input_mode: Optional[str] = None,
    expect_input_path: Optional[str] = None,
) -> Dict[str, Any]:
    matched: List[DiagnosticSample] = []
    filtered_count = 0
    last_filtered_sample: Optional[DiagnosticSample] = None
    for sample in samples:
        if _sample_matches_expected(
            sample,
            expect_input_mode=expect_input_mode,
            expect_input_path=expect_input_path,
        ):
            matched.append(sample)
        else:
            filtered_count += 1
            last_filtered_sample = sample
    return {
        "samples": matched,
        "filtered_sample_count": filtered_count,
        "last_filtered_sample": last_filtered_sample,
    }


def apply_filtered_sample_policy(
    result: Dict[str, Any],
    *,
    filtered_sample_count: int,
    fail_on_filtered_samples: bool,
) -> None:
    if fail_on_filtered_samples and filtered_sample_count > 0:
        result["failures"].append("filtered_diagnostics_source")
        result["pass"] = False


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    return value


def collect_diagnostics(
    *,
    duration_sec: float,
    topic: str,
    status_name: str,
    expect_input_mode: Optional[str] = None,
    expect_input_path: Optional[str] = None,
) -> Dict[str, Any]:
    import rclpy
    from diagnostic_msgs.msg import DiagnosticArray

    rclpy.init()
    node = rclpy.create_node("tg0_c2_diagnostics_stability_monitor")
    samples: List[DiagnosticSample] = []

    def callback(message: DiagnosticArray) -> None:
        samples.extend(samples_from_diagnostic_array(message, status_name=status_name))

    node.create_subscription(DiagnosticArray, topic, callback, 10)
    start = time.time()
    while rclpy.ok() and time.time() - start < duration_sec:
        rclpy.spin_once(node, timeout_sec=0.2)

    node.destroy_node()
    rclpy.shutdown()
    return _partition_samples_by_expected_source(
        samples,
        expect_input_mode=expect_input_mode,
        expect_input_path=expect_input_path,
    )


def write_result(result: Dict[str, Any], output_path: Optional[str]) -> None:
    safe_result = _json_safe_value(result)
    text = json.dumps(safe_result, allow_nan=False, indent=2, sort_keys=True)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(
        "C2_DIAGNOSTICS_STABILITY_RESULT=" +
        json.dumps(safe_result, allow_nan=False, sort_keys=True)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-sec", type=float, default=600.0)
    parser.add_argument("--topic", default="/diagnostics")
    parser.add_argument("--status-name", default="tg0_multipad/raw_stream")
    parser.add_argument("--min-frame-delta", type=int, default=1_000_000)
    parser.add_argument("--max-crc-delta", type=int, default=100)
    parser.add_argument("--max-resync-delta", type=int, default=100)
    parser.add_argument("--min-diagnostic-samples", type=int)
    parser.add_argument("--expect-input-mode")
    parser.add_argument("--expect-input-path")
    parser.add_argument("--expect-publish-raw", choices=("true", "false"))
    parser.add_argument("--fail-on-filtered-samples", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    collected = collect_diagnostics(
        duration_sec=args.duration_sec,
        topic=args.topic,
        status_name=args.status_name,
        expect_input_mode=args.expect_input_mode,
        expect_input_path=args.expect_input_path,
    )
    result = evaluate_stability(
        collected["samples"],
        min_frame_delta=args.min_frame_delta,
        max_crc_delta=args.max_crc_delta,
        max_resync_delta=args.max_resync_delta,
        min_diagnostic_samples=default_min_diagnostic_samples(
            args.duration_sec,
            args.min_diagnostic_samples,
        ),
        expect_input_mode=args.expect_input_mode,
        expect_input_path=args.expect_input_path,
        expect_publish_raw=args.expect_publish_raw,
    )
    result["duration_sec"] = args.duration_sec
    result["filtered_sample_count"] = collected["filtered_sample_count"]
    result["last_filtered_sample"] = collected["last_filtered_sample"]
    apply_filtered_sample_policy(
        result,
        filtered_sample_count=collected["filtered_sample_count"],
        fail_on_filtered_samples=args.fail_on_filtered_samples,
    )
    write_result(result, args.output)
    return 0 if result["pass"] else 6


if __name__ == "__main__":
    sys.exit(main())
