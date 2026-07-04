#!/usr/bin/env python3

import json
from typing import Dict, Iterable, Tuple

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
except ModuleNotFoundError as exc:
    raise SystemExit(
        "ROS 2 Python modules are not available in this terminal.\n"
        "Source ROS 2 first, then run this bridge again:\n\n"
        "  source /opt/ros/humble/setup.bash\n"
        "  source /home/hannibal/d4d_ws/install/setup.bash\n"
        "  ros2 run ammp_pkg missiondeck_to_c2_bridge\n"
    ) from exc


KOREA_BBOX = (124.7893155286271, 33.172610584346295, 130.96524575425667, 38.54255349620522)

SUBTYPES = {
    "UAV": "Mission UAV",
    "UGV": "Ground rover",
    "USV": "Surface vessel",
}

CAMERA_MODES = {
    "UAV": "EO / WIDE",
    "UGV": "THERMAL / FORWARD",
    "USV": "EO / MARITIME",
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def project_to_ui_map(lon: float, lat: float) -> Tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = KOREA_BBOX
    padding = 34
    width = 1000 - padding * 2
    height = 600 - padding * 2
    x = padding + ((lon - min_lon) / (max_lon - min_lon)) * width
    y = padding + ((max_lat - lat) / (max_lat - min_lat)) * height
    return clamp(x, 0.0, 1000.0), clamp(y, 0.0, 600.0)


def alert_level(asset: Dict) -> str:
    device_state = str(asset.get("device_state", "")).lower()
    battery = float(asset.get("battery", 0.0))
    comm_quality = float(asset.get("comm_quality", 0.0))
    if device_state in ("critical", "disabled") or battery <= 20.0 or comm_quality <= 0.35:
        return "RED"
    if device_state == "caution" or battery <= 45.0 or comm_quality <= 0.65:
        return "AMBER"
    return "GREEN"


def mission_state(asset: Dict) -> str:
    status = str(asset.get("mission_status", "unknown")).upper()
    state = str(asset.get("device_state", "")).upper()
    if state == "DISABLED":
        return "DISABLED"
    if status == "AVAILABLE":
        return "STANDBY"
    return status


def normalize_vehicle_id(asset_id: str) -> str:
    return asset_id.replace("-", "_")


class MissionDeckToC2Bridge(Node):
    def __init__(self):
        super().__init__("missiondeck_to_c2_bridge")

        self.create_subscription(String, "/missiondeck/uxv_states", self.on_uxv_states, 10)
        self.fleet_publisher = self.create_publisher(String, "/c2/fleet/state", 10)
        self.alert_publisher = self.create_publisher(String, "/c2/alerts", 10)
        self.last_alert_levels = {}

        self.get_logger().info("Bridge ready: /missiondeck/uxv_states -> /c2/fleet/state")

    def on_uxv_states(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid /missiondeck/uxv_states JSON")
            return

        assets = payload if isinstance(payload, list) else payload.get("assets", [])
        if not isinstance(assets, list):
            self.get_logger().warning("Ignoring /missiondeck/uxv_states without an assets list")
            return

        c2_payload = {
            "schema": "c2.fleet.state.v1",
            "source_topic": "/missiondeck/uxv_states",
            "random_seed": payload.get("random_seed") if isinstance(payload, dict) else None,
            "assets": [self.to_c2_asset(asset) for asset in assets if isinstance(asset, dict)],
        }
        self.fleet_publisher.publish(String(data=json.dumps(c2_payload, separators=(",", ":"))))
        self.publish_changed_alerts(c2_payload["assets"])

    def to_c2_asset(self, asset: Dict) -> Dict:
        asset_type = str(asset.get("type", "UAV")).upper()
        position = asset.get("position") or {}
        lat = float(position.get("lat", asset.get("lat", 0.0)))
        lon = float(position.get("lon", asset.get("lon", 0.0)))
        map_x, map_y = project_to_ui_map(lon, lat)
        vehicle_id = normalize_vehicle_id(str(asset.get("id", "UNKNOWN")))
        level = alert_level(asset)

        return {
            "id": asset.get("id", vehicle_id),
            "type": asset_type,
            "vehicle_id": vehicle_id,
            "vehicle_type": asset_type,
            "subtype": asset.get("subtype") or SUBTYPES.get(asset_type, asset_type),
            "role": asset.get("role") or "AMMP asset",
            "battery": float(asset.get("battery", 0.0)),
            "battery_pct": float(asset.get("battery", 0.0)),
            "comm_quality": float(asset.get("comm_quality", 0.0)),
            "link_quality": float(asset.get("comm_quality", 0.0)),
            "device_state": asset.get("device_state", "unknown"),
            "mission_status": asset.get("mission_status", "unknown"),
            "speed_mps": float(asset.get("speed_mps", 0.0)),
            "nav_confidence": float(asset.get("nav_confidence", 0.95)),
            "assignment_possible": bool(asset.get("assignment_possible", False)),
            "assignable": bool(asset.get("assignment_possible", False)),
            "alert_level": level,
            "mission_state": mission_state(asset),
            "current_mission": asset.get("current_mission") or "No mission assigned",
            "position": {
                "lat": lat,
                "lon": lon,
            },
            "lat": lat,
            "lon": lon,
            "alt_m": float(asset.get("alt_m", 0.0)),
            "map_x": round(map_x, 1),
            "map_y": round(map_y, 1),
            "route": asset.get("route", []),
            "camera_mode": CAMERA_MODES.get(asset_type, "CAMERA / NO FEED"),
            "camera_status": f"AMMP {asset.get('device_state', 'unknown')} / {asset.get('mission_status', 'unknown')}",
        }

    def publish_changed_alerts(self, assets: Iterable[Dict]) -> None:
        for asset in assets:
            vehicle_id = asset["vehicle_id"]
            level = asset["alert_level"]
            previous_level = self.last_alert_levels.get(vehicle_id)
            self.last_alert_levels[vehicle_id] = level
            if level == "GREEN" or previous_level == level:
                continue

            self.alert_publisher.publish(String(data=json.dumps({
                "vehicle_id": vehicle_id,
                "severity": level,
                "title": f"{vehicle_id.replace('_', '-')} state requires attention",
                "recommendation": "Review battery, communication quality, and assignment availability.",
            }, separators=(",", ":"))))


def main(args=None):
    rclpy.init(args=args)
    node = MissionDeckToC2Bridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
