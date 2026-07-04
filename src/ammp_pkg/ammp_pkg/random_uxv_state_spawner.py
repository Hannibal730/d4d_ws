#!/usr/bin/env python3

import json
import random
from typing import Dict, List, Optional

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
except ModuleNotFoundError as exc:
    raise SystemExit(
        "ROS 2 Python modules are not available in this terminal.\n"
        "Source ROS 2 first, then run this node again:\n\n"
        "  source /opt/ros/humble/setup.bash\n"
        "  source /home/hannibal/d4d_ws/install/setup.bash\n"
        "  ros2 run ammp_pkg random_uxv_state_spawner --ros-args -p random_seed:=42\n"
    ) from exc


KOREA_BBOX = (124.7893155286271, 33.172610584346295, 130.96524575425667, 38.54255349620522)

TYPE_PROFILES = {
    "UAV": {
        "speed": (14.0, 32.0),
        "alt": (90.0, 650.0),
        "roles": ["Wide-area ISR", "Relay", "Target confirmation", "Route scan"],
    },
    "UGV": {
        "speed": (2.0, 12.0),
        "alt": (0.0, 8.0),
        "roles": ["Ground investigation", "Convoy scout", "Perimeter check", "Route clearance"],
    },
    "USV": {
        "speed": (3.0, 14.0),
        "alt": (0.0, 0.0),
        "roles": ["Coastal surveillance", "Harbor patrol", "Waterway screen", "Maritime watch"],
    },
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def choose_device_state(rng: random.Random) -> str:
    return rng.choices(
        ["good", "caution", "critical", "disabled"],
        weights=[0.64, 0.24, 0.09, 0.03],
        k=1,
    )[0]


def choose_mission_status(rng: random.Random, device_state: str) -> str:
    if device_state == "disabled":
        return "returning"
    return rng.choices(
        ["available", "assigned", "returning"],
        weights=[0.64, 0.27, 0.09],
        k=1,
    )[0]


def assignment_possible(device_state: str, mission_status: str, battery: float, comm_quality: float) -> bool:
    return (
        device_state not in ("critical", "disabled")
        and mission_status == "available"
        and battery >= 25.0
        and comm_quality >= 0.45
    )


class RandomUxvStateSpawner(Node):
    def __init__(self):
        super().__init__("random_uxv_state_spawner")

        self.declare_parameter("random_seed", 42)
        self.declare_parameter("count_per_type", 5)
        self.declare_parameter("publish_hz", 1.0)
        self.declare_parameter("min_lat", KOREA_BBOX[1])
        self.declare_parameter("min_lon", KOREA_BBOX[0])
        self.declare_parameter("max_lat", KOREA_BBOX[3])
        self.declare_parameter("max_lon", KOREA_BBOX[2])
        self.declare_parameter("respawn_each_publish", False)

        self.random_seed = int(self.get_parameter("random_seed").value)
        self.count_per_type = max(1, int(self.get_parameter("count_per_type").value))
        publish_hz = max(0.1, float(self.get_parameter("publish_hz").value))
        self.respawn_each_publish = bool(self.get_parameter("respawn_each_publish").value)

        self.publisher = self.create_publisher(String, "/missiondeck/uxv_states", 10)
        self.assets = self.generate_assets(self.random_seed)
        self.sequence = 0

        self.create_timer(1.0 / publish_hz, self.publish_state)
        self.get_logger().info(
            "Random UxV spawner ready: "
            f"seed={self.random_seed}, count_per_type={self.count_per_type}, publish_hz={publish_hz:.2f}"
        )

    def generate_assets(self, seed: Optional[int] = None) -> List[Dict]:
        rng = random.Random(seed)
        assets = []
        for asset_type in ("UAV", "UGV", "USV"):
            profile = TYPE_PROFILES[asset_type]
            for index in range(1, self.count_per_type + 1):
                battery = round(rng.uniform(18.0, 100.0), 1)
                comm_quality = round(rng.uniform(0.30, 1.00), 2)
                device_state = choose_device_state(rng)
                mission_status = choose_mission_status(rng, device_state)
                possible = assignment_possible(device_state, mission_status, battery, comm_quality)
                current_mission = None if mission_status == "available" else f"{asset_type}_TASK_{rng.randint(1, 7):02d}"

                min_lat = float(self.get_parameter("min_lat").value)
                min_lon = float(self.get_parameter("min_lon").value)
                max_lat = float(self.get_parameter("max_lat").value)
                max_lon = float(self.get_parameter("max_lon").value)

                speed_low, speed_high = profile["speed"]
                alt_low, alt_high = profile["alt"]
                assets.append(
                    {
                        "id": f"{asset_type}-{index}",
                        "type": asset_type,
                        "battery": battery,
                        "comm_quality": comm_quality,
                        "device_state": device_state,
                        "mission_status": mission_status,
                        "speed_mps": round(rng.uniform(speed_low, speed_high), 1),
                        "assignment_possible": possible,
                        "position": {
                            "lat": round(rng.uniform(min_lat, max_lat), 7),
                            "lon": round(rng.uniform(min_lon, max_lon), 7),
                        },
                        "alt_m": round(rng.uniform(alt_low, alt_high), 1),
                        "role": rng.choice(profile["roles"]),
                        "current_mission": current_mission,
                    }
                )
        return assets

    def jitter_assets(self) -> None:
        rng = random.Random(self.random_seed + self.sequence)
        for asset in self.assets:
            asset["battery"] = round(clamp(float(asset["battery"]) - rng.uniform(0.0, 0.05), 0.0, 100.0), 1)
            asset["comm_quality"] = round(clamp(float(asset["comm_quality"]) + rng.uniform(-0.01, 0.01), 0.0, 1.0), 2)

    def publish_state(self) -> None:
        if self.respawn_each_publish:
            self.assets = self.generate_assets(self.random_seed + self.sequence)
        else:
            self.jitter_assets()

        payload = {
            "schema": "missiondeck.uxv_states.v1",
            "random_seed": self.random_seed,
            "sequence": self.sequence,
            "assets": self.assets,
        }
        self.publisher.publish(String(data=json.dumps(payload, separators=(",", ":"))))
        if self.sequence == 0:
            self.get_logger().info(
                f"Publishing {len(self.assets)} assets to /missiondeck/uxv_states"
            )
        self.sequence += 1


def main(args=None):
    rclpy.init(args=args)
    node = RandomUxvStateSpawner()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
