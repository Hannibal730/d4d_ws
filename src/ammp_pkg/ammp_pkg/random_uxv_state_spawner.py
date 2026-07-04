#!/usr/bin/env python3

import json
import math
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
EARTH_RADIUS_M = 6371008.8


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


def normalize_vehicle_id(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    h = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


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
        self.declare_parameter("command_speed_multiplier", 120.0)

        self.random_seed = int(self.get_parameter("random_seed").value)
        self.count_per_type = max(1, int(self.get_parameter("count_per_type").value))
        self.publish_hz = max(0.1, float(self.get_parameter("publish_hz").value))
        self.respawn_each_publish = bool(self.get_parameter("respawn_each_publish").value)
        self.max_spawn_attempts = max(1, int(self.get_parameter("max_spawn_attempts").value))
        self.command_speed_multiplier = max(1.0, float(self.get_parameter("command_speed_multiplier").value))

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
        self.create_subscription(String, "/c2/operator_command", self.on_operator_command, 10)
        self.create_subscription(String, "/missiondeck/planner/selected_route", self.on_selected_route, 10)
        self.assets = self.generate_assets(self.random_seed)
        self.sequence = 0

        self.create_timer(1.0 / self.publish_hz, self.publish_state)
        self.get_logger().info(
            "Random UxV spawner ready: "
            f"seed={self.random_seed}, count_per_type={self.count_per_type}, publish_hz={self.publish_hz:.2f}"
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
                battery = round(rng.uniform(90.0, 100.0), 1)
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
                        "target_position": None,
                        "route_queue": [],
                        "pending_move": None,
                    }
                )
        return assets

    def on_operator_command(self, msg: String) -> None:
        try:
            command = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid /c2/operator_command JSON")
            return

        if str(command.get("command", "")).upper() != "MOVE_TO":
            return

        vehicle_id = command.get("vehicle_id") or command.get("asset_id")
        target_lat = command.get("target_lat")
        target_lon = command.get("target_lon")
        if vehicle_id is None or target_lat is None or target_lon is None:
            self.get_logger().warning("MOVE_TO ignored: vehicle_id, target_lat, and target_lon are required")
            return

        asset = self.find_asset(vehicle_id)
        if not asset:
            self.get_logger().warning(f"MOVE_TO ignored: asset not found: {vehicle_id}")
            return
        if str(asset.get("device_state", "")).lower() == "disabled":
            self.get_logger().warning(f"MOVE_TO ignored: {asset.get('id')} is disabled")
            return

        target_position = {
            "lat": float(target_lat),
            "lon": float(target_lon),
            "alt_m": float(command.get("target_alt_m", asset.get("alt_m", 0.0))),
        }
        target_name = command.get("target_area") or command.get("target_node_id") or "target"
        planner_request_id = command.get("planner_request_id")
        if not planner_request_id:
            asset["pending_move"] = None
            asset["target_position"] = target_position
            asset["route_queue"] = []
            asset["mission_status"] = "assigned"
            asset["assignment_possible"] = False
            asset["current_mission"] = f"MOVE_TO {target_name}"
            self.get_logger().info(
                f"MOVE_TO direct fallback: {asset.get('id')} -> "
                f"{target_position['lat']:.5f}, {target_position['lon']:.5f}"
            )
            return

        asset["pending_move"] = {
            "request_id": planner_request_id,
            "target_position": target_position,
            "target_name": target_name,
        }
        asset["target_position"] = None
        asset["route_queue"] = []
        asset["mission_status"] = "planning"
        asset["current_mission"] = f"PLANNING {target_name}"
        self.get_logger().info(
            f"MOVE_TO planning: {asset.get('id')} -> "
            f"{target_position['lat']:.5f}, {target_position['lon']:.5f}"
        )

    def on_selected_route(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid /missiondeck/planner/selected_route JSON")
            return

        selected = payload.get("selected") if isinstance(payload, dict) else None
        if not selected:
            self.clear_failed_pending_move(payload if isinstance(payload, dict) else {})
            return

        asset = self.find_asset(selected.get("asset_id"))
        if not asset:
            return

        route_points = selected.get("route_points") or selected.get("routePoints") or []
        queue = []
        for point in route_points[1:]:
            if not isinstance(point, dict):
                continue
            lat = point.get("lat")
            lon = point.get("lon")
            if lat is None or lon is None:
                continue
            queue.append({
                "lat": float(lat),
                "lon": float(lon),
                "alt_m": float(point.get("alt_m", asset.get("alt_m", 0.0))),
            })

        if not queue:
            return

        asset["pending_move"] = None
        asset["route_queue"] = queue[1:]
        asset["target_position"] = queue[0]
        asset["mission_status"] = "assigned"
        asset["assignment_possible"] = False
        asset["current_mission"] = f"FOLLOW_ROUTE {selected.get('target_node_id', 'target')}"
        self.get_logger().info(
            f"Route accepted: {asset.get('id')} following {len(queue)} waypoint(s)"
        )

    def clear_failed_pending_move(self, payload: Dict) -> None:
        vehicle_id = (
            payload.get("requested_asset_id")
            or payload.get("asset_id")
            or payload.get("vehicle_id")
        )
        if not vehicle_id:
            return

        asset = self.find_asset(vehicle_id)
        if not asset or not asset.get("pending_move"):
            return

        asset["pending_move"] = None
        if not asset.get("target_position"):
            asset["route_queue"] = []
            asset["mission_status"] = "available"
            asset["current_mission"] = None
            asset["assignment_possible"] = assignment_possible(
                str(asset.get("device_state", "good")).lower(),
                str(asset.get("mission_status", "available")).lower(),
                float(asset.get("battery", 0.0)),
                float(asset.get("comm_quality", 0.0)),
            )
        self.get_logger().warning(
            f"Route rejected: clearing pending MOVE_TO for {asset.get('id')}: "
            f"{payload.get('reason', 'no feasible route')}"
        )

    def find_asset(self, vehicle_id: str) -> Optional[Dict]:
        target = normalize_vehicle_id(vehicle_id)
        return next(
            (asset for asset in self.assets if normalize_vehicle_id(asset.get("id")) == target),
            None,
        )

    def advance_asset_toward_target(self, asset: Dict) -> None:
        target = asset.get("target_position")
        if not target:
            return

        position = asset.get("position") or {}
        current_lat = float(position.get("lat", 0.0))
        current_lon = float(position.get("lon", 0.0))
        target_lat = float(target["lat"])
        target_lon = float(target["lon"])
        remaining_m = haversine_m(current_lat, current_lon, target_lat, target_lon)
        speed_mps = max(0.1, float(asset.get("speed_mps", 1.0)))
        step_m = speed_mps * self.command_speed_multiplier / self.publish_hz

        if remaining_m <= max(step_m, 8.0):
            asset["position"] = {"lat": round(target_lat, 7), "lon": round(target_lon, 7)}
            asset["alt_m"] = round(float(target.get("alt_m", asset.get("alt_m", 0.0))), 1)
            route_queue = asset.get("route_queue") or []
            if route_queue:
                asset["target_position"] = route_queue.pop(0)
                asset["route_queue"] = route_queue
                asset["mission_status"] = "assigned"
            else:
                asset["target_position"] = None
                asset["mission_status"] = "available"
                asset["current_mission"] = None
        else:
            ratio = step_m / remaining_m
            asset["position"] = {
                "lat": round(current_lat + (target_lat - current_lat) * ratio, 7),
                "lon": round(current_lon + (target_lon - current_lon) * ratio, 7),
            }
            asset["mission_status"] = "assigned"

    def jitter_assets(self) -> None:
        rng = random.Random(self.random_seed + self.sequence)
        for asset in self.assets:
            state = str(asset.get("device_state", "good")).lower()
            mission_status = str(asset.get("mission_status", "available")).lower()
            drain_range = {
                "good": (0.02, 0.06),
                "caution": (0.08, 0.18),
                "critical": (0.22, 0.42),
                "disabled": (0.01, 0.03),
            }.get(state, (0.04, 0.10))
            motion_factor = 1.35 if mission_status in ("assigned", "returning") else 0.65
            battery_drain = rng.uniform(*drain_range) * motion_factor
            self.advance_asset_toward_target(asset)
            asset["battery"] = round(clamp(float(asset["battery"]) - battery_drain, 0.0, 100.0), 1)
            asset["comm_quality"] = round(clamp(float(asset["comm_quality"]) + rng.uniform(-0.01, 0.01), 0.0, 1.0), 2)
            asset["assignment_possible"] = assignment_possible(
                str(asset.get("device_state", "good")).lower(),
                str(asset.get("mission_status", "available")).lower(),
                float(asset.get("battery", 0.0)),
                float(asset.get("comm_quality", 0.0)),
            )

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
