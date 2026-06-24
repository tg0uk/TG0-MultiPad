#include "tg0_multipad_driver/adda_frame_parser.hpp"
#include "tg0_multipad_driver/raw_frame_message.hpp"
#include "tg0_multipad_driver/raw_stream_diagnostics.hpp"
#include "tg0_multipad_driver/serial_port.hpp"

#include "diagnostic_msgs/msg/diagnostic_array.hpp"
#include "rclcpp/rclcpp.hpp"
#include "tg0_multipad_msgs/msg/raw_frame.hpp"

#include <fstream>
#include <iterator>
#include <algorithm>
#include <cinttypes>
#include <exception>
#include <memory>
#include <string>
#include <vector>

namespace {

std::vector<uint8_t> read_all_bytes(const std::string & path)
{
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    throw std::runtime_error("failed to open input_path: " + path);
  }

  return {
    std::istreambuf_iterator<char>(input),
    std::istreambuf_iterator<char>()
  };
}

class RawFramePublisherNode : public rclcpp::Node
{
public:
  RawFramePublisherNode()
  : Node("tg0_multipad_raw_publisher")
  {
    device_id_ = static_cast<uint16_t>(declare_parameter<int>("device_id", 0));
    frame_id_ = declare_parameter<std::string>("frame_id", "tg0_multipad_link");
    input_path_ = declare_parameter<std::string>("input_path", "");
    serial_port_path_ = declare_parameter<std::string>("serial_port", "");
    baud_rate_ = declare_parameter<int>("baud_rate", 12000000);
    const auto configured_chunk_size = declare_parameter<int>("read_chunk_size", 4096);
    read_chunk_size_ = configured_chunk_size < 1 ? 1 : configured_chunk_size;
    publish_raw_ = declare_parameter<bool>("publish_raw", true);
    startup_delay_ms_ = declare_parameter<int>("startup_delay_ms", 1000);
    replay_count_ = declare_parameter<int>("replay_count", 1);
    diagnostics_.set_raw_publish_enabled(publish_raw_);

    if (publish_raw_) {
      raw_publisher_ = create_publisher<tg0_multipad_msgs::msg::RawFrame>(
        "/tg0/multipad/raw",
        rclcpp::SensorDataQoS());
    }
    diagnostics_publisher_ =
      create_publisher<diagnostic_msgs::msg::DiagnosticArray>("/diagnostics", 10);
    diagnostics_timer_ = create_wall_timer(
      std::chrono::seconds(1),
      [this]() {
        publish_diagnostics();
      });

    if (!input_path_.empty()) {
      diagnostics_.configure("file", input_path_);
      publish_timer_ = create_wall_timer(
        std::chrono::milliseconds(startup_delay_ms_),
        [this]() {
          publish_file_once();
          ++replay_index_;
          if (replay_count_ > 0 && replay_index_ >= replay_count_) {
            publish_timer_->cancel();
          }
        });
    } else if (!serial_port_path_.empty()) {
      diagnostics_.configure("serial", serial_port_path_);
      serial_port_ = std::make_unique<tg0_multipad_driver::SerialPort>(
        serial_port_path_,
        baud_rate_);
      diagnostics_.set_serial_open(true);
      RCLCPP_INFO(
        get_logger(),
        "reading TG0 multipad serial stream from %s at %d baud",
        serial_port_path_.c_str(),
        baud_rate_);
      publish_timer_ = create_wall_timer(
        std::chrono::milliseconds(startup_delay_ms_),
        [this]() {
          serial_timer_ = create_wall_timer(
            std::chrono::milliseconds(1),
            [this]() {
              publish_serial_frames();
            });
          publish_timer_->cancel();
        });
    } else {
      diagnostics_.configure("idle", "");
    }
  }

private:
  void publish_diagnostics()
  {
    diagnostic_msgs::msg::DiagnosticArray message;
    const auto timestamp = now();
    message.header.stamp = timestamp;
    message.status.push_back(diagnostics_.make_status(timestamp.seconds()));
    diagnostics_publisher_->publish(message);
  }

  void publish_file_once()
  {
    tg0_multipad_driver::AddaFrameParser parser;
    const auto bytes = read_all_bytes(input_path_);
    diagnostics_.record_bytes(bytes.size(), now().seconds());
    parser.push_bytes(bytes);

    uint64_t parsed = 0;
    uint64_t published = 0;
    while (auto frame = parser.next_frame()) {
      const auto timestamp = now();
      diagnostics_.record_sample(timestamp.seconds());
      ++parsed;
      if (raw_publisher_) {
        raw_publisher_->publish(tg0_multipad_driver::make_raw_frame_message(
          *frame,
          device_id_,
          frame_id_,
          timestamp));
        ++published;
      }
    }

    file_total_frames_ += parser.total_frames();
    file_crc_errors_ += parser.crc_errors();
    file_resync_count_ += parser.resync_count();
    diagnostics_.set_parser_counters(file_total_frames_, file_crc_errors_, file_resync_count_);

    RCLCPP_INFO(
      get_logger(),
      "parsed %" PRIu64 " raw frame(s), published=%" PRIu64
      ", crc_errors=%" PRIu64 ", resync_count=%" PRIu64,
      parsed,
      published,
      parser.crc_errors(),
      parser.resync_count());
  }

  void publish_serial_frames()
  {
    try {
      const auto bytes = serial_port_->read_available(static_cast<std::size_t>(read_chunk_size_));
      diagnostics_.set_serial_open(true);
      diagnostics_.clear_error();
      if (bytes.empty()) {
        return;
      }

      diagnostics_.record_bytes(bytes.size(), now().seconds());
      serial_parser_.push_bytes(bytes);
      while (auto frame = serial_parser_.next_frame()) {
        const auto timestamp = now();
        diagnostics_.record_sample(timestamp.seconds());
        if (raw_publisher_) {
          raw_publisher_->publish(tg0_multipad_driver::make_raw_frame_message(
            *frame,
            device_id_,
            frame_id_,
            timestamp));
        }
      }
      diagnostics_.set_parser_counters(
        serial_parser_.total_frames(),
        serial_parser_.crc_errors(),
        serial_parser_.resync_count());
    } catch (const std::exception & error) {
      diagnostics_.set_serial_open(false);
      diagnostics_.record_error(error.what());
      RCLCPP_WARN(get_logger(), "serial read failed: %s", error.what());
    }
  }

  uint16_t device_id_{};
  std::string frame_id_;
  std::string input_path_;
  std::string serial_port_path_;
  int baud_rate_{12000000};
  int read_chunk_size_{4096};
  bool publish_raw_{true};
  int startup_delay_ms_{1000};
  int replay_count_{1};
  int replay_index_{0};
  uint64_t file_total_frames_{};
  uint64_t file_crc_errors_{};
  uint64_t file_resync_count_{};
  tg0_multipad_driver::AddaFrameParser serial_parser_;
  tg0_multipad_driver::RawStreamDiagnostics diagnostics_;
  std::unique_ptr<tg0_multipad_driver::SerialPort> serial_port_;
  rclcpp::Publisher<tg0_multipad_msgs::msg::RawFrame>::SharedPtr raw_publisher_;
  rclcpp::Publisher<diagnostic_msgs::msg::DiagnosticArray>::SharedPtr diagnostics_publisher_;
  rclcpp::TimerBase::SharedPtr publish_timer_;
  rclcpp::TimerBase::SharedPtr serial_timer_;
  rclcpp::TimerBase::SharedPtr diagnostics_timer_;
};

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<RawFramePublisherNode>());
  rclcpp::shutdown();
  return 0;
}
