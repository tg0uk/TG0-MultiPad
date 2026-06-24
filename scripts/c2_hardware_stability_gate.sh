#!/usr/bin/env bash
set -euo pipefail

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

serial_port="${SERIAL_PORT:-/dev/ttyUSB0}"
baud_rate="${BAUD_RATE:-12000000}"
frame_id="${FRAME_ID:-tg0_multipad_link}"
duration_sec="${DURATION_SEC:-600}"
min_frame_delta="${MIN_FRAME_DELTA:-1000000}"
max_crc_delta="${MAX_CRC_DELTA:-100}"
max_resync_delta="${MAX_RESYNC_DELTA:-100}"
output_path="${OUTPUT:-jetson_test_logs/c2_diagnostics_result.json}"
publisher_log="${PUBLISHER_LOG:-jetson_test_logs/c2_raw_publisher.log}"

mkdir -p "$(dirname "${output_path}")" "$(dirname "${publisher_log}")"

ros2 run tg0_multipad_driver tg0_multipad_raw_publisher \
  --ros-args \
  -p serial_port:="${serial_port}" \
  -p baud_rate:="${baud_rate}" \
  -p frame_id:="${frame_id}" \
  -p publish_raw:=false \
  > "${publisher_log}" 2>&1 &
publisher_pid=$!

cleanup() {
  kill "${publisher_pid}" >/dev/null 2>&1 || true
  wait "${publisher_pid}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

sleep 1

if ! kill -0 "${publisher_pid}" >/dev/null 2>&1; then
  echo "C2_HARDWARE_GATE_PUBLISHER_EXITED" >&2
  tail -n 40 "${publisher_log}" >&2 || true
  exit 2
fi

if ros2 topic list | grep -Fxq "/tg0/multipad/raw"; then
  echo "C2_HARDWARE_GATE_RAW_TOPIC_PRESENT" >&2
  exit 3
fi

monitor_args=(
  scripts/c2_diagnostics_stability.py
  --duration-sec "${duration_sec}"
  --min-frame-delta "${min_frame_delta}"
  --max-crc-delta "${max_crc_delta}"
  --max-resync-delta "${max_resync_delta}"
  --expect-input-mode serial
  --expect-input-path "${serial_port}"
  --expect-publish-raw false
  --fail-on-filtered-samples
  --output "${output_path}"
)

if [[ -n "${MIN_DIAGNOSTIC_SAMPLES:-}" ]]; then
  monitor_args+=(--min-diagnostic-samples "${MIN_DIAGNOSTIC_SAMPLES}")
fi

set +e
python3 "${monitor_args[@]}"
monitor_rc=$?
set -e

if ros2 topic list | grep -Fxq "/tg0/multipad/raw"; then
  echo "C2_HARDWARE_GATE_RAW_TOPIC_PRESENT_AFTER_MONITOR" >&2
  exit 4
fi

if [[ "${monitor_rc}" -eq 0 ]]; then
  echo "C2_HARDWARE_STABILITY_GATE_OK"
fi
exit "${monitor_rc}"
