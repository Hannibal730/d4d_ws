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
        "Source ROS 2 first, then run this bridge again:\n\n"
        "  source /opt/ros/humble/setup.bash\n"
        "  source ~/px4_ros2_ws/install/setup.bash\n"
        "  python3 /home/kuzdx/d4d_ws/src/CoreCenter/ros/px4_to_c2_bridge.py\n"
    ) from exc

try:
    from px4_msgs.msg import (
        BatteryStatus,
        VehicleCommand,
        VehicleCommandAck,
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
        "Then run this bridge again from the same sourced terminal."
    ) from exc


KOREA_BBOX = (124.7893155286271, 33.172610584346295, 130.96524575425667, 38.54255349620522)


def project_to_ui_map(lon, lat):
    min_lon, min_lat, max_lon, max_lat = KOREA_BBOX
    padding = 34
    width = 1000 - padding * 2
    height = 600 - padding * 2
    x = padding + ((lon - min_lon) / (max_lon - min_lon)) * width
    y = padding + ((max_lat - lat) / (max_lat - min_lat)) * height
    return x, y


class Px4ToC2Bridge(Node):
    def __init__(self):
        super().__init__("px4_to_c2_bridge")

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        command_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.global_position = None
        self.battery = None
        self.odometry = None
        self.status = None
        self.last_wait_log_time = self.get_clock().now()
        self.received_position_once = False
        self.published_once = False
        self.last_command_name_by_id = {}

        self.create_subscription(VehicleGlobalPosition, "/fmu/out/vehicle_global_position", self.on_global_position, qos)
        self.create_subscription(BatteryStatus, "/fmu/out/battery_status", self.on_battery, qos)
        self.create_subscription(VehicleOdometry, "/fmu/out/vehicle_odometry", self.on_odometry, qos)
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status", self.on_status, qos)
        self.create_subscription(VehicleCommandAck, "/fmu/out/vehicle_command_ack", self.on_vehicle_command_ack, qos)
        self.create_subscription(String, "/c2/operator_command", self.on_operator_command, 10)

        self.publisher = self.create_publisher(String, "/c2/fleet/state", 10)
        self.autopilot_log_publisher = self.create_publisher(String, "/c2/autopilot_log", 10)
        self.alert_publisher = self.create_publisher(String, "/c2/alerts", 10)
        self.vehicle_command_publisher = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", command_qos)
        self.create_timer(0.2, self.publish_state)

    def on_global_position(self, msg):
        self.global_position = msg
        if not self.received_position_once:
            self.received_position_once = True
            self.get_logger().info(
                f"Received PX4 global position: lat={float(msg.lat):.7f}, lon={float(msg.lon):.7f}, alt={float(msg.alt):.2f}"
            )

    def on_battery(self, msg):
        self.battery = msg

    def on_odometry(self, msg):
        self.odometry = msg

    def on_status(self, msg):
        self.status = msg

    def publish_autopilot_log(self, log_type, text):
        self.autopilot_log_publisher.publish(String(data=json.dumps({
            "type": log_type,
            "time": self.get_clock().now().to_msg().sec,
            "text": text,
        })))

    def publish_alert(self, severity, title, recommendation):
        self.alert_publisher.publish(String(data=json.dumps({
            "vehicle_id": "PX4_GJ_01",
            "severity": severity,
            "title": title,
            "recommendation": recommendation,
        })))

    def ack_result_text(self, result):
        names = {
            getattr(VehicleCommandAck, "VEHICLE_CMD_RESULT_ACCEPTED", 0): "ACCEPTED",
            getattr(VehicleCommandAck, "VEHICLE_CMD_RESULT_TEMPORARILY_REJECTED", 1): "TEMPORARILY_REJECTED",
            getattr(VehicleCommandAck, "VEHICLE_CMD_RESULT_DENIED", 2): "DENIED",
            getattr(VehicleCommandAck, "VEHICLE_CMD_RESULT_UNSUPPORTED", 3): "UNSUPPORTED",
            getattr(VehicleCommandAck, "VEHICLE_CMD_RESULT_FAILED", 4): "FAILED",
            getattr(VehicleCommandAck, "VEHICLE_CMD_RESULT_IN_PROGRESS", 5): "IN_PROGRESS",
            getattr(VehicleCommandAck, "VEHICLE_CMD_RESULT_CANCELLED", 6): "CANCELLED",
        }
        return names.get(int(result), f"UNKNOWN_{int(result)}")

    def on_vehicle_command_ack(self, msg):
        command_id = int(msg.command)
        command_name = self.last_command_name_by_id.get(command_id, f"COMMAND_{command_id}")
        result_text = self.ack_result_text(msg.result)
        log_type = "auto" if result_text in ("ACCEPTED", "IN_PROGRESS") else "warning"
        self.publish_autopilot_log(log_type, f"PX4 {command_name} ACK: {result_text}")
        if result_text not in ("ACCEPTED", "IN_PROGRESS"):
            self.publish_alert(
                "AMBER",
                f"PX4 rejected {command_name}",
                f"VehicleCommand ACK result: {result_text}. Check mode, arming state, failsafe, and takeoff preconditions.",
            )

    def on_operator_command(self, msg):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning(f"Invalid /c2/operator_command payload: {msg.data}")
            return

        command = payload.get("command")
        if command == "TAKEOFF":
            takeoff_alt_m = float(payload.get("takeoff_alt_m", 15.0))
            self.publish_takeoff(takeoff_alt_m)
            return
        if command == "MOVE_TO":
            self.publish_move_to(payload)
            return

        self.get_logger().info(f"Operator command received but not handled by PX4 bridge: {command}")

    def publish_vehicle_command(self, command, **params):
        command_name = params.pop("command_name", f"COMMAND_{int(command)}")
        msg = VehicleCommand()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.param1 = float(params.get("param1", 0.0))
        msg.param2 = float(params.get("param2", 0.0))
        msg.param3 = float(params.get("param3", 0.0))
        msg.param4 = float(params.get("param4", 0.0))
        msg.param5 = float(params.get("param5", 0.0))
        msg.param6 = float(params.get("param6", 0.0))
        msg.param7 = float(params.get("param7", 0.0))
        msg.command = int(command)
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.confirmation = 0
        msg.from_external = True
        self.last_command_name_by_id[int(command)] = command_name
        self.vehicle_command_publisher.publish(msg)
        self.publish_autopilot_log("manual", f"Sent PX4 {command_name} command")

    def publish_takeoff(self, takeoff_alt_m):
        arm_command = getattr(VehicleCommand, "VEHICLE_CMD_COMPONENT_ARM_DISARM", 400)
        takeoff_command = getattr(VehicleCommand, "VEHICLE_CMD_NAV_TAKEOFF", 22)

        self.publish_vehicle_command(arm_command, command_name="ARM", param1=1.0)

        target_alt = takeoff_alt_m
        target_lat = 0.0
        target_lon = 0.0
        if self.global_position is not None:
            target_lat = float(self.global_position.lat)
            target_lon = float(self.global_position.lon)
            target_alt = float(self.global_position.alt) + takeoff_alt_m

        self.publish_vehicle_command(
            takeoff_command,
            command_name="TAKEOFF",
            param5=target_lat,
            param6=target_lon,
            param7=target_alt,
        )
        self.get_logger().info(
            f"PX4 takeoff requested: target_lat={target_lat:.7f}, target_lon={target_lon:.7f}, target_alt={target_alt:.2f}"
        )

    def publish_move_to(self, payload):
        target_lat = payload.get("target_lat")
        target_lon = payload.get("target_lon")
        if target_lat is None or target_lon is None:
            self.publish_autopilot_log("warning", "MOVE_TO ignored: target_lat/target_lon missing")
            return

        target_alt = payload.get("target_alt_m")
        if target_alt is None:
            target_alt = float(self.global_position.alt) if self.global_position is not None else 50.0

        reposition_command = getattr(VehicleCommand, "VEHICLE_CMD_DO_REPOSITION", 192)
        target_area = payload.get("target_area", "operation area")
        self.publish_vehicle_command(
            reposition_command,
            command_name=f"MOVE_TO {target_area}",
            param1=-1.0,
            param5=float(target_lat),
            param6=float(target_lon),
            param7=float(target_alt),
        )
        self.get_logger().info(
            f"PX4 move-to requested: area={target_area}, lat={float(target_lat):.7f}, "
            f"lon={float(target_lon):.7f}, alt={float(target_alt):.2f}"
        )

    def publish_state(self):
        if self.global_position is None:
            now = self.get_clock().now()
            if (now - self.last_wait_log_time).nanoseconds > 5_000_000_000:
                self.last_wait_log_time = now
                self.get_logger().info("Waiting for /fmu/out/vehicle_global_position ...")
            return

        lat = float(self.global_position.lat)
        lon = float(self.global_position.lon)
        alt = float(self.global_position.alt)
        map_x, map_y = project_to_ui_map(lon, lat)

        battery_pct = 0.0
        if self.battery is not None and math.isfinite(float(self.battery.remaining)):
            battery_pct = max(0.0, min(100.0, float(self.battery.remaining) * 100.0))

        speed_mps = 0.0
        if self.odometry is not None:
            velocity = list(self.odometry.velocity)
            speed_mps = math.sqrt(sum(float(component) ** 2 for component in velocity if math.isfinite(float(component))))

        mission_state = "PX4_ACTIVE" if self.status is not None else "PX4_LINK_WAIT"

        payload = {
            "assets": [
                {
                    "vehicle_id": "PX4_GJ_01",
                    "vehicle_type": "UAV",
                    "subtype": "PX4 x500 SITL",
                    "role": "Gwangju telemetry test",
                    "battery_pct": battery_pct,
                    "link_quality": 1.0,
                    "speed_mps": speed_mps,
                    "nav_confidence": 1.0,
                    "assignable": True,
                    "alert_level": "GREEN",
                    "mission_state": mission_state,
                    "current_mission": "PX4 SITL at Gwangju",
                    "lat": lat,
                    "lon": lon,
                    "alt_m": alt,
                    "map_x": map_x,
                    "map_y": map_y,
                    "route": [],
                }
            ]
        }

        self.publisher.publish(String(data=json.dumps(payload)))
        if not self.published_once:
            self.published_once = True
            self.get_logger().info("Publishing /c2/fleet/state for PX4_GJ_01")


def main():
    rclpy.init()
    node = Px4ToC2Bridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
