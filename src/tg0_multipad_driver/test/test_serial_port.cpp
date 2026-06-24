#include "tg0_multipad_driver/serial_port.hpp"

#include <gtest/gtest.h>

#include <pty.h>
#include <unistd.h>

#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

class PseudoTerminal {
public:
  PseudoTerminal()
  {
    std::array<char, 128> name{};
    if (openpty(&master_fd_, &slave_fd_, name.data(), nullptr, nullptr) != 0) {
      throw std::runtime_error("openpty failed");
    }
    slave_path_ = name.data();
  }

  ~PseudoTerminal()
  {
    if (master_fd_ >= 0) {
      close(master_fd_);
    }
    if (slave_fd_ >= 0) {
      close(slave_fd_);
    }
  }

  PseudoTerminal(const PseudoTerminal &) = delete;
  PseudoTerminal & operator=(const PseudoTerminal &) = delete;

  int master_fd() const { return master_fd_; }
  const std::string & slave_path() const { return slave_path_; }

  void close_initial_slave()
  {
    if (slave_fd_ >= 0) {
      close(slave_fd_);
      slave_fd_ = -1;
    }
  }

private:
  int master_fd_{-1};
  int slave_fd_{-1};
  std::string slave_path_;
};

std::vector<uint8_t> read_until_bytes(
  tg0_multipad_driver::SerialPort & serial,
  const std::size_t expected_count)
{
  std::vector<uint8_t> bytes;
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);

  while (bytes.size() < expected_count && std::chrono::steady_clock::now() < deadline) {
    auto chunk = serial.read_available(64);
    bytes.insert(bytes.end(), chunk.begin(), chunk.end());
    if (bytes.size() < expected_count) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
  }

  return bytes;
}

}  // namespace

TEST(SerialPortTest, ConfiguresTwelveMegabaudOnPseudoTerminal)
{
  PseudoTerminal pty;
  pty.close_initial_slave();

  tg0_multipad_driver::SerialPort serial(pty.slave_path(), 12000000);

  EXPECT_EQ(serial.configured_baud_rate(), 12000000);
}

TEST(SerialPortTest, ReadsBytesWrittenToPseudoTerminal)
{
  PseudoTerminal pty;
  pty.close_initial_slave();
  tg0_multipad_driver::SerialPort serial(pty.slave_path(), 12000000);

  const std::vector<uint8_t> expected{0x05, 0x00, 0x9c, 0xff, 0xc8, 0x00};
  ASSERT_EQ(write(pty.master_fd(), expected.data(), expected.size()), static_cast<ssize_t>(expected.size()));

  const auto actual = read_until_bytes(serial, expected.size());

  EXPECT_EQ(actual, expected);
}
