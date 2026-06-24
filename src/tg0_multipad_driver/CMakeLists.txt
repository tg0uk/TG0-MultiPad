cmake_minimum_required(VERSION 3.8)
project(tg0_multipad_driver)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_gtest REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(tg0_multipad_msgs REQUIRED)

add_library(adda_frame_parser
  src/adda_frame_parser.cpp
  src/raw_frame_message.cpp
)
target_include_directories(adda_frame_parser
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
ament_target_dependencies(adda_frame_parser
  builtin_interfaces
  tg0_multipad_msgs
)

add_library(serial_port
  src/serial_port.cpp
)
target_include_directories(serial_port
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

add_library(raw_stream_diagnostics
  src/raw_stream_diagnostics.cpp
)
target_include_directories(raw_stream_diagnostics
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
ament_target_dependencies(raw_stream_diagnostics
  diagnostic_msgs
)

add_executable(tg0_multipad_raw_publisher
  src/raw_frame_publisher_node.cpp
)
target_link_libraries(tg0_multipad_raw_publisher
  adda_frame_parser
  raw_stream_diagnostics
  serial_port
)
ament_target_dependencies(tg0_multipad_raw_publisher
  diagnostic_msgs
  rclcpp
  tg0_multipad_msgs
)

if(BUILD_TESTING)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)

  ament_add_gtest(test_adda_frame_parser
    test/test_adda_frame_parser.cpp
  )
  target_link_libraries(test_adda_frame_parser
    adda_frame_parser
  )

  ament_add_gtest(test_raw_frame_message
    test/test_raw_frame_message.cpp
  )
  target_link_libraries(test_raw_frame_message
    adda_frame_parser
  )
  ament_target_dependencies(test_raw_frame_message
    tg0_multipad_msgs
  )

  ament_add_gtest(test_serial_port
    test/test_serial_port.cpp
  )
  target_link_libraries(test_serial_port
    serial_port
  )

  ament_add_gtest(test_raw_stream_diagnostics
    test/test_raw_stream_diagnostics.cpp
  )
  target_link_libraries(test_raw_stream_diagnostics
    raw_stream_diagnostics
  )
  ament_target_dependencies(test_raw_stream_diagnostics
    diagnostic_msgs
  )

  add_test(
    NAME test_c2_diagnostics_stability
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/../../scripts/test_c2_diagnostics_stability.py
  )

  add_test(
    NAME test_smoke_diagnostics_topic
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/../../scripts/test_smoke_diagnostics_topic.py
  )

  add_test(
    NAME test_publish_raw_disabled_smoke
    COMMAND bash
      ${CMAKE_CURRENT_SOURCE_DIR}/../../scripts/smoke_publish_raw_disabled.sh
  )

  add_test(
    NAME test_c2_hardware_gate_syntax
    COMMAND bash -n
      ${CMAKE_CURRENT_SOURCE_DIR}/../../scripts/c2_hardware_stability_gate.sh
  )

  add_test(
    NAME test_rqt_plot_raw_launcher
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/test/test_rqt_plot_raw.py
  )

  add_test(
    NAME test_raw_plot_channels_cli
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/test/test_raw_plot_channels.py
  )
endif()

install(
  DIRECTORY include/
  DESTINATION include
)

install(
  TARGETS adda_frame_parser serial_port raw_stream_diagnostics
  EXPORT export_adda_frame_parser
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(
  TARGETS tg0_multipad_raw_publisher
  DESTINATION lib/${PROJECT_NAME}
)

install(
  PROGRAMS examples/raw_plot_channels.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME tg0_multipad_raw_plot_channels
)

install(
  PROGRAMS examples/rqt_plot_raw.sh
  DESTINATION lib/${PROJECT_NAME}
  RENAME tg0_multipad_raw_plot
)

ament_export_targets(export_adda_frame_parser HAS_LIBRARY_TARGET)
ament_export_include_directories(include)
ament_package()
