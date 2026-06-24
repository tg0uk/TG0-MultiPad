#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>

namespace tg0_multipad_driver {

struct AddaFrame {
  std::array<int16_t, 4> data{};
  uint16_t crc{};
  uint16_t tag{};
  int16_t encoded_tag{};
  bool marker_valid{};
};

uint16_t crc16_xmodem(const uint8_t * bytes, std::size_t size);
uint16_t crc16_xmodem(const std::vector<uint8_t> & bytes);

class AddaFrameParser {
public:
  void push_bytes(const std::vector<uint8_t> & bytes);
  std::optional<AddaFrame> next_frame();

  uint64_t total_frames() const;
  uint64_t crc_errors() const;
  uint64_t resync_count() const;

private:
  std::vector<uint8_t> buffer_;
  uint64_t total_frames_{};
  uint64_t crc_errors_{};
  uint64_t resync_count_{};
  uint64_t consecutive_crc_errors_{};
};

}  // namespace tg0_multipad_driver
