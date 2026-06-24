#include "tg0_multipad_driver/raw_frame_message.hpp"

#include <gtest/gtest.h>

TEST(RawFrameMessageTest, MapsParsedFrameToRosMessage)
{
  tg0_multipad_driver::AddaFrame frame;
  frame.data = {2, -100, 200, 8800};
  frame.crc = 0xee3b;
  frame.tag = 2;
  frame.encoded_tag = 5;
  frame.marker_valid = true;

  builtin_interfaces::msg::Time stamp;
  stamp.sec = 123;
  stamp.nanosec = 456;

  const auto msg = tg0_multipad_driver::make_raw_frame_message(
    frame,
    7,
    "file_multipad_link",
    stamp);

  EXPECT_EQ(msg.header.stamp.sec, 123);
  EXPECT_EQ(msg.header.stamp.nanosec, 456U);
  EXPECT_EQ(msg.header.frame_id, "file_multipad_link");
  EXPECT_EQ(msg.device_id, 7);
  EXPECT_EQ(msg.tag, 2);
  EXPECT_EQ(msg.encoded_tag, 5);
  EXPECT_EQ(msg.data[0], 2);
  EXPECT_EQ(msg.data[1], -100);
  EXPECT_EQ(msg.data[2], 200);
  EXPECT_EQ(msg.data[3], 8800);
  EXPECT_EQ(msg.crc, 0xee3b);
  EXPECT_TRUE(msg.crc_valid);
  EXPECT_EQ(msg.device_timestamp_ms, 0U);
}
