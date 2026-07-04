# Terminal 1
cd d4d_ws/
python3 -m http.server 8080

# Terminal 2
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg random_uxv_state_spawner --ros-args -p random_seed:=42

# Terminal 3
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg missiondeck_to_c2_bridge

# Terminal 4
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg map_node_publisher

# Terminal 5
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg route_planner_node

# Terminal 6
source /opt/ros/humble/setup.bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml

# Terminal 7
cd d4d_ws/
source /opt/ros/humble/setup.bash
ros2 run vision uav1_yolo_alert_node


# 배터리 파라미터
battery = round(rng.uniform(90.0, 100.0), 1)

        self.declare_parameter("battery_drain_scale", 0.5)
        self.declare_parameter("moving_battery_drain_scale", 4.0)