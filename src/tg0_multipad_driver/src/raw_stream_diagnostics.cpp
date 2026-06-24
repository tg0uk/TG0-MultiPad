#include "tg0_multipad_driver/raw_stream_diagnostics.hpp"

#include "diagnostic_msgs/msg/key_value.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <sstream>
#include <string>

namespace tg0_multipad_driver {

namespace {

diagnostic_msgs::msg::KeyValue key_value(const std::string & key, const std::string & value)
{
  diagnostic_msgs::msg::KeyValue item;
  item.key = key;
  item.value = value;
  return item;
}

std::string bool_string(bool value)
{
  return value ? "true" : "false";
}

std::string uint64_string(uint64_t value)
{
  return std::to_string(value);
}

std::string rate_string(double value)
{
  std::ostringstream stream;
  stream << std::fixed << std::setprecision(3) << value;
  return stream.str();
}

std::string age_ms_string(double now_seconds, double last_frame_time_seconds)
{
  if (last_frame_time_seconds < 0.0 || now_seconds < last_frame_time_seconds) {
    return "unknown";
  }

  const auto age_ms = static_cast<uint64_t>(
    std::llround((now_seconds - last_frame_time_seconds) * 1000.0));
  return std::to_string(age_ms);
}

}  // namespace

void RawStreamDiagnostics::configure(const std::string & input_mode, const std::string & input_path)
{
  input_mode_ = input_mode;
  input_path_ = input_path;
}

void RawStreamDiagnostics::set_serial_open(bool open)
{
  serial_open_ = open;
}

void RawStreamDiagnostics::set_raw_publish_enabled(bool enabled)
{
  publish_raw_ = enabled;
}

void RawStreamDiagnostics::record_bytes(uint64_t bytes, double timestamp_seconds)
{
  total_bytes_ += bytes;
  if (first_activity_time_seconds_ < 0.0) {
    first_activity_time_seconds_ = timestamp_seconds;
  }
}

void RawStreamDiagnostics::record_sample(double timestamp_seconds)
{
  ++sample_count_;
  last_frame_time_seconds_ = timestamp_seconds;
  if (first_activity_time_seconds_ < 0.0) {
    first_activity_time_seconds_ = timestamp_seconds;
  }
}

void RawStreamDiagnostics::set_parser_counters(
  uint64_t total_frames,
  uint64_t crc_errors,
  uint64_t resync_count)
{
  total_frames_ = total_frames;
  crc_errors_ = crc_errors;
  resync_count_ = resync_count;
}

void RawStreamDiagnostics::record_error(const std::string & text)
{
  last_error_text_ = text;
}

void RawStreamDiagnostics::clear_error()
{
  last_error_text_.clear();
}

diagnostic_msgs::msg::DiagnosticStatus RawStreamDiagnostics::make_status(double now_seconds) const
{
  diagnostic_msgs::msg::DiagnosticStatus status;
  status.name = "tg0_multipad/raw_stream";
  status.hardware_id = input_path_.empty() ? "unknown" : input_path_;

  const auto is_idle = input_mode_ == "idle";
  const auto has_error = !last_error_text_.empty() || (input_mode_ == "serial" && !serial_open_);
  const auto has_frame = last_frame_time_seconds_ >= 0.0;
  const auto frame_age_seconds = has_frame ? now_seconds - last_frame_time_seconds_ : 0.0;
  if (has_error) {
    status.level = diagnostic_msgs::msg::DiagnosticStatus::ERROR;
    status.message = "serial error";
  } else if (is_idle) {
    status.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
    status.message = "idle: set input_path or serial_port";
  } else if (has_frame && frame_age_seconds > 1.0) {
    status.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
    status.message = "stale stream";
  } else {
    status.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
    status.message = "running";
  }

  const auto elapsed_seconds = first_activity_time_seconds_ >= 0.0 ?
    std::max(0.0, now_seconds - first_activity_time_seconds_) :
    0.0;
  const auto frame_rate_hz = elapsed_seconds > 0.0 ?
    static_cast<double>(sample_count_) / elapsed_seconds :
    0.0;
  const auto bytes_per_sec = elapsed_seconds > 0.0 ?
    static_cast<double>(total_bytes_) / elapsed_seconds :
    0.0;

  status.values.push_back(key_value("input_mode", input_mode_));
  status.values.push_back(key_value("input_path", input_path_));
  status.values.push_back(key_value("serial_open", bool_string(serial_open_)));
  status.values.push_back(key_value("publish_raw", bool_string(publish_raw_)));
  status.values.push_back(key_value("total_frames", uint64_string(total_frames_)));
  status.values.push_back(key_value("crc_errors", uint64_string(crc_errors_)));
  status.values.push_back(key_value("resync_count", uint64_string(resync_count_)));
  status.values.push_back(key_value("sample_count", uint64_string(sample_count_)));
  status.values.push_back(key_value("total_bytes", uint64_string(total_bytes_)));
  status.values.push_back(key_value("frame_rate_hz", rate_string(frame_rate_hz)));
  status.values.push_back(key_value("bytes_per_sec", rate_string(bytes_per_sec)));
  status.values.push_back(key_value(
    "last_frame_age_ms",
    age_ms_string(now_seconds, last_frame_time_seconds_)));
  status.values.push_back(key_value("last_error_text", last_error_text_));

  return status;
}

}  // namespace tg0_multipad_driver
