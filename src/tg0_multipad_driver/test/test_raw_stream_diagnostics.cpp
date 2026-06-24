#include "tg0_multipad_driver/raw_stream_diagnostics.hpp"

#include "diagnostic_msgs/msg/diagnostic_status.hpp"

#include <gtest/gtest.h>

#include <string>

namespace {

const diagnostic_msgs::msg::KeyValue * find_value(
  const diagnostic_msgs::msg::DiagnosticStatus & status,
  const std::string & key)
{
  for (const auto & value : status.values) {
    if (value.key == key) {
      return &value;
    }
  }
  return nullptr;
}

std::string value_for(
  const diagnostic_msgs::msg::DiagnosticStatus & status,
  const std::string & key)
{
  const auto * value = find_value(status, key);
  return value == nullptr ? "" : value->value;
}

}  // namespace

TEST(RawStreamDiagnosticsTest, ReportsNominalRuntimeCounters)
{
  tg0_multipad_driver::RawStreamDiagnostics diagnostics;
  diagnostics.configure("serial", "/dev/ttyUSB0");
  diagnostics.set_serial_open(true);
  diagnostics.set_raw_publish_enabled(false);
  diagnostics.record_bytes(2048);
  diagnostics.record_sample(100.0);
  diagnostics.record_sample(100.5);
  diagnostics.set_parser_counters(2, 1, 3);

  const auto status = diagnostics.make_status(101.0);

  EXPECT_EQ(status.name, "tg0_multipad/raw_stream");
  EXPECT_EQ(status.hardware_id, "/dev/ttyUSB0");
  EXPECT_EQ(status.level, diagnostic_msgs::msg::DiagnosticStatus::OK);
  EXPECT_EQ(status.message, "running");
  EXPECT_EQ(value_for(status, "input_mode"), "serial");
  EXPECT_EQ(value_for(status, "input_path"), "/dev/ttyUSB0");
  EXPECT_EQ(value_for(status, "serial_open"), "true");
  EXPECT_EQ(value_for(status, "publish_raw"), "false");
  EXPECT_EQ(value_for(status, "total_frames"), "2");
  EXPECT_EQ(value_for(status, "crc_errors"), "1");
  EXPECT_EQ(value_for(status, "resync_count"), "3");
  EXPECT_EQ(value_for(status, "sample_count"), "2");
  EXPECT_EQ(value_for(status, "total_bytes"), "2048");
  EXPECT_EQ(value_for(status, "last_frame_age_ms"), "500");
  EXPECT_EQ(value_for(status, "last_error_text"), "");
  EXPECT_NE(find_value(status, "frame_rate_hz"), nullptr);
  EXPECT_NE(find_value(status, "bytes_per_sec"), nullptr);
}

TEST(RawStreamDiagnosticsTest, WarnsWhenStreamIsStale)
{
  tg0_multipad_driver::RawStreamDiagnostics diagnostics;
  diagnostics.configure("serial", "/dev/ttyUSB0");
  diagnostics.set_serial_open(true);
  diagnostics.record_sample(10.0);

  const auto status = diagnostics.make_status(12.5);

  EXPECT_EQ(status.level, diagnostic_msgs::msg::DiagnosticStatus::WARN);
  EXPECT_EQ(status.message, "stale stream");
  EXPECT_EQ(value_for(status, "last_frame_age_ms"), "2500");
}

TEST(RawStreamDiagnosticsTest, WarnsWhenInputModeIsIdle)
{
  tg0_multipad_driver::RawStreamDiagnostics diagnostics;
  diagnostics.configure("idle", "");

  const auto status = diagnostics.make_status(42.0);

  EXPECT_EQ(status.level, diagnostic_msgs::msg::DiagnosticStatus::WARN);
  EXPECT_EQ(status.message, "idle: set input_path or serial_port");
  EXPECT_EQ(status.hardware_id, "unknown");
  EXPECT_EQ(value_for(status, "input_mode"), "idle");
  EXPECT_EQ(value_for(status, "serial_open"), "false");
}

TEST(RawStreamDiagnosticsTest, ReportsSerialErrors)
{
  tg0_multipad_driver::RawStreamDiagnostics diagnostics;
  diagnostics.configure("serial", "/dev/ttyUSB0");
  diagnostics.set_serial_open(false);
  diagnostics.record_error("serial read failed");

  const auto status = diagnostics.make_status(42.0);

  EXPECT_EQ(status.level, diagnostic_msgs::msg::DiagnosticStatus::ERROR);
  EXPECT_EQ(status.message, "serial error");
  EXPECT_EQ(value_for(status, "serial_open"), "false");
  EXPECT_EQ(value_for(status, "last_error_text"), "serial read failed");
}
