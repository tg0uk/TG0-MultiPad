#!/usr/bin/env python3
import sys
import time

import rclpy
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from tg0_multipad_msgs.msg import RawFrame


def main() -> int:
    rclpy.init()
    node = rclpy.create_node("tg0_multipad_smoke_listener")
    received = []

    def callback(msg: RawFrame) -> None:
        print(f"frame_id={msg.header.frame_id}")
        print(f"device_id={msg.device_id}")
        print(f"tag={msg.tag}")
        print(f"encoded_tag={msg.encoded_tag}")
        print(f"data={list(msg.data)}")
        print(f"crc={msg.crc}")
        print(f"crc_valid={msg.crc_valid}")
        received.append(msg)

    qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=ReliabilityPolicy.BEST_EFFORT,
    )
    node.create_subscription(RawFrame, "/tg0/multipad/raw", callback, qos)
    deadline = time.time() + 8.0
    while rclpy.ok() and not received and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)

    node.destroy_node()
    rclpy.shutdown()
    return 0 if received else 2


if __name__ == "__main__":
    sys.exit(main())
