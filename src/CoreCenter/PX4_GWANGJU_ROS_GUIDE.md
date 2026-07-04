# PX4 Gwangju to CoreCenter

This guide connects PX4 telemetry to CoreCenter without requiring Gazebo. It uses PX4 uXRCE-DDS topics, bridges them into `/c2/fleet/state`, then shows the vehicle in CoreCenter.

## Coordinates

Gwangju Metropolitan City Hall area:

```text
lat: 35.1595
lon: 126.8526
alt: 50
```

For real hardware, the map marker comes from the real GPS position published by PX4. To test at Gwangju without Gazebo, the easiest option is to publish a one-shot `/c2/fleet/state` test message or use a real/simulated PX4 source whose GPS origin is configured near Gwangju.

## 0. Install prerequisites

Use Ubuntu 22.04 + ROS 2 Humble where possible.

```bash
sudo apt install ros-humble-rosbridge-suite python3-colcon-common-extensions
```

Install Micro XRCE-DDS Agent:

```bash
cd ~
git clone -b v2.4.3 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent
mkdir -p build
cd build
cmake ..
make
sudo make install
sudo ldconfig /usr/local/lib/
```

Create a ROS 2 workspace with PX4 messages:

```bash
mkdir -p ~/px4_ros2_ws/src
cd ~/px4_ros2_ws/src
git clone https://github.com/PX4/px4_msgs.git
cd ~/px4_ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

## 1. Fix `ModuleNotFoundError: No module named 'px4_msgs'`

This bridge imports PX4 ROS 2 message definitions from `px4_msgs`. If that package is not built and sourced, Python cannot import it.

```bash
source /opt/ros/humble/setup.bash
mkdir -p ~/px4_ros2_ws/src
cd ~/px4_ros2_ws/src
git clone https://github.com/PX4/px4_msgs.git
cd ~/px4_ros2_ws
colcon build --symlink-install --packages-select px4_msgs
source ~/px4_ros2_ws/install/setup.bash
```

Check:

```bash
python3 -c "from px4_msgs.msg import VehicleGlobalPosition; print('px4_msgs OK')"
```

Run every ROS/PX4 terminal with these first:

```bash
source /opt/ros/humble/setup.bash
source ~/px4_ros2_ws/install/setup.bash
```

## 2. Terminal A: start Micro XRCE-DDS Agent

For PX4 over UDP:

```bash
MicroXRCEAgent udp4 -p 8888
```

For PX4 over serial USB/TELEM, use the device and baud rate that match your hardware:

```bash
MicroXRCEAgent serial --dev /dev/ttyACM0 -b 921600
```

## 3. Terminal B: check PX4 ROS 2 topics

```bash
source /opt/ros/humble/setup.bash
source ~/px4_ros2_ws/install/setup.bash
ros2 topic list | grep /fmu/out
ros2 topic echo /fmu/out/vehicle_global_position
```

If this is a real PX4, latitude/longitude will be the real GPS position. If the GPS source is set to Gwangju, you should see latitude near `35.1595` and longitude near `126.8526`.

## 4. Terminal C: publish CoreCenter fleet state

Run the provided bridge directly:

```bash
source /opt/ros/humble/setup.bash
source ~/px4_ros2_ws/install/setup.bash
python3 /home/kuzdx/d4d_ws/src/CoreCenter/ros/px4_to_c2_bridge.py
```

Verify:

```bash
ros2 topic echo /c2/fleet/state
```

## 5. Terminal D: start rosbridge

```bash
source /opt/ros/humble/setup.bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

## 6. Terminal E: start CoreCenter web

```bash
cd /home/kuzdx/d4d_ws
python3 -m http.server 8080
```

Open:

```text
http://127.0.0.1:8080/src/CoreCenter/
```

Click `Connect ROS`.

Expected result:

- Header changes to `ROS CONNECTED`
- Equipment list shows `PX4-GJ-01`
- Selected Asset shows Gwangju latitude/longitude
- Map marker appears at the projected Gwangju position

## Quick web-only connection test without PX4

Use this to confirm CoreCenter and rosbridge work before connecting PX4:

```bash
ros2 topic pub --once /c2/fleet/state std_msgs/msg/String "{data: '{\"assets\":[{\"vehicle_id\":\"PX4_GJ_01\",\"vehicle_type\":\"UAV\",\"subtype\":\"PX4 test\",\"role\":\"Gwangju connection test\",\"battery_pct\":82,\"link_quality\":1.0,\"speed_mps\":0,\"nav_confidence\":1.0,\"assignable\":true,\"alert_level\":\"GREEN\",\"mission_state\":\"TEST\",\"current_mission\":\"Gwangju test\",\"lat\":35.1595,\"lon\":126.8526,\"alt_m\":50,\"map_x\":344,\"map_y\":369,\"route\":[]}]}' }"
```

## Troubleshooting

If `ros2` is not found:

```bash
source /opt/ros/humble/setup.bash
```

If `/fmu/out/...` topics do not appear:

- Start `MicroXRCEAgent udp4 -p 8888` before PX4.
- Restart PX4 SITL.
- Confirm PX4 is v1.14 or newer for uXRCE-DDS workflow.

If CoreCenter does not connect:

- Confirm rosbridge is running on `ws://127.0.0.1:9090`.
- Open browser devtools and check WebSocket errors.
- Confirm `/c2/fleet/state` is publishing `std_msgs/msg/String`.
