#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/humble/setup.bash
source /tmp/tg0_ros_install/setup.bash
set -u

rm -f /tmp/tg0_raw_serial_py_sub.txt \
  /tmp/tg0_raw_serial_node.txt \
  /tmp/tg0_raw_serial_pty.txt

python3 - <<'PY' &
import os
import pty
import time
import tty

master_fd, slave_fd = pty.openpty()
tty.setraw(master_fd)
tty.setraw(slave_fd)
slave_path = os.ttyname(slave_fd)
with open("/tmp/tg0_raw_serial_pty.txt", "w", encoding="utf-8") as f:
    f.write(slave_path + "\n")
    f.flush()

frame = bytes.fromhex("05009cffc8006022ee3b")
time.sleep(2.0)
for _ in range(20):
    os.write(master_fd, frame)
    time.sleep(0.1)
time.sleep(4.0)
PY
pty_pid=$!

cleanup() {
  kill "${node_pid:-0}" >/dev/null 2>&1 || true
  kill "${sub_pid:-0}" >/dev/null 2>&1 || true
  kill "${pty_pid:-0}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if [ -s /tmp/tg0_raw_serial_pty.txt ]; then
    break
  fi
  sleep 0.1
done

reader_pty="$(cat /tmp/tg0_raw_serial_pty.txt 2>/dev/null || true)"

if [ -z "${reader_pty}" ]; then
  echo "Failed to create pseudo serial pair" >&2
  exit 1
fi

python3 /home/ubuntu/TG0_ROS/ros/scripts/smoke_raw_publisher.py \
  > /tmp/tg0_raw_serial_py_sub.txt 2>&1 &
sub_pid=$!

sleep 1

timeout 10s ros2 run tg0_multipad_driver tg0_multipad_raw_publisher \
  --ros-args \
  -p serial_port:="${reader_pty}" \
  -p baud_rate:=12000000 \
  -p read_chunk_size:=64 \
  -p device_id:=8 \
  -p frame_id:=serial_multipad_link \
  -p startup_delay_ms:=200 \
  > /tmp/tg0_raw_serial_node.txt 2>&1 &
node_pid=$!

sleep 1

wait "${sub_pid}"

cat /tmp/tg0_raw_serial_py_sub.txt

grep -Fq "frame_id=serial_multipad_link" /tmp/tg0_raw_serial_py_sub.txt
grep -Fq "device_id=8" /tmp/tg0_raw_serial_py_sub.txt
grep -Fq "tag=2" /tmp/tg0_raw_serial_py_sub.txt
grep -Fq "encoded_tag=5" /tmp/tg0_raw_serial_py_sub.txt
grep -Fq "data=[2, -100, 200, 8800]" /tmp/tg0_raw_serial_py_sub.txt
grep -Fq "crc=60987" /tmp/tg0_raw_serial_py_sub.txt
grep -Fq "crc_valid=True" /tmp/tg0_raw_serial_py_sub.txt

echo "RAW_SERIAL_PTY_SMOKE_OK"
