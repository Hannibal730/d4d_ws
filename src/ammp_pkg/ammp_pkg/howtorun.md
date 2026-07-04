# Terminal 1
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg random_uxv_state_spawner --ros-args -p random_seed:=42

# Battery drain can be softened further with:
# ros2 run ammp_pkg random_uxv_state_spawner --ros-args \
#   -p random_seed:=42 \
#   -p battery_drain_scale:=0.35 \
#   -p moving_battery_factor:=1.0 \
#   -p idle_battery_factor:=0.25

# Terminal 2
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg missiondeck_to_c2_bridge

# Terminal 3
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg map_node_publisher

# Optional graph verification:
# ros2 topic echo /missiondeck/map/graph_geojson std_msgs/msg/String --once

# Terminal 4
source /opt/ros/humble/setup.bash
source /home/hannibal/d4d_ws/install/setup.bash
ros2 run ammp_pkg route_planner_node

# Selected routes now include snapped_asset_node_id, edge_ids, and distance_m:
# ros2 topic echo /missiondeck/planner/selected_route std_msgs/msg/String
#
# Risk-crossing graph edges are rejected by default.
# The planner also uses a 3 km safety margin around each risk zone:
#   risk_clearance_margin_km:=3.0
# If fallback is explicitly enabled, risk-crossing edges receive math.inf cost:
#   -p allow_risk_crossing_edges:=true

# Planner battery estimate can be softened further with:
# ros2 run ammp_pkg route_planner_node --ros-args \
#   -p battery_drain_scale:=0.7 \
#   -p uav_battery_pct_per_km:=0.14 \
#   -p ugv_battery_pct_per_km:=0.06 \
#   -p usv_battery_pct_per_km:=0.045 \
#   -p min_arrival_battery_pct:=0.0

# Terminal 5
source /opt/ros/humble/setup.bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
