# Terminal 1
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg random_uxv_state_spawner --ros-args -p random_seed:=42

# Terminal 2
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg missiondeck_to_c2_bridge

# Terminal 3
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg map_node_publisher

# Terminal 4
source /opt/ros/humble/setup.bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
