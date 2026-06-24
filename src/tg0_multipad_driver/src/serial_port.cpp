#include "tg0_multipad_driver/serial_port.hpp"

#include <asm/ioctls.h>
#include <asm/termbits.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <cstring>
#include <stdexcept>
#include <utility>

namespace tg0_multipad_driver {

namespace {

std::runtime_error system_error(const std::string & message)
{
  return std::runtime_error(message + ": " + std::strerror(errno));
}

void configure_raw_serial(const int fd, const int baud_rate)
{
  termios2 tty{};
  if (ioctl(fd, TCGETS2, &tty) != 0) {
    throw system_error("ioctl(TCGETS2) failed");
  }

  tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
  tty.c_iflag = 0;
  tty.c_lflag = 0;
  tty.c_oflag = 0;
  tty.c_cc[VMIN] = 0;
  tty.c_cc[VTIME] = 0;
  tty.c_cflag |= CLOCAL | CREAD;
  tty.c_cflag &= ~(PARENB | PARODD);
  tty.c_cflag &= ~CSTOPB;
  tty.c_cflag &= ~CRTSCTS;
  tty.c_cflag &= ~CBAUD;
  tty.c_cflag |= BOTHER;
  tty.c_ispeed = baud_rate;
  tty.c_ospeed = baud_rate;

  if (ioctl(fd, TCSETS2, &tty) != 0) {
    throw system_error("ioctl(TCSETS2) failed");
  }
}

}  // namespace

SerialPort::SerialPort(std::string path, const int baud_rate)
{
  fd_ = open(path.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (fd_ < 0) {
    throw system_error("failed to open serial port " + path);
  }

  try {
    configure_raw_serial(fd_, baud_rate);
  } catch (...) {
    close_if_open();
    throw;
  }
}

SerialPort::~SerialPort()
{
  close_if_open();
}

SerialPort::SerialPort(SerialPort && other) noexcept
: fd_(std::exchange(other.fd_, -1))
{
}

SerialPort & SerialPort::operator=(SerialPort && other) noexcept
{
  if (this != &other) {
    close_if_open();
    fd_ = std::exchange(other.fd_, -1);
  }
  return *this;
}

std::vector<uint8_t> SerialPort::read_available(const std::size_t max_bytes)
{
  std::vector<uint8_t> bytes(max_bytes);
  const auto count = read(fd_, bytes.data(), bytes.size());
  if (count > 0) {
    bytes.resize(static_cast<std::size_t>(count));
    return bytes;
  }

  if (count == 0 || errno == EAGAIN || errno == EWOULDBLOCK) {
    return {};
  }

  throw system_error("serial read failed");
}

int SerialPort::configured_baud_rate() const
{
  termios2 tty{};
  if (ioctl(fd_, TCGETS2, &tty) != 0) {
    throw system_error("ioctl(TCGETS2) failed");
  }
  return tty.c_ispeed;
}

void SerialPort::close_if_open() noexcept
{
  if (fd_ >= 0) {
    close(fd_);
    fd_ = -1;
  }
}

}  // namespace tg0_multipad_driver
