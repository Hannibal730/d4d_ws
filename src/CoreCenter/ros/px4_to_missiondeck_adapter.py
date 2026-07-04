#!/usr/bin/env python3

import json
import math

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String
except ModuleNotFoundError as exc:
    raise SystemExit(
        "ROS 2 Python modules are not available in this terminal.\n"
        "Source ROS 2 first, then run this adapter again:\n\n"
        "  source /opt/ros/humble/setup.bash\n"
        "  source ~/px4_ros2_ws/install/setup.bash\n"
        "  python3 /home/hannibal/d4d_ws/src/CoreCenter/ros/px4_to_missiondeck_adapter.py\n"
    ) from exc

try:
    from px4_msgs.msg import (
        BatteryStatus,
        VehicleGlobalPosition,
        VehicleOdometry,
        VehicleStatus,
    )
except ModuleNotFoundError as exc:
    raise SystemExit(
        "px4_msgs is not available in this terminal.\n"
        "Build and source a ROS 2 workspace containing px4_msgs first:\n\n"
        "  source /opt/ros/humble/setup.bash\n"
        "  mkdir -p ~/px4_ros2_ws/src\n"
        "  cd ~/px4_ros2_ws/src\n"
        "  git clone https://github.com/PX4/px4_msgs.git\n"
        "  cd ~/px4_ros2_ws\n"
        "  colcon build --symlink-install --packages-select px4_msgs\n"
        "  source ~/px4_ros2_ws/install/setup.bash\n\n"
        "Then run this adapter again from the same sourced terminal."
    ) from exc


def clamp(value, low, high):
    return max(low, min(high, value))


def finite_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


class Px4ToMissionDeckAdapter(Node):
    def __init__(self):
        super().__init__("px4_to_missiondeck_adapter")

        self.declare_parameter("asset_id", "PX4_GJ_01")
        self.declare_parameter("asset_type", "UAV")
        self.declare_parameter("default_battery_pct", 100.0)
        self.declare_parameter("default_comm_quality", 1.0)
        self.declare_parameter("current_mission", "")
        self.declare_parameter("link_timeout_sec", 3.0)
        self.declare_parameter("battery_caution_pct", 30.0)
        self.declare_parameter("battery_critical_pct", 15.0)
        self.declare_parameter("publish_hz", 5.0)

        # PX4 uXRCE-DDS telemetry is commonly best-effort and volatile.
        px4_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        missiondeck_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.global_position = None
        self.battery = None
        self.odometry = None
        self.status = None
        self.last_position_time = None
        self.last_battery_time = None
        self.last_odometry_time = None
        self.last_status_time = None
        self.last_wait_log_time = self.get_clock().now()
        self.received_position_once = False
        self.published_once = False

        self.create_subscription(
            VehicleGlobalPosition,
            "/fmu/out/vehicle_global_position",
            self.on_global_position,
            px4_qos,
        )
        self.create_subscription(BatteryStatus, "/fmu/out/battery_status", self.on_battery, px4_qos)
        self.create_subscription(VehicleOdometry, "/fmu/out/vehicle_odometry", self.on_odometry, px4_qos)
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status", self.on_status, px4_qos)

        self.publisher = self.create_publisher(String, "/missiondeck/uxv_states", missiondeck_qos)

        publish_hz = max(0.1, finite_float(self.get_parameter("publish_hz").value, 5.0))
        self.create_timer(1.0 / publish_hz, self.publish_uxv_state)

    def on_global_position(self, msg):
        self.global_position = msg
        self.last_position_time = self.get_clock().now()
        if not self.received_position_once:
            self.received_position_once = True
            self.get_logger().info(
                f"Received PX4 global position: lat={float(msg.lat):.7f}, lon={float(msg.lon):.7f}"
            )

    def on_battery(self, msg):
        self.battery = msg
        self.last_battery_time = self.get_clock().now()

    def on_odometry(self, msg):
        self.odometry = msg
        self.last_odometry_time = self.get_clock().now()

    def on_status(self, msg):
        self.status = msg
        self.last_status_time = self.get_clock().now()

    def seconds_since(self, stamp):
        if stamp is None:
            return None
        return (self.get_clock().now() - stamp).nanoseconds / 1_000_000_000.0

    def has_fresh_position(self):
        age = self.seconds_since(self.last_position_time)
        timeout = finite_float(self.get_parameter("link_timeout_sec").value, 3.0)
        return age is not None and age <= timeout

    def battery_pct(self):
        default_battery = finite_float(self.get_parameter("default_battery_pct").value, 100.0)
        if self.battery is None:
            return clamp(default_battery, 0.0, 100.0)
        return clamp(finite_float(self.battery.remaining, default_battery) * 100.0, 0.0, 100.0)

    def comm_quality(self):
        base = clamp(finite_float(self.get_parameter("default_comm_quality").value, 1.0), 0.0, 1.0)
        age = self.seconds_since(self.last_position_time)
        timeout = finite_float(self.get_parameter("link_timeout_sec").value, 3.0)
        if age is None:
            return 0.0
        if age <= timeout:
            return base
        if age >= timeout * 2.0:
            return 0.0
        return clamp(base * (1.0 - ((age - timeout) / timeout)), 0.0, 1.0)

    def speed_mps(self):
        if self.odometry is None:
            return 0.0
        components = [finite_float(component, 0.0) for component in self.odometry.velocity]
        return math.sqrt(sum(component * component for component in components))

    def status_failsafe(self):
        return bool(getattr(self.status, "failsafe", False)) if self.status is not None else False

    def nav_state(self):
        if self.status is None:
            return None
        return int(getattr(self.status, "nav_state", -1))

    def nav_state_is_one_of(self, *constant_names):
        state = self.nav_state()
        if state is None:
            return False
        return any(state == int(getattr(VehicleStatus, name, -9999)) for name in constant_names)

    def mission_status(self):
        current_mission = str(self.get_parameter("current_mission").value or "").strip()
        if self.nav_state_is_one_of(
            "NAVIGATION_STATE_AUTO_RTL",
            "NAVIGATION_STATE_AUTO_LAND",
            "NAVIGATION_STATE_AUTO_PRECLAND",
        ):
            return "returning"
        if current_mission:
            return "assigned"
        if self.nav_state_is_one_of(
            "NAVIGATION_STATE_AUTO_MISSION",
            "NAVIGATION_STATE_AUTO_LOITER",
            "NAVIGATION_STATE_ORBIT",
            "NAVIGATION_STATE_AUTO_TAKEOFF",
        ):
            return "assigned"
        return "available"

    def device_state(self):
        battery = self.battery_pct()
        battery_caution = finite_float(self.get_parameter("battery_caution_pct").value, 30.0)
        battery_critical = finite_float(self.get_parameter("battery_critical_pct").value, 15.0)
        comm = self.comm_quality()

        if not self.has_fresh_position():
            return "critical"
        if self.status_failsafe() or battery <= battery_critical or comm < 0.2:
            return "critical"
        if self.status is None or self.battery is None:
            return "caution"
        if battery <= battery_caution or comm < 0.5:
            return "caution"
        return "good"

    def assignment_possible(self, device_state, mission_status):
        if device_state in ("critical", "disabled"):
            return False
        if mission_status in ("assigned", "returning"):
            return False
        return self.has_fresh_position()

    def current_mission(self):
        value = str(self.get_parameter("current_mission").value or "").strip()
        return value if value else None

    def publish_uxv_state(self):
        if self.global_position is None:
            now = self.get_clock().now()
            if (now - self.last_wait_log_time).nanoseconds > 5_000_000_000:
                self.last_wait_log_time = now
                self.get_logger().info("Waiting for /fmu/out/vehicle_global_position ...")
            return

        lat = finite_float(self.global_position.lat, 0.0)
        lon = finite_float(self.global_position.lon, 0.0)
        device_state = self.device_state()
        mission_status = self.mission_status()

        payload = {
            "assets": [
                {
                    "id": str(self.get_parameter("asset_id").value),
                    "type": str(self.get_parameter("asset_type").value),
                    "battery": self.battery_pct(),
                    "comm_quality": self.comm_quality(),
                    "device_state": device_state,
                    "mission_status": mission_status,
                    "speed_mps": self.speed_mps(),
                    "assignment_possible": self.assignment_possible(device_state, mission_status),
                    "position": {
                        "lat": lat,
                        "lon": lon,
                    },
                    "current_mission": self.current_mission(),
                }
            ]
        }

        self.publisher.publish(String(data=json.dumps(payload)))
        if not self.published_once:
            self.published_once = True
            self.get_logger().info(f"Publishing /missiondeck/uxv_states for {payload['assets'][0]['id']}")


def main():
    rclpy.init()
    node = Px4ToMissionDeckAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
