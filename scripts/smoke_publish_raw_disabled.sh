#!/usr/bin/env bash
set -eo pipefail

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-231}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
input_path=/tmp/tg0_valid_frame.bin
printf "05009cffc8006022ee3b" | xxd -r -p > "${input_path}"
rm -f /tmp/tg0_publish_raw_disabled_node.txt

ros2 run tg0_multipad_driver tg0_multipad_raw_publisher \
  --ros-args \
  -p input_path:="${input_path}" \
  -p publish_raw:=false \
  -p startup_delay_ms:=1000 \
  -p replay_count:=0 \
  > /tmp/tg0_publish_raw_disabled_node.txt 2>&1 &
node_pid=$!

cleanup() {
  kill "${node_pid}" >/dev/null 2>&1 || true
  wait "${node_pid}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

python3 "${script_dir}/smoke_diagnostics_topic.py" \
  --expect-hardware-id "${input_path}" \
  --expect-input-mode file \
  --expect-input-path "${input_path}" \
  --expect-publish-raw false \
  --min-total-frames 1 \
  --min-sample-count 1 \
  --min-total-bytes 10 \
  --timeout-sec 8

if ros2 topic list | grep -Fxq "/tg0/multipad/raw"; then
  echo "PUBLISH_RAW_DISABLED_RAW_TOPIC_PRESENT" >&2
  exit 2
fi

echo "PUBLISH_RAW_DISABLED_SMOKE_OK"
