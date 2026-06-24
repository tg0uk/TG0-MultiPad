#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/humble/setup.bash
source /tmp/tg0_ros_install/setup.bash
set -u

bridge_port="${1:-17007}"

rm -f /tmp/tg0_com7_bridge_pty.txt \
  /tmp/tg0_com7_bridge_server.txt \
  /tmp/tg0_com7_bridge_sub.txt \
  /tmp/tg0_com7_bridge_node.txt

python3 - "${bridge_port}" <<'PY' > /tmp/tg0_com7_bridge_server.txt 2>&1 &
import os
import pty
import socket
import sys
import tty

port = int(sys.argv[1])
master_fd, slave_fd = pty.openpty()
tty.setraw(master_fd)
tty.setraw(slave_fd)
slave_path = os.ttyname(slave_fd)

with open("/tmp/tg0_com7_bridge_pty.txt", "w", encoding="utf-8") as f:
    f.write(slave_path + "\n")
    f.flush()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", port))
server.listen(1)
print(f"listening port={port} slave={slave_path}", flush=True)

conn, addr = server.accept()
print(f"accepted addr={addr}", flush=True)
try:
    while True:
        data = conn.recv(8192)
        if not data:
            break
        os.write(master_fd, data)
finally:
    conn.close()
    server.close()
PY
server_pid=$!

cleanup() {
  kill "${node_pid:-0}" >/dev/null 2>&1 || true
  kill "${sub_pid:-0}" >/dev/null 2>&1 || true
  kill "${server_pid:-0}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if [ -s /tmp/tg0_com7_bridge_pty.txt ]; then
    break
  fi
  sleep 0.1
done

reader_pty="$(cat /tmp/tg0_com7_bridge_pty.txt 2>/dev/null || true)"
if [ -z "${reader_pty}" ]; then
  cat /tmp/tg0_com7_bridge_server.txt 2>/dev/null || true
  echo "Failed to create bridge pseudo terminal" >&2
  exit 1
fi

python3 /home/ubuntu/TG0_ROS/ros/scripts/smoke_raw_publisher.py \
  > /tmp/tg0_com7_bridge_sub.txt 2>&1 &
sub_pid=$!

sleep 1

timeout 15s ros2 run tg0_multipad_driver tg0_multipad_raw_publisher \
  --ros-args \
  -p serial_port:="${reader_pty}" \
  -p baud_rate:=12000000 \
  -p read_chunk_size:=4096 \
  -p device_id:=0 \
  -p frame_id:=hardware_multipad_link \
  -p startup_delay_ms:=200 \
  > /tmp/tg0_com7_bridge_node.txt 2>&1 &
node_pid=$!

wait "${sub_pid}"

cat /tmp/tg0_com7_bridge_sub.txt

grep -Fq "frame_id=hardware_multipad_link" /tmp/tg0_com7_bridge_sub.txt
grep -Fq "crc_valid=True" /tmp/tg0_com7_bridge_sub.txt

echo "RAW_HARDWARE_ROS_BRIDGE_SMOKE_OK"
