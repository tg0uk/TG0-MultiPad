#include "tg0_multipad_driver/raw_frame_message.hpp"

namespace tg0_multipad_driver {

tg0_multipad_msgs::msg::RawFrame make_raw_frame_message(
  const AddaFrame & frame,
  uint16_t device_id,
  const std::string & frame_id,
  const builtin_interfaces::msg::Time & stamp)
{
  tg0_multipad_msgs::msg::RawFrame message;
  message.header.stamp = stamp;
  message.header.frame_id = frame_id;
  message.device_id = device_id;
  message.tag = frame.tag;
  message.encoded_tag = frame.encoded_tag;
  message.data = frame.data;
  message.crc = frame.crc;
  message.crc_valid = true;
  message.device_timestamp_ms = 0;
  return message;
}

}  // namespace tg0_multipad_driver
