cmake_minimum_required(VERSION 3.8)
project(rviz_za6_io_panel)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rviz_common REQUIRED)
find_package(std_msgs REQUIRED)
find_package(pluginlib REQUIRED)
find_package(Qt5 REQUIRED COMPONENTS Widgets)

# Enable Qt MOC, UIC, and RCC
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

# Include directories
include_directories(include ${Qt5Widgets_INCLUDE_DIRS})

# Source files
set(${PROJECT_NAME}_SRCS src/io_panel.cpp)

# Header files with Q_OBJECT
set(${PROJECT_NAME}_HDRS include/rviz_za6_io_panel/io_panel.hpp)

# Create library
add_library(
  ${PROJECT_NAME} SHARED ${${PROJECT_NAME}_SRCS} ${${PROJECT_NAME}_HDRS}
  )

# Link dependencies
ament_target_dependencies(${PROJECT_NAME} rclcpp rviz_common std_msgs pluginlib)

target_link_libraries(${PROJECT_NAME} Qt5::Widgets)

# Causes the visibility macros to use dllexport rather than dllimport
target_compile_definitions(
  ${PROJECT_NAME} PRIVATE "RVIZ_ZA6_IO_PANEL_BUILDING_LIBRARY"
  )

# Export plugin description file
pluginlib_export_plugin_description_file(rviz_common plugins_description.xml)

# Install
install(
  TARGETS ${PROJECT_NAME}
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
  )

install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})

install(FILES plugins_description.xml DESTINATION share/${PROJECT_NAME})

# Export
ament_export_include_directories(include)
ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_dependencies(rclcpp rviz_common std_msgs pluginlib Qt5)

ament_package()
