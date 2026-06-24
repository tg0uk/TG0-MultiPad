#ifndef TG0_MULTIPAD_DRIVER__RAW_STREAM_DIAGNOSTICS_HPP_
#define TG0_MULTIPAD_DRIVER__RAW_STREAM_DIAGNOSTICS_HPP_

#include "diagnostic_msgs/msg/diagnostic_status.hpp"

#include <cstdint>
#include <string>

namespace tg0_multipad_driver {

class RawStreamDiagnostics
{
public:
  void configure(const std::string & input_mode, const std::string & input_path);
  void set_serial_open(bool open);
  void set_raw_publish_enabled(bool enabled);
  void record_bytes(uint64_t bytes, double timestamp_seconds = 0.0);
  void record_sample(double timestamp_seconds);
  void set_parser_counters(uint64_t total_frames, uint64_t crc_errors, uint64_t resync_count);
  void record_error(const std::string & text);
  void clear_error();

  diagnostic_msgs::msg::DiagnosticStatus make_status(double now_seconds) const;

private:
  std::string input_mode_{"idle"};
  std::string input_path_;
  bool serial_open_{false};
  bool publish_raw_{true};
  uint64_t total_frames_{};
  uint64_t crc_errors_{};
  uint64_t resync_count_{};
  uint64_t sample_count_{};
  uint64_t total_bytes_{};
  double first_activity_time_seconds_{-1.0};
  double last_frame_time_seconds_{-1.0};
  std::string last_error_text_;
};

}  // namespace tg0_multipad_driver

#endif  // TG0_MULTIPAD_DRIVER__RAW_STREAM_DIAGNOSTICS_HPP_
