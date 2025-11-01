# `rviz_za6_io_panel` - Digital I/O Panel for Tormach ZA6

This package provides a custom RViz panel for visualizing and controlling the Tormach ZA6 robot's digital I/O system. It displays 16 digital inputs and 16 digital outputs in a clean, tabbed interface.

## Features

- **Digital Inputs Tab**: Real-time monitoring of 16 digital inputs (DIN01-DIN16)
  - Color-coded status indicators (Green=ON, Gray=OFF)
  - Compact grid layout with 4 inputs per row
  - Read-only status display

- **Digital Outputs Tab**: Control interface for 16 digital outputs (DOUT01-DOUT16)
  - Toggle buttons for each output
  - Visual feedback with button state changes
  - Instant publishing to ROS 2 topics

## ROS 2 Integration

### Topics

**Subscribes to:**
- `/din01` through `/din16` (std_msgs/Bool)

**Publishes to:**
- `/hal_io/dout01` through `/hal_io/dout16` (std_msgs/Bool)

### QoS Settings
- Reliability: Best Effort
- History: Keep Last (10 messages)
- Compatible with the existing `hal_io` node configuration

## Installation

The panel is automatically included when building the Tormach ZA ROS 2 drivers workspace:

```bash
colcon build --packages-select rviz_za6_io_panel
source install/setup.bash
```

## Usage

### Launch with RViz

The panel is automatically included in the main RViz configurations:

```bash
# Launch with MoveIt and RViz
ros2 launch za6_bringup bringup.launch

# Launch hardware-only with RViz
ros2 launch za6_hardware hal_hardware.launch.py
```

### Manual Panel Addition

If you need to add the panel manually to RViz:

1. In RViz, go to `Panels` → `Add New Panel...`
2. Select `rviz_za6_io_panel/IOPanel` from the list
3. The "Digital IO" panel will appear with two tabs

## Technical Details

### Dependencies
- ROS 2 Humble
- rviz_common
- std_msgs
- pluginlib
- Qt5 Widgets

### Build Requirements
- CMake 3.8+
- Qt5 development packages
- ROS 2 development tools

### Architecture
- Inherits from `rviz_common::Panel`
- Uses Qt signals/slots for UI interactions
- ROS 2 node integration via `RosNodeAbstractionIface`
- Plugin system integration via `pluginlib`

## Integration with Existing System

This panel integrates seamlessly with the existing Tormach ZA6 digital I/O system:

- **HAL Layer**: Connects to HAL pins `din01`-`din16` and `dout01`-`dout16`
- **ROS 2 Bridge**: Uses the existing `hal_io` node for topic communication
- **Hardware**: Compatible with both real EtherCAT hardware and simulation mode
- **Configuration**: Works with existing `hal_io_config.yaml` settings

## Development

### Building
```bash
colcon build --packages-select rviz_za6_io_panel
```

### Testing
1. Launch the ZA6 hardware (real or simulation)
2. Start RViz with the updated configuration
3. Verify input states update in real-time
4. Test output control via toggle buttons

### Customization
- Modify `src/io_panel.cpp` for UI layout changes
- Update `include/rviz_za6_io_panel/io_panel.hpp` for functionality changes
- Adjust topic names or QoS settings as needed

## License

This package is licensed under Apache-2.0, consistent with the main Tormach ZA ROS 2 drivers repository.
