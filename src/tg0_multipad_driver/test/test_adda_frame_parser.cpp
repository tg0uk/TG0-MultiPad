#include "tg0_multipad_driver/adda_frame_parser.hpp"

#include <gtest/gtest.h>

#include <cstdint>
#include <vector>

namespace {

std::vector<uint8_t> valid_frame()
{
  return {
    0x05, 0x00,  // encoded tag = 5
    0x9c, 0xff,  // x = -100
    0xc8, 0x00,  // y = 200
    0x60, 0x22,  // z = 8800
    0xee, 0x3b   // CRC-16/XMODEM, big-endian
  };
}

std::vector<uint8_t> frame_with_bad_crc()
{
  auto bytes = valid_frame();
  bytes[9] ^= 0x01;
  return bytes;
}

}  // namespace

TEST(Crc16XmodemTest, MatchesKnownCheckValue)
{
  const std::vector<uint8_t> bytes = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
  EXPECT_EQ(tg0_multipad_driver::crc16_xmodem(bytes), 0x31c3);
}

TEST(AddaFrameParserTest, ParsesValidTenByteFrame)
{
  tg0_multipad_driver::AddaFrameParser parser;
  parser.push_bytes(valid_frame());

  const auto frame = parser.next_frame();

  ASSERT_TRUE(frame.has_value());
  EXPECT_EQ(frame->encoded_tag, 5);
  EXPECT_EQ(frame->tag, 2);
  EXPECT_TRUE(frame->marker_valid);
  EXPECT_EQ(frame->data[0], 2);
  EXPECT_EQ(frame->data[1], -100);
  EXPECT_EQ(frame->data[2], 200);
  EXPECT_EQ(frame->data[3], 8800);
  EXPECT_EQ(frame->crc, 0xee3b);
  EXPECT_EQ(parser.total_frames(), 1U);
  EXPECT_EQ(parser.crc_errors(), 0U);
  EXPECT_EQ(parser.resync_count(), 0U);
}

TEST(AddaFrameParserTest, ParsesChunkedInput)
{
  tg0_multipad_driver::AddaFrameParser parser;
  const auto frame_bytes = valid_frame();
  parser.push_bytes({frame_bytes.begin(), frame_bytes.begin() + 3});
  EXPECT_FALSE(parser.next_frame().has_value());

  parser.push_bytes({frame_bytes.begin() + 3, frame_bytes.end()});
  const auto frame = parser.next_frame();

  ASSERT_TRUE(frame.has_value());
  EXPECT_EQ(frame->data[3], 8800);
}

TEST(AddaFrameParserTest, ParsesConcatenatedFrames)
{
  tg0_multipad_driver::AddaFrameParser parser;
  auto bytes = valid_frame();
  const auto second = valid_frame();
  bytes.insert(bytes.end(), second.begin(), second.end());

  parser.push_bytes(bytes);

  ASSERT_TRUE(parser.next_frame().has_value());
  ASSERT_TRUE(parser.next_frame().has_value());
  EXPECT_FALSE(parser.next_frame().has_value());
  EXPECT_EQ(parser.total_frames(), 2U);
}

TEST(AddaFrameParserTest, ResynchronizesAfterLeadingNoise)
{
  tg0_multipad_driver::AddaFrameParser parser;
  auto bytes = std::vector<uint8_t>{0xaa, 0xbc, 0xcc};
  const auto frame_bytes = valid_frame();
  bytes.insert(bytes.end(), frame_bytes.begin(), frame_bytes.end());

  parser.push_bytes(bytes);
  const auto frame = parser.next_frame();

  ASSERT_TRUE(frame.has_value());
  EXPECT_EQ(frame->tag, 2);
  EXPECT_EQ(parser.crc_errors(), 0U);
  EXPECT_EQ(parser.resync_count(), 3U);
}

TEST(AddaFrameParserTest, RejectsFrameWithBadCrc)
{
  tg0_multipad_driver::AddaFrameParser parser;
  auto bytes = frame_with_bad_crc();

  parser.push_bytes(bytes);

  EXPECT_FALSE(parser.next_frame().has_value());
  EXPECT_EQ(parser.total_frames(), 0U);
  EXPECT_EQ(parser.crc_errors(), 1U);
  EXPECT_EQ(parser.resync_count(), 0U);
}

TEST(AddaFrameParserTest, ResynchronizesWhenMarkerBitIsNotSet)
{
  tg0_multipad_driver::AddaFrameParser parser;
  auto bytes = std::vector<uint8_t>{0x00};
  const auto frame_bytes = valid_frame();
  bytes.insert(bytes.end(), frame_bytes.begin(), frame_bytes.end());

  parser.push_bytes(bytes);
  const auto frame = parser.next_frame();

  ASSERT_TRUE(frame.has_value());
  EXPECT_EQ(frame->encoded_tag, 5);
  EXPECT_TRUE(frame->marker_valid);
  EXPECT_EQ(parser.crc_errors(), 0U);
  EXPECT_EQ(parser.resync_count(), 1U);
}

TEST(AddaFrameParserTest, DoesNotResynchronizeBeforeSixteenConsecutiveCrcErrors)
{
  tg0_multipad_driver::AddaFrameParser parser;
  std::vector<uint8_t> bytes;
  for (int i = 0; i < 15; ++i) {
    const auto bad_frame = frame_with_bad_crc();
    bytes.insert(bytes.end(), bad_frame.begin(), bad_frame.end());
  }
  const auto frame_bytes = valid_frame();
  bytes.insert(bytes.end(), frame_bytes.begin(), frame_bytes.end());

  parser.push_bytes(bytes);
  const auto frame = parser.next_frame();

  ASSERT_TRUE(frame.has_value());
  EXPECT_EQ(frame->encoded_tag, 5);
  EXPECT_EQ(parser.crc_errors(), 15U);
  EXPECT_EQ(parser.resync_count(), 0U);
}

TEST(AddaFrameParserTest, ResynchronizesAfterSixteenConsecutiveCrcErrors)
{
  tg0_multipad_driver::AddaFrameParser parser;
  std::vector<uint8_t> bytes;
  for (int i = 0; i < 16; ++i) {
    const auto bad_frame = frame_with_bad_crc();
    bytes.insert(bytes.end(), bad_frame.begin(), bad_frame.end());
  }

  parser.push_bytes(bytes);

  EXPECT_FALSE(parser.next_frame().has_value());
  EXPECT_EQ(parser.total_frames(), 0U);
  EXPECT_EQ(parser.crc_errors(), 16U);
  EXPECT_EQ(parser.resync_count(), 1U);
}
