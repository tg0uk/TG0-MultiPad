#!/usr/bin/env python3
import argparse
from typing import List


def normalized_prefix(prefix: str) -> str:
    prefix = prefix.strip()
    if not prefix:
        raise ValueError("output prefix must not be empty")
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    return prefix.rstrip("/")


def channel_topics(prefix: str, tag_count: int = 8) -> List[str]:
    base = normalized_prefix(prefix)
    if tag_count < 1:
        raise ValueError("tag count must be at least 1")
    return [
        f"{base}/tag{tag}/data{data_index}"
        for tag in range(tag_count)
        for data_index in (1, 2, 3)
    ]


def parse_cli(argv=None):
    parser = argparse.ArgumentParser(
        description="Publish downsampled TG0 multipad raw channels for rqt_plot."
    )
    parser.add_argument(
        "--describe-topics",
        action="store_true",
        help="Print the sensor data output topics and exit without importing ROS.",
    )
    parser.add_argument(
        "--output-prefix",
        default="/tg0/multipad/raw_plot",
        help="Output prefix used with --describe-topics.",
    )
    parser.add_argument(
        "--tag-count",
        type=int,
        default=8,
        help="Number of tag namespaces to describe.",
    )
    return parser.parse_known_args(argv)


def run_node(args=None) -> int:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from std_msgs.msg import Float32
    from tg0_multipad_msgs.msg import RawFrame

    class RawPlotChannelsNode(Node):
        def __init__(self):
            super().__init__("tg0_multipad_raw_plot_channels")
            self.declare_parameter("input_topic", "/tg0/multipad/raw")
            self.declare_parameter("output_prefix", "/tg0/multipad/raw_plot")
            self.declare_parameter("publish_hz", 20.0)
            self.declare_parameter("tag_count", 8)

            input_topic = self.get_parameter("input_topic").value
            output_prefix = self.get_parameter("output_prefix").value
            publish_hz = float(self.get_parameter("publish_hz").value)
            tag_count = int(self.get_parameter("tag_count").value)
            if publish_hz <= 0.0:
                raise ValueError("publish_hz must be greater than 0")
            if tag_count < 1:
                raise ValueError("tag_count must be at least 1")

            self._tag_count = tag_count
            self._latest_by_tag = {}
            topics = channel_topics(output_prefix, tag_count)
            self._channel_publishers = {}
            for tag in range(tag_count):
                self._channel_publishers[tag] = {
                    data_index: self.create_publisher(
                        Float32,
                        f"{normalized_prefix(output_prefix)}/tag{tag}/data{data_index}",
                        10,
                    )
                    for data_index in (1, 2, 3)
                }
            self.create_subscription(
                RawFrame,
                input_topic,
                self._record_frame,
                qos_profile_sensor_data,
            )
            self.create_timer(1.0 / publish_hz, self._publish_latest)
            self.get_logger().info(
                "publishing rqt_plot tag channels: " + ", ".join(topics)
            )

        def _record_frame(self, message):
            tag = int(message.tag)
            if 0 <= tag < self._tag_count:
                self._latest_by_tag[tag] = [float(value) for value in message.data]

        def _publish_latest(self):
            for tag, values in self._latest_by_tag.items():
                for data_index, publisher in self._channel_publishers[tag].items():
                    message = Float32()
                    message.data = values[data_index]
                    publisher.publish(message)

    rclpy.init(args=args)
    node = RawPlotChannelsNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


def main(argv=None) -> int:
    parsed, remaining = parse_cli(argv)
    if parsed.describe_topics:
        for topic in channel_topics(parsed.output_prefix, parsed.tag_count):
            print(topic)
        return 0
    return run_node(args=remaining)


if __name__ == "__main__":
    raise SystemExit(main())
