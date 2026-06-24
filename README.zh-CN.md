<div align="center">
  <img src="assets/tg0-logo.png" alt="TG0" width="220">

  <h1>TG0 MultiPad ROS Driver</h1>

  <p>
    面向 TG0 MultiPad 传感器的 ROS 2 RAW 数据驱动与可视化示例。
  </p>

  <p>
    <img alt="ROS 2 Humble" src="https://img.shields.io/badge/ROS%202-Humble-22314E">
    <img alt="Ubuntu 22.04" src="https://img.shields.io/badge/Ubuntu-22.04%20LTS-E95420">
    <img alt="Jetson" src="https://img.shields.io/badge/NVIDIA-Jetson-76B900">
    <img alt="Status" src="https://img.shields.io/badge/status-RAW%20driver%20ready-2E7D32">
  </p>

  <p>
    <a href="README.md">English</a> | <a href="README.zh-CN.md">中文</a>
  </p>
</div>

---

## 概览

TG0 MultiPad ROS Driver 提供 TG0 MultiPad RAW 传感器数据流的协议层访问能力。
驱动会解析通过 CRC 校验的 ADDA frame，并将其发布为 ROS 2 message，方便集成方
在 RAW 数据之上实现自己的拓扑映射、标定、滤波和应用逻辑。

当前版本刻意保持接近硬件协议层。它适合作为稳定的 ROS 数据入口，同时保留客户
对产品级传感器映射和信号处理的自主实现空间。

## 支持环境

当前版本开发和验证环境如下：

- Ubuntu 22.04 LTS
- ROS 2 Humble Hawksbill
- Linux x86_64 开发环境
- 运行 Ubuntu 系 Linux 与 ROS 2 Humble 的 NVIDIA Jetson
- `colcon` 构建系统

`rqt_plot` 只用于可选的可视化示例。其他 Ubuntu 或 ROS 2 版本不在当前验证范围内。

## 仓库结构

```text
.
├── assets/
│   └── tg0-logo.png
├── scripts/
│   └── 验证和硬件 bring-up 辅助脚本
└── src/
    ├── tg0_multipad_driver/
    │   ├── examples/
    │   ├── include/
    │   ├── src/
    │   └── test/
    └── tg0_multipad_msgs/
        └── msg/RawFrame.msg
```

## ROS 包

- `tg0_multipad_msgs`：TG0 MultiPad 数据流的 ROS interface。
- `tg0_multipad_driver`：RAW frame 解析、串口/文件发布、diagnostics 与可视化示例。

## 当前范围

已包含：

- RAW ADDA frame 解析与 CRC-16/XMODEM 校验。
- Linux 串口输入，包括 Jetson 上的串口设备。
- 用于离线解析验证的二进制文件 replay。
- 通过 `/tg0/multipad/raw` 发布 ROS topic。
- 通过 `/diagnostics` 发布运行状态。
- 面向 RAW payload channel 的 `rqt_plot` 可视化示例。

当前阶段不包含：

- 产品相关的 topology mapping。
- calibration、tare 或滤波算法。
- `MultipadArray` 这类上层聚合 message。
- 硬件序列号读取。当前可使用 `device_id` 参数作为软件侧设备标识。

## Frame 格式

每个硬件 frame 长度为 10 bytes：

```text
Octet 0..1   Encoded tag word, little-endian int16
Octet 2..3   Data 1, little-endian int16
Octet 4..5   Data 2, little-endian int16
Octet 6..7   Data 3, little-endian int16
Octet 8..9   CRC-16/XMODEM bytes as transmitted
```

encoded tag word 包含 marker bit 与 routing tag：

```text
marker_valid = (encoded_tag & 1) == 1
tag          = encoded_tag >> 1
```

解码后，ROS message 中的 `data[0]` 保存解码后的 `tag` 值。真正的传感器 payload
为 `data[1]`、`data[2]` 和 `data[3]`。

CRC 设置：

- Polynomial: `0x1021`
- Initial value: `0x0000`
- RefIn / RefOut: false
- XorOut: `0x0000`

## 构建

在 ROS workspace 根目录执行：

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

可选的 package 测试：

```bash
colcon test --packages-select tg0_multipad_driver tg0_multipad_msgs
colcon test-result --verbose
```

## 启动 RAW Publisher

在 Linux 或 Jetson 硬件上运行时，传入系统暴露出的串口路径：

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_publisher --ros-args \
  -p serial_port:=/dev/ttyUSB0 \
  -p baud_rate:=12000000 \
  -p device_id:=0 \
  -p frame_id:=tg0_multipad_link
```

节点会发布 RAW frame 到：

```text
/tg0/multipad/raw
```

这是一个高频传感器数据流，使用 ROS `SensorDataQoS`。如果通过终端查看 topic，
需要使用 best-effort reliability：

```bash
ros2 topic echo /tg0/multipad/raw --qos-reliability best_effort
```

如需从二进制 frame capture 文件离线 replay：

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_publisher --ros-args \
  -p input_path:=/path/to/raw_capture.bin \
  -p replay_count:=1 \
  -p device_id:=0
```

## RAW Message

`/tg0/multipad/raw` 使用 `tg0_multipad_msgs/msg/RawFrame`：

```text
std_msgs/Header header
uint16 device_id
uint16 tag
int16 encoded_tag
int16[4] data
uint16 crc
bool crc_valid
uint64 device_timestamp_ms
```

字段说明：

- `device_id`：来自 ROS 参数的软件侧设备标识。
- `tag`：解码后的 routing tag，采用从 0 开始的命名方式，例如 `tag0`、`tag1`。
- `encoded_tag`：硬件 frame 中的原始 encoded tag word。
- `data[0]`：解码后的 tag 值，用于保留 raw word layout 的兼容性。
- `data[1]`、`data[2]`、`data[3]`：传感器 payload 数值。
- `crc`：frame 中传输的 CRC 值。
- `crc_valid`：由本驱动发布的 frame 为 true。
- `device_timestamp_ms`：预留给未来硬件 timestamp 支持。

## 使用 rqt_plot 可视化

直接绘制高频 `RawFrame` message 可能比较重。本驱动提供了一个 example bridge，
将 RAW payload 以降频后的 scalar topic 重新发布，方便使用 `rqt_plot` 查看。

先启动 RAW publisher，然后启动 plot-channel bridge：

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_plot_channels --ros-args \
  -p publish_hz:=20.0
```

bridge 会发布只包含 payload 的 scalar topic：

```text
/tg0/multipad/raw_plot/tag<N>/data1
/tg0/multipad/raw_plot/tag<N>/data2
/tg0/multipad/raw_plot/tag<N>/data3
```

打开默认第一路 tag，即 `tag0`：

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_plot
```

指定某一路 tag：

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_plot --tag 0
```

同时绘制多个已连接 tag：

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_plot --tag 0 --tag 3
```

建议只绘制实际连接传感器的 tag。未连接的 tag 可能出现空载电噪声，容易误导观察。

在 Jetson 上使用 `rqt_plot` 时，需要从桌面会话启动，或确保容器能访问本地显示。
如果容器内 Qt 无法打开 display，可在启动 ROS 容器前允许本地容器访问 X11：

```bash
xhost +local:root
```

## Diagnostics

RAW publisher 会在以下 topic 发布运行状态：

```text
/diagnostics
```

status name 为：

```text
tg0_multipad/raw_stream
```

常用 diagnostics 字段包括：

- `input_mode`
- `input_path`
- `serial_open`
- `publish_raw`
- `total_frames`
- `crc_errors`
- `resync_count`
- `sample_count`
- `total_bytes`
- `frame_rate_hz`
- `bytes_per_sec`
- `last_frame_age_ms`
- `last_error_text`

查看 diagnostics：

```bash
ros2 topic echo /diagnostics
```

长时间稳定性观察时，应避免不必要的全速 RAW subscriber。如果只需要查看驱动健康
状态，可以关闭 RAW 发布，只监控 diagnostics：

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_publisher --ros-args \
  -p serial_port:=/dev/ttyUSB0 \
  -p baud_rate:=12000000 \
  -p publish_raw:=false
```

## Publisher 参数

`tg0_multipad_raw_publisher` 参数：

- `device_id` (`int`, default `0`)
- `frame_id` (`string`, default `tg0_multipad_link`)
- `input_path` (`string`, default empty)
- `serial_port` (`string`, default empty)
- `baud_rate` (`int`, default `12000000`)
- `read_chunk_size` (`int`, default `4096`; 小于 `1` 时会被 clamp)
- `publish_raw` (`bool`, default `true`)
- `startup_delay_ms` (`int`, default `1000`)
- `replay_count` (`int`, default `1`; `<= 0` 时持续重复直到 shutdown)

`tg0_multipad_raw_plot_channels` 参数：

- `input_topic` (`string`, default `/tg0/multipad/raw`)
- `output_prefix` (`string`, default `/tg0/multipad/raw_plot`)
- `publish_hz` (`double`, default `20.0`)
- `tag_count` (`int`, default `8`)

## 集成建议

建议将 `/tg0/multipad/raw` 作为稳定的协议层集成入口。客户应用可以订阅 RAW frame，
并根据 `tag` 与 payload 值实现自己的传感器位置映射、手势逻辑、标定模型或控制逻辑。

驱动刻意保持 ROS API 接近硬件 frame。这样后续添加 topology 与 calibration 层时，
不需要改变底层 RAW stream。
