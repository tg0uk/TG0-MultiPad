#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/humble/setup.bash
source /tmp/tg0_ros_install/setup.bash
set -u

printf "05009cffc8006022ee3b" | xxd -r -p > /tmp/tg0_valid_frame.bin
rm -f /tmp/tg0_raw_py_sub.txt /tmp/tg0_raw_node.txt

python3 /home/ubuntu/TG0_ROS/ros/scripts/smoke_raw_publisher.py \
  > /tmp/tg0_raw_py_sub.txt 2>&1 &
sub_pid=$!

sleep 1

timeout 10s ros2 run tg0_multipad_driver tg0_multipad_raw_publisher \
  --ros-args \
  -p input_path:=/tmp/tg0_valid_frame.bin \
  -p device_id:=7 \
  -p frame_id:=file_multipad_link \
  -p startup_delay_ms:=1000 \
  -p replay_count:=5 \
  > /tmp/tg0_raw_node.txt 2>&1 || true

wait "${sub_pid}"

cat /tmp/tg0_raw_py_sub.txt

grep -Fq "frame_id=file_multipad_link" /tmp/tg0_raw_py_sub.txt
grep -Fq "device_id=7" /tmp/tg0_raw_py_sub.txt
grep -Fq "tag=2" /tmp/tg0_raw_py_sub.txt
grep -Fq "encoded_tag=5" /tmp/tg0_raw_py_sub.txt
grep -Fq "data=[2, -100, 200, 8800]" /tmp/tg0_raw_py_sub.txt
grep -Fq "crc=60987" /tmp/tg0_raw_py_sub.txt
grep -Fq "crc_valid=True" /tmp/tg0_raw_py_sub.txt

echo "RAW_FILE_REPLAY_SMOKE_OK"
