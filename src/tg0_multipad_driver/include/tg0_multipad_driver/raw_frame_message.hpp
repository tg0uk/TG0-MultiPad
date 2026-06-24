#pragma once

#include "tg0_multipad_driver/adda_frame_parser.hpp"

#include "builtin_interfaces/msg/time.hpp"
#include "tg0_multipad_msgs/msg/raw_frame.hpp"

#include <cstdint>
#include <string>

namespace tg0_multipad_driver {

tg0_multipad_msgs::msg::RawFrame make_raw_frame_message(
  const AddaFrame & frame,
  uint16_t device_id,
  const std::string & frame_id,
  const builtin_interfaces::msg::Time & stamp);

}  // namespace tg0_multipad_driver

