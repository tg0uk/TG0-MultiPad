#include "tg0_multipad_driver/adda_frame_parser.hpp"

#include <algorithm>

namespace tg0_multipad_driver {

namespace {

constexpr std::size_t kFrameSize = 10;
constexpr uint64_t kCrcErrorsBeforeResync = 16;

int16_t read_int16_le(const uint8_t low, const uint8_t high)
{
  const auto value = static_cast<uint16_t>(low) | (static_cast<uint16_t>(high) << 8);
  return static_cast<int16_t>(value);
}

uint16_t read_uint16_be(const uint8_t high, const uint8_t low)
{
  return static_cast<uint16_t>((static_cast<uint16_t>(high) << 8) | static_cast<uint16_t>(low));
}

AddaFrame decode_frame(const std::vector<uint8_t> & bytes)
{
  AddaFrame frame;
  frame.data = {
    read_int16_le(bytes[0], bytes[1]),
    read_int16_le(bytes[2], bytes[3]),
    read_int16_le(bytes[4], bytes[5]),
    read_int16_le(bytes[6], bytes[7]),
  };
  frame.crc = read_uint16_be(bytes[8], bytes[9]);
  frame.encoded_tag = frame.data[0];
  frame.tag = static_cast<uint16_t>(frame.encoded_tag >> 1);
  frame.marker_valid = (frame.encoded_tag & 1) == 1;
  frame.data[0] = static_cast<int16_t>(frame.encoded_tag >> 1);
  return frame;
}

}  // namespace

uint16_t crc16_xmodem(const uint8_t * bytes, std::size_t size)
{
  uint16_t crc = 0;
  for (std::size_t i = 0; i < size; ++i) {
    crc ^= static_cast<uint16_t>(bytes[i]) << 8;
    for (int bit = 0; bit < 8; ++bit) {
      if ((crc & 0x8000) != 0) {
        crc = static_cast<uint16_t>((crc << 1) ^ 0x1021);
      } else {
        crc = static_cast<uint16_t>(crc << 1);
      }
    }
  }
  return crc;
}

uint16_t crc16_xmodem(const std::vector<uint8_t> & bytes)
{
  return crc16_xmodem(bytes.data(), bytes.size());
}

void AddaFrameParser::push_bytes(const std::vector<uint8_t> & bytes)
{
  buffer_.insert(buffer_.end(), bytes.begin(), bytes.end());
}

std::optional<AddaFrame> AddaFrameParser::next_frame()
{
  while (buffer_.size() >= kFrameSize) {
    std::vector<uint8_t> candidate(buffer_.begin(), buffer_.begin() + kFrameSize);
    const auto frame = decode_frame(candidate);

    if (!frame.marker_valid) {
      buffer_.erase(buffer_.begin());
      consecutive_crc_errors_ = 0;
      ++resync_count_;
      continue;
    }

    if (crc16_xmodem(candidate) == 0) {
      buffer_.erase(buffer_.begin(), buffer_.begin() + kFrameSize);
      consecutive_crc_errors_ = 0;
      ++total_frames_;
      return frame;
    }

    ++crc_errors_;
    ++consecutive_crc_errors_;
    if (consecutive_crc_errors_ >= kCrcErrorsBeforeResync) {
      buffer_.erase(buffer_.begin());
      consecutive_crc_errors_ = 0;
      ++resync_count_;
    } else {
      buffer_.erase(buffer_.begin(), buffer_.begin() + kFrameSize);
    }
  }

  return std::nullopt;
}

uint64_t AddaFrameParser::total_frames() const
{
  return total_frames_;
}

uint64_t AddaFrameParser::crc_errors() const
{
  return crc_errors_;
}

uint64_t AddaFrameParser::resync_count() const
{
  return resync_count_;
}

}  // namespace tg0_multipad_driver
