#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace tg0_multipad_driver {

class SerialPort {
public:
  SerialPort(std::string path, int baud_rate);
  ~SerialPort();

  SerialPort(const SerialPort &) = delete;
  SerialPort & operator=(const SerialPort &) = delete;

  SerialPort(SerialPort && other) noexcept;
  SerialPort & operator=(SerialPort && other) noexcept;

  std::vector<uint8_t> read_available(std::size_t max_bytes);
  int configured_baud_rate() const;

private:
  void close_if_open() noexcept;

  int fd_{-1};
};

}  // namespace tg0_multipad_driver
