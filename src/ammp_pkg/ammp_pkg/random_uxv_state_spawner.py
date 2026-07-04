#!/usr/bin/env python3

import json
from pathlib import Path
import random
from typing import Dict, List, Optional, Sequence, Tuple

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


def find_default_land_geojson() -> str:
    filename = Path("res") / "TL_SCCO_CTPRVN.json"
    candidates = [Path.cwd() / filename, Path("/home/hannibal/d4d_ws") / filename]
    candidates.extend(parent / filename for parent in Path(__file__).resolve().parents)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(Path("/home/hannibal/d4d_ws") / filename)


DEFAULT_LAND_GEOJSON = find_default_land_geojson()

FALLBACK_POSITIONS = {
    "UAV": {"lat": 35.1595, "lon": 126.8526, "domain": "air"},
    "UGV": {"lat": 35.1595, "lon": 126.8526, "domain": "land"},
    "USV": {"lat": 35.1028, "lon": 129.0403, "domain": "water"},
}

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


def ring_bbox(ring: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
    lons = [float(point[0]) for point in ring]
    lats = [float(point[1]) for point in ring]
    return min(lons), min(lats), max(lons), max(lats)


def point_in_ring(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
    inside = False
    count = len(ring)
    if count < 3:
        return False

    previous_lon = float(ring[-1][0])
    previous_lat = float(ring[-1][1])
    for point in ring:
        current_lon = float(point[0])
        current_lat = float(point[1])
        crosses_lat = (current_lat > lat) != (previous_lat > lat)
        if crosses_lat:
            intersect_lon = (
                (previous_lon - current_lon) * (lat - current_lat)
                / (previous_lat - current_lat)
                + current_lon
            )
            if lon < intersect_lon:
                inside = not inside
        previous_lon = current_lon
        previous_lat = current_lat
    return inside


def bbox_contains(bbox: Tuple[float, float, float, float], lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


class LandMask:
    def __init__(self, rings: List[Dict], bbox: Tuple[float, float, float, float]):
        self.rings = rings
        self.bbox = bbox

    @classmethod
    def from_geojson(cls, path: str, fallback_bbox: Tuple[float, float, float, float]):
        geojson_path = Path(path).expanduser()
        if not geojson_path.exists():
            return cls([], fallback_bbox)

        with geojson_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        rings = []
        for feature in data.get("features", []):
            geometry = feature.get("geometry") or {}
            geometry_type = geometry.get("type")
            coordinates = geometry.get("coordinates") or []
            polygons = []
            if geometry_type == "Polygon":
                polygons = [coordinates]
            elif geometry_type == "MultiPolygon":
                polygons = coordinates

            for polygon in polygons:
                if not polygon:
                    continue
                outer = polygon[0]
                holes = polygon[1:]
                rings.append({
                    "outer": outer,
                    "holes": holes,
                    "bbox": ring_bbox(outer),
                })

        return cls(rings, fallback_bbox)

    def contains_land(self, lon: float, lat: float) -> bool:
        for ring in self.rings:
            if not bbox_contains(ring["bbox"], lon, lat):
                continue
            if not point_in_ring(lon, lat, ring["outer"]):
                continue
            if any(point_in_ring(lon, lat, hole) for hole in ring["holes"]):
                continue
            return True
        return False


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
        self.declare_parameter("land_geojson_path", DEFAULT_LAND_GEOJSON)
        self.declare_parameter("max_spawn_attempts", 5000)

        self.random_seed = int(self.get_parameter("random_seed").value)
        self.count_per_type = max(1, int(self.get_parameter("count_per_type").value))
        publish_hz = max(0.1, float(self.get_parameter("publish_hz").value))
        self.respawn_each_publish = bool(self.get_parameter("respawn_each_publish").value)
        self.max_spawn_attempts = max(1, int(self.get_parameter("max_spawn_attempts").value))

        configured_bbox = (
            float(self.get_parameter("min_lon").value),
            float(self.get_parameter("min_lat").value),
            float(self.get_parameter("max_lon").value),
            float(self.get_parameter("max_lat").value),
        )
        self.land_mask = LandMask.from_geojson(
            str(self.get_parameter("land_geojson_path").value),
            configured_bbox,
        )

        self.publisher = self.create_publisher(String, "/missiondeck/uxv_states", 10)
        self.assets = self.generate_assets(self.random_seed)
        self.sequence = 0

        self.create_timer(1.0 / publish_hz, self.publish_state)
        self.get_logger().info(
            "Random UxV spawner ready: "
            f"seed={self.random_seed}, count_per_type={self.count_per_type}, publish_hz={publish_hz:.2f}"
        )
        if self.land_mask.rings:
            self.get_logger().info(
                f"Loaded land mask with {len(self.land_mask.rings)} polygons from "
                f"{self.get_parameter('land_geojson_path').value}"
            )
        else:
            raise RuntimeError(
                "Land mask unavailable. Set land_geojson_path to a GeoJSON file with Polygon or MultiPolygon features."
            )

    def random_position(self, rng: random.Random, asset_type: str) -> Dict[str, float]:
        min_lon, min_lat, max_lon, max_lat = self.land_mask.bbox

        if asset_type == "UGV" and self.land_mask.rings:
            for _ in range(self.max_spawn_attempts):
                ring = rng.choice(self.land_mask.rings)
                sample_min_lon, sample_min_lat, sample_max_lon, sample_max_lat = ring["bbox"]
                lat = rng.uniform(sample_min_lat, sample_max_lat)
                lon = rng.uniform(sample_min_lon, sample_max_lon)
                if self.land_mask.contains_land(lon, lat):
                    return {"lat": round(lat, 7), "lon": round(lon, 7), "domain": "land"}

        for _ in range(self.max_spawn_attempts):
            lat = rng.uniform(min_lat, max_lat)
            lon = rng.uniform(min_lon, max_lon)
            is_land = self.land_mask.contains_land(lon, lat)
            if asset_type == "USV" and not is_land:
                return {"lat": round(lat, 7), "lon": round(lon, 7), "domain": "water"}
            if asset_type == "UAV":
                return {"lat": round(lat, 7), "lon": round(lon, 7), "domain": "air"}

        fallback = FALLBACK_POSITIONS.get(asset_type, FALLBACK_POSITIONS["UAV"]).copy()
        self.get_logger().warning(
            f"Could not sample a valid {asset_type} spawn point after {self.max_spawn_attempts} attempts. "
            f"Using fallback {fallback['lat']:.4f}, {fallback['lon']:.4f}."
        )
        return fallback

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

                spawn_position = self.random_position(rng, asset_type)

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
                            "lat": spawn_position["lat"],
                            "lon": spawn_position["lon"],
                        },
                        "spawn_domain": spawn_position["domain"],
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
