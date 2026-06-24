# TG0 Multipad ROS Driver

ROS 2 Humble driver and message package for TG0 multipad RAW sensor streams.

This release provides protocol-level access to the hardware stream. It decodes
validated ADDA frames and publishes them as ROS messages so customers can build
their own topology mapping, calibration, filtering, and application logic on top
of the RAW data.

## Supported Environment

This release is developed and validated with:

- Ubuntu 22.04 LTS
- ROS 2 Humble Hawksbill
- Linux x86_64 development environments
- NVIDIA Jetson running Ubuntu-based Linux with ROS 2 Humble
- `colcon` build system

`rqt_plot` is only required for the optional visualization example. Other Ubuntu
or ROS 2 versions are outside the validated release scope.

## Packages

- `tg0_multipad_msgs`: ROS interfaces for TG0 multipad streams.
- `tg0_multipad_driver`: RAW frame parser, serial/file publisher, diagnostics,
  and visualization examples.

## Current Scope

Included:

- RAW ADDA frame parsing with CRC-16/XMODEM validation.
- Live Linux serial input, including Jetson serial devices.
- Optional binary file replay for offline parser validation.
- ROS topic publication on `/tg0/multipad/raw`.
- Runtime health publication on `/diagnostics`.
- `rqt_plot` visualization examples for RAW payload channels.

Not included in this phase:

- Product-specific topology mapping.
- Calibration, tare, or filtering algorithms.
- Aggregate application-level messages such as `MultipadArray`.
- Hardware serial number reporting. Use the configurable `device_id` parameter
  as a software-side identifier for now.

## Frame Format

Each hardware frame is 10 bytes:

```text
Octet 0..1   Encoded tag word, little-endian int16
Octet 2..3   Data 1, little-endian int16
Octet 4..5   Data 2, little-endian int16
Octet 6..7   Data 3, little-endian int16
Octet 8..9   CRC-16/XMODEM bytes as transmitted
```

The encoded tag word contains a marker bit and routing tag:

```text
marker_valid = (encoded_tag & 1) == 1
tag          = encoded_tag >> 1
```

After decoding, `data[0]` in the ROS message contains the decoded `tag` value.
The sensor payload values are `data[1]`, `data[2]`, and `data[3]`.

CRC settings:

- Polynomial: `0x1021`
- Initial value: `0x0000`
- RefIn / RefOut: false
- XorOut: `0x0000`

## Build

From the ROS workspace root:

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

Optional package-level test run:

```bash
colcon test --packages-select tg0_multipad_driver tg0_multipad_msgs
colcon test-result --verbose
```

## Run the RAW Publisher

For live hardware on Linux or Jetson, pass the serial device path exposed by
the operating system:

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_publisher --ros-args \
  -p serial_port:=/dev/ttyUSB0 \
  -p baud_rate:=12000000 \
  -p device_id:=0 \
  -p frame_id:=tg0_multipad_link
```

The node publishes RAW frames on:

```text
/tg0/multipad/raw
```

This is a high-rate sensor stream and uses ROS `SensorDataQoS`. Subscribers that
inspect the topic from the terminal should request best-effort reliability:

```bash
ros2 topic echo /tg0/multipad/raw --qos-reliability best_effort
```

For offline replay from a binary frame capture:

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_publisher --ros-args \
  -p input_path:=/path/to/raw_capture.bin \
  -p replay_count:=1 \
  -p device_id:=0
```

## RAW Message

`/tg0/multipad/raw` uses `tg0_multipad_msgs/msg/RawFrame`:

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

Field notes:

- `device_id`: software-side device identifier from the ROS parameter.
- `tag`: decoded routing tag, using zero-based naming (`tag0`, `tag1`, ...).
- `encoded_tag`: original encoded tag word from the hardware frame.
- `data[0]`: decoded tag value for compatibility with the raw word layout.
- `data[1]`, `data[2]`, `data[3]`: sensor payload values.
- `crc`: transmitted CRC value.
- `crc_valid`: true for frames published by this driver.
- `device_timestamp_ms`: reserved for future hardware timestamp support.

## Visualization With rqt_plot

Plotting the high-rate `RawFrame` message directly can be heavy. The driver
therefore includes an example bridge that republishes downsampled scalar topics
for `rqt_plot`.

Start the RAW publisher first, then run the plot-channel bridge:

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_plot_channels --ros-args \
  -p publish_hz:=20.0
```

The bridge publishes payload-only scalar topics:

```text
/tg0/multipad/raw_plot/tag<N>/data1
/tg0/multipad/raw_plot/tag<N>/data2
/tg0/multipad/raw_plot/tag<N>/data3
```

Open `rqt_plot` for the default first tag (`tag0`):

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_plot
```

Select a specific tag:

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_plot --tag 0
```

Plot multiple connected tags:

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_plot --tag 0 --tag 3
```

Only plot tags that are connected to sensors. Unconnected tags can show idle
electrical noise and make the graph look misleading.

On Jetson, run `rqt_plot` from a desktop session or a container with access to
the local display. If Qt cannot open the display from a container, allow local
container access to X11 before starting the ROS container:

```bash
xhost +local:root
```

## Diagnostics

The RAW publisher also reports runtime health on:

```text
/diagnostics
```

The status name is:

```text
tg0_multipad/raw_stream
```

Common diagnostic fields include:

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

Inspect diagnostics with:

```bash
ros2 topic echo /diagnostics
```

For long stability runs, avoid unnecessary full-rate RAW subscribers. If only
driver health is needed, disable RAW publication and monitor diagnostics:

```bash
ros2 run tg0_multipad_driver tg0_multipad_raw_publisher --ros-args \
  -p serial_port:=/dev/ttyUSB0 \
  -p baud_rate:=12000000 \
  -p publish_raw:=false
```

## Publisher Parameters

`tg0_multipad_raw_publisher` parameters:

- `device_id` (`int`, default `0`)
- `frame_id` (`string`, default `tg0_multipad_link`)
- `input_path` (`string`, default empty)
- `serial_port` (`string`, default empty)
- `baud_rate` (`int`, default `12000000`)
- `read_chunk_size` (`int`, default `4096`; values below `1` are clamped)
- `publish_raw` (`bool`, default `true`)
- `startup_delay_ms` (`int`, default `1000`)
- `replay_count` (`int`, default `1`; values `<= 0` repeat until shutdown)

`tg0_multipad_raw_plot_channels` parameters:

- `input_topic` (`string`, default `/tg0/multipad/raw`)
- `output_prefix` (`string`, default `/tg0/multipad/raw_plot`)
- `publish_hz` (`double`, default `20.0`)
- `tag_count` (`int`, default `8`)

## Integration Guidance

Use `/tg0/multipad/raw` as the stable protocol-level integration point. Customer
applications can subscribe to RAW frames and implement their own mapping from
`tag` and payload values to product-specific sensor positions, gestures,
calibration models, or control logic.

The driver deliberately keeps the ROS API close to the hardware frame so later
topology and calibration layers can be added without changing the underlying
RAW stream.
