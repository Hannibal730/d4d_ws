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
HEADQUARTERS = {
    "name": "Headquarters",
    "lat": 35.124333,
    "lon": 129.064000,
}


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
        "speed_kmph": (150.0, 230.0),
        "alt": (90.0, 650.0),
        "roles": ["Wide-area ISR", "Relay", "Target confirmation", "Route scan"],
    },
    "UGV": {
        "speed_kmph": (80.0, 140.0),
        "alt": (0.0, 8.0),
        "roles": ["Ground investigation", "Convoy scout", "Perimeter check", "Route clearance"],
    },
    "USV": {
        "speed_kmph": (80.0, 140.0),
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


def angle_from_center_to_point(center: Dict[str, float], point: Dict[str, float]) -> float:
    center_lat = math.radians(float(center["lat"]))
    center_lon = math.radians(float(center["lon"]))
    point_lat = math.radians(float(point["lat"]))
    point_lon = math.radians(float(point["lon"]))
    dlon = point_lon - center_lon
    y = math.sin(dlon) * math.cos(point_lat)
    x = (
        math.cos(center_lat) * math.sin(point_lat)
        - math.sin(center_lat) * math.cos(point_lat) * math.cos(dlon)
    )
    return math.atan2(y, x) % math.tau


def point_from_center_angle(
    center: Dict[str, float],
    radius_m: float,
    angle_rad: float,
    alt_m: float = 0.0,
) -> Dict[str, float]:
    center_lat = math.radians(float(center["lat"]))
    center_lon = math.radians(float(center["lon"]))
    angular_distance = max(0.0, radius_m) / EARTH_RADIUS_M

    point_lat = math.asin(
        math.sin(center_lat) * math.cos(angular_distance)
        + math.cos(center_lat) * math.sin(angular_distance) * math.cos(angle_rad)
    )
    point_lon = center_lon + math.atan2(
        math.sin(angle_rad) * math.sin(angular_distance) * math.cos(center_lat),
        math.cos(angular_distance) - math.sin(center_lat) * math.sin(point_lat),
    )
    point_lon = (point_lon + math.pi) % math.tau - math.pi
    return {
        "lat": round(math.degrees(point_lat), 7),
        "lon": round(math.degrees(point_lon), 7),
        "alt_m": round(float(alt_m), 1),
    }


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
        self.declare_parameter("battery_drain_scale", 0.5)
        self.declare_parameter("moving_battery_drain_scale", 0.5)
        self.declare_parameter("good_battery_drain_min", 0.01)
        self.declare_parameter("good_battery_drain_max", 0.03)
        self.declare_parameter("caution_battery_drain_min", 0.04)
        self.declare_parameter("caution_battery_drain_max", 0.09)
        self.declare_parameter("critical_battery_drain_min", 0.12)
        self.declare_parameter("critical_battery_drain_max", 0.22)
        self.declare_parameter("disabled_battery_drain_min", 0.005)
        self.declare_parameter("disabled_battery_drain_max", 0.015)
        self.declare_parameter("moving_battery_factor", 1.15)
        self.declare_parameter("idle_battery_factor", 0.35)
        self.declare_parameter("return_battery_reserve_pct", 8.0)
        self.declare_parameter("return_battery_safety_factor", 1.25)
        self.declare_parameter("uav_battery_pct_per_km", 0.18)
        self.declare_parameter("ugv_battery_pct_per_km", 0.08)
        self.declare_parameter("usv_battery_pct_per_km", 0.06)
        self.declare_parameter("uav_return_battery_pct_per_km", 0.18)
        self.declare_parameter("ugv_return_battery_pct_per_km", 0.08)
        self.declare_parameter("usv_return_battery_pct_per_km", 0.06)
        self.declare_parameter("good_battery_multiplier", 1.0)
        self.declare_parameter("caution_battery_multiplier", 1.35)
        self.declare_parameter("critical_battery_multiplier", 2.0)
        self.declare_parameter("disabled_battery_multiplier", 0.0)
        self.declare_parameter("unknown_battery_multiplier", 1.5)
        self.declare_parameter("risk_zones_topic", "/missiondeck/map/risk_zones")

        self.random_seed = int(self.get_parameter("random_seed").value)
        self.count_per_type = max(1, int(self.get_parameter("count_per_type").value))
        self.publish_hz = max(0.1, float(self.get_parameter("publish_hz").value))
        self.respawn_each_publish = bool(self.get_parameter("respawn_each_publish").value)
        self.max_spawn_attempts = max(1, int(self.get_parameter("max_spawn_attempts").value))
        self.command_speed_multiplier = max(1.0, float(self.get_parameter("command_speed_multiplier").value))
        self.battery_drain_scale = max(0.0, float(self.get_parameter("battery_drain_scale").value))
        self.moving_battery_drain_scale = max(0.0, float(self.get_parameter("moving_battery_drain_scale").value))
        self.battery_drain_ranges = {
            "good": (
                max(0.0, float(self.get_parameter("good_battery_drain_min").value)),
                max(0.0, float(self.get_parameter("good_battery_drain_max").value)),
            ),
            "caution": (
                max(0.0, float(self.get_parameter("caution_battery_drain_min").value)),
                max(0.0, float(self.get_parameter("caution_battery_drain_max").value)),
            ),
            "critical": (
                max(0.0, float(self.get_parameter("critical_battery_drain_min").value)),
                max(0.0, float(self.get_parameter("critical_battery_drain_max").value)),
            ),
            "disabled": (
                max(0.0, float(self.get_parameter("disabled_battery_drain_min").value)),
                max(0.0, float(self.get_parameter("disabled_battery_drain_max").value)),
            ),
        }
        self.moving_battery_factor = max(0.0, float(self.get_parameter("moving_battery_factor").value))
        self.idle_battery_factor = max(0.0, float(self.get_parameter("idle_battery_factor").value))
        self.return_battery_reserve_pct = max(0.0, float(self.get_parameter("return_battery_reserve_pct").value))
        self.return_battery_safety_factor = max(1.0, float(self.get_parameter("return_battery_safety_factor").value))
        self.battery_pct_per_km = {
            "UAV": max(0.0, float(self.get_parameter("uav_battery_pct_per_km").value)),
            "UGV": max(0.0, float(self.get_parameter("ugv_battery_pct_per_km").value)),
            "USV": max(0.0, float(self.get_parameter("usv_battery_pct_per_km").value)),
        }
        self.return_battery_pct_per_km = {
            "UAV": max(0.0, float(self.get_parameter("uav_return_battery_pct_per_km").value)),
            "UGV": max(0.0, float(self.get_parameter("ugv_return_battery_pct_per_km").value)),
            "USV": max(0.0, float(self.get_parameter("usv_return_battery_pct_per_km").value)),
        }
        self.battery_multipliers = {
            "good": max(0.0, float(self.get_parameter("good_battery_multiplier").value)),
            "caution": max(0.0, float(self.get_parameter("caution_battery_multiplier").value)),
            "critical": max(0.0, float(self.get_parameter("critical_battery_multiplier").value)),
            "disabled": max(0.0, float(self.get_parameter("disabled_battery_multiplier").value)),
            "unknown": max(0.0, float(self.get_parameter("unknown_battery_multiplier").value)),
        }

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
        self.planner_request_publisher = self.create_publisher(String, "/missiondeck/planner/request", 10)
        self.autopilot_log_publisher = self.create_publisher(String, "/c2/autopilot_log", 10)
        self.create_subscription(String, "/c2/operator_command", self.on_operator_command, 10)
        self.create_subscription(String, "/missiondeck/planner/selected_route", self.on_selected_route, 10)

        # Risk zones ("위험지역"): assets are never spawned inside these circular areas.
        self.risk_zones: List[Dict] = []
        risk_zones_topic = str(self.get_parameter("risk_zones_topic").value)
        self.create_subscription(String, risk_zones_topic, self.on_risk_zones, 10)

        self.assets = self.generate_assets(self.random_seed)
        self.sequence = 0

        self.create_timer(1.0 / self.publish_hz, self.publish_state)
        self.get_logger().info(
            "Random UxV spawner ready: "
            f"seed={self.random_seed}, count_per_type={self.count_per_type}, "
            f"publish_hz={self.publish_hz:.2f}, patrol_orbit=enabled, file={__file__}"
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

    def on_risk_zones(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid /missiondeck/map/risk_zones JSON")
            return

        zones = payload if isinstance(payload, list) else payload.get("zones", [])
        zones = [zone for zone in zones if isinstance(zone, dict)]
        if zones == self.risk_zones:
            return

        self.risk_zones = zones
        # Respawn so that no asset remains inside a newly-known risk zone.
        self.assets = self.generate_assets(self.random_seed + self.sequence)
        self.get_logger().info(
            f"Risk zones updated ({len(self.risk_zones)}); respawned assets outside risk areas"
        )

    def position_in_risk_zone(self, lat: float, lon: float) -> bool:
        for zone in self.risk_zones:
            radius_km = float(zone.get("radius_km", 0.0))
            if radius_km <= 0.0:
                continue
            try:
                zone_lat = float(zone["lat"])
                zone_lon = float(zone["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if haversine_m(lat, lon, zone_lat, zone_lon) <= radius_km * 1000.0:
                return True
        return False

    def random_position(self, rng: random.Random, asset_type: str) -> Dict[str, float]:
        min_lon, min_lat, max_lon, max_lat = self.land_mask.bbox

        if asset_type == "UGV" and self.land_mask.rings:
            for _ in range(self.max_spawn_attempts):
                ring = rng.choice(self.land_mask.rings)
                sample_min_lon, sample_min_lat, sample_max_lon, sample_max_lat = ring["bbox"]
                lat = rng.uniform(sample_min_lat, sample_max_lat)
                lon = rng.uniform(sample_min_lon, sample_max_lon)
                if self.position_in_risk_zone(lat, lon):
                    continue
                if self.land_mask.contains_land(lon, lat):
                    return {"lat": round(lat, 7), "lon": round(lon, 7), "domain": "land"}

        for _ in range(self.max_spawn_attempts):
            lat = rng.uniform(min_lat, max_lat)
            lon = rng.uniform(min_lon, max_lon)
            if self.position_in_risk_zone(lat, lon):
                continue
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
                battery = round(rng.uniform(80.0, 99.0), 1)
                comm_quality = round(rng.uniform(0.30, 1.00), 2)
                device_state = choose_device_state(rng)
                mission_status = choose_mission_status(rng, device_state)
                current_mission = None if mission_status == "available" else f"{asset_type}_TASK_{rng.randint(1, 7):02d}"

                spawn_position = self.random_position(rng, asset_type)

                speed_low_kmph, speed_high_kmph = profile["speed_kmph"]
                speed_mps = rng.uniform(speed_low_kmph, speed_high_kmph) / 3.6
                alt_low, alt_high = profile["alt"]
                assets.append(
                    {
                        "id": f"{asset_type}-{index}",
                        "type": asset_type,
                        "battery": battery,
                        "comm_quality": comm_quality,
                        "device_state": device_state,
                        "mission_status": mission_status,
                        "speed_mps": round(speed_mps, 1),
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
                        "patrol": None,
                    }
                )
        return assets

    def on_operator_command(self, msg: String) -> None:
        try:
            command = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid /c2/operator_command JSON")
            return

        command_name = str(command.get("command", "")).upper()
        if command_name == "STOP":
            self.stop_asset(command)
            return
        if command_name == "RETURN_HOME":
            self.return_asset_to_headquarters(command)
            return
        if command_name != "MOVE_TO":
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
            asset["patrol"] = None
            asset["mission_status"] = "assigned"
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
        asset["patrol"] = None
        asset["mission_status"] = "planning"
        asset["current_mission"] = f"PLANNING {target_name}"
        self.get_logger().info(
            f"MOVE_TO planning: {asset.get('id')} -> "
            f"{target_position['lat']:.5f}, {target_position['lon']:.5f}"
        )

    def stop_asset(self, command: Dict) -> None:
        vehicle_id = command.get("vehicle_id") or command.get("asset_id")
        if vehicle_id is None:
            self.get_logger().warning("STOP ignored: vehicle_id is required")
            return

        asset = self.find_asset(vehicle_id)
        if not asset:
            self.get_logger().warning(f"STOP ignored: asset not found: {vehicle_id}")
            return

        asset["pending_move"] = None
        asset["target_position"] = None
        asset["route_queue"] = []
        asset["patrol"] = None
        asset["mission_status"] = "available"
        asset["current_mission"] = "STOPPED"
        self.get_logger().info(f"STOP accepted: {asset.get('id')} cleared active route")

    def return_asset_to_headquarters(self, command: Dict) -> None:
        vehicle_id = command.get("vehicle_id") or command.get("asset_id")
        if vehicle_id is None:
            self.get_logger().warning("RETURN_HOME ignored: vehicle_id is required")
            return

        asset = self.find_asset(vehicle_id)
        if not asset:
            self.get_logger().warning(f"RETURN_HOME ignored: asset not found: {vehicle_id}")
            return
        if str(asset.get("device_state", "")).lower() == "disabled":
            self.get_logger().warning(f"RETURN_HOME ignored: {asset.get('id')} is disabled")
            return

        target_position = {
            "lat": float(command.get("target_lat", HEADQUARTERS["lat"])),
            "lon": float(command.get("target_lon", HEADQUARTERS["lon"])),
            "alt_m": float(command.get("target_alt_m", asset.get("alt_m", 0.0))),
        }
        asset["pending_move"] = None
        asset["target_position"] = target_position
        asset["route_queue"] = []
        asset["patrol"] = None
        asset["mission_status"] = "returning"
        asset["current_mission"] = f"RETURN_HOME {command.get('target_area', HEADQUARTERS['name'])}"
        self.get_logger().info(
            f"RETURN_HOME accepted: {asset.get('id')} -> "
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

        mission_type = str(
            selected.get("mission_type")
            or selected.get("command")
            or payload.get("mission_type")
            or "MOVE_TO"
        ).upper()
        patrol = None
        if mission_type == "PATROL":
            center_source = selected.get("route_points", [])[-1] if selected.get("route_points") else None
            target_node = payload.get("target_node") if isinstance(payload.get("target_node"), dict) else None
            center_lat = (target_node or center_source or queue[-1]).get("lat")
            center_lon = (target_node or center_source or queue[-1]).get("lon")
            if center_lat is not None and center_lon is not None:
                radius_km = max(0.1, float(selected.get("patrol_radius_km", payload.get("patrol_radius_km", 5.0))))
                direction = str(selected.get("patrol_direction", payload.get("patrol_direction", "clockwise"))).lower()
                if direction not in ("clockwise", "counterclockwise"):
                    direction = "clockwise"
                center = {"lat": float(center_lat), "lon": float(center_lon)}
                approach_source = queue[-2] if len(queue) >= 2 else (asset.get("position") or queue[0])
                entry_angle = angle_from_center_to_point(center, approach_source)
                entry_point = point_from_center_angle(
                    center,
                    radius_km * 1000.0,
                    entry_angle,
                    float(queue[-1].get("alt_m", asset.get("alt_m", 0.0))),
                )
                queue[-1] = entry_point
                patrol = {
                    "center": center,
                    "radius_m": radius_km * 1000.0,
                    "direction": direction,
                    "angle_rad": entry_angle,
                    "alt_m": entry_point["alt_m"],
                    "target_node_id": selected.get("target_node_id", "target"),
                }

        asset["pending_move"] = None
        asset["route_queue"] = queue[1:]
        asset["target_position"] = queue[0]
        asset["patrol"] = patrol
        if mission_type == "RETURN_HOME":
            asset["mission_status"] = "returning"
            asset["current_mission"] = f"RETURN_HOME {selected.get('target_node_id', HEADQUARTERS['name'])}"
        else:
            asset["mission_status"] = "assigned"
            asset["current_mission"] = (
                f"PATROL {selected.get('target_node_id', 'target')}"
                if patrol else f"FOLLOW_ROUTE {selected.get('target_node_id', 'target')}"
            )
        self.get_logger().info(
            f"Route accepted: {asset.get('id')} following {len(queue)} waypoint(s)"
            + (f" then patrolling {patrol['radius_m'] / 1000.0:.1f} km {patrol['direction']}" if patrol else "")
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
            asset["patrol"] = None
            asset["mission_status"] = "available"
            asset["current_mission"] = None
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

    def battery_rate_pct_per_km(self, asset: Dict) -> float:
        asset_type = str(asset.get("type", "UAV")).upper()
        device_state = str(asset.get("device_state", "unknown")).lower()
        base_rate = self.battery_pct_per_km.get(asset_type, 0.10)
        multiplier = self.battery_multipliers.get(
            device_state,
            self.battery_multipliers.get("unknown", 1.5),
        )
        return base_rate * multiplier * self.moving_battery_drain_scale

    def estimated_battery_used_for_distance_pct(self, asset: Dict, distance_km: float) -> float:
        return max(0.0, distance_km) * self.battery_rate_pct_per_km(asset)

    def idle_battery_drain_pct(self, asset: Dict, rng: random.Random) -> float:
        state = str(asset.get("device_state", "good")).lower()
        drain_range = self.battery_drain_ranges.get(state, (0.02, 0.05))
        return rng.uniform(*drain_range) * self.idle_battery_factor * self.battery_drain_scale

    def estimated_return_battery_required_pct(self, asset: Dict) -> float:
        position = asset.get("position") or {}
        distance_km = haversine_m(
            float(position.get("lat", HEADQUARTERS["lat"])),
            float(position.get("lon", HEADQUARTERS["lon"])),
            HEADQUARTERS["lat"],
            HEADQUARTERS["lon"],
        ) / 1000.0
        return (
            self.return_battery_reserve_pct
            + self.estimated_battery_used_for_distance_pct(asset, distance_km)
            * self.return_battery_safety_factor
        )

    def next_asset_id(self, asset_type: str) -> str:
        prefix = f"{asset_type}-"
        max_index = 0
        for asset in self.assets:
            asset_id = str(asset.get("id", ""))
            if not asset_id.startswith(prefix):
                continue
            try:
                max_index = max(max_index, int(asset_id.removeprefix(prefix)))
            except ValueError:
                continue
        return f"{asset_type}-{max_index + 1}"

    def create_hq_replacement_asset(self, asset_type: str) -> Dict:
        profile = TYPE_PROFILES.get(asset_type, TYPE_PROFILES["UAV"])
        speed_low_kmph, speed_high_kmph = profile["speed_kmph"]
        alt_low, alt_high = profile["alt"]
        replacement = {
            "id": self.next_asset_id(asset_type),
            "type": asset_type,
            "battery": 100.0,
            "comm_quality": 0.98,
            "device_state": "good",
            "mission_status": "available",
            "speed_mps": round(((speed_low_kmph + speed_high_kmph) / 2.0) / 3.6, 1),
            "position": {
                "lat": HEADQUARTERS["lat"],
                "lon": HEADQUARTERS["lon"],
            },
            "spawn_domain": "air" if asset_type == "UAV" else ("water" if asset_type == "USV" else "land"),
            "alt_m": round((alt_low + alt_high) / 2.0, 1),
            "role": profile["roles"][0],
            "current_mission": None,
            "target_position": None,
            "route_queue": [],
            "pending_move": None,
            "patrol": None,
        }
        self.assets.append(replacement)
        self.get_logger().info(f"Created HQ replacement asset {replacement['id']} for patrol handoff")
        return replacement

    def find_or_create_hq_replacement_asset(self, retiring_asset: Dict) -> Dict:
        asset_type = str(retiring_asset.get("type", "UAV")).upper()
        retiring_id = normalize_vehicle_id(retiring_asset.get("id"))
        candidates = []
        for asset in self.assets:
            if normalize_vehicle_id(asset.get("id")) == retiring_id:
                continue
            if str(asset.get("type", "")).upper() != asset_type:
                continue
            if str(asset.get("device_state", "")).lower() == "disabled":
                continue
            if asset.get("target_position") or asset.get("route_queue") or asset.get("pending_move") or asset.get("patrol"):
                continue
            if str(asset.get("mission_status", "available")).lower() != "available":
                continue
            position = asset.get("position") or {}
            distance_m = haversine_m(
                float(position.get("lat", 0.0)),
                float(position.get("lon", 0.0)),
                HEADQUARTERS["lat"],
                HEADQUARTERS["lon"],
            )
            if distance_m <= 1000.0:
                candidates.append((distance_m, asset))
        if candidates:
            return min(candidates, key=lambda item: item[0])[1]
        return self.create_hq_replacement_asset(asset_type)

    def publish_planner_request(self, payload: Dict) -> None:
        self.planner_request_publisher.publish(String(data=json.dumps(payload, separators=(",", ":"))))

    def publish_autopilot_log(self, log_type: str, text: str) -> None:
        publisher = getattr(self, "autopilot_log_publisher", None)
        if not publisher:
            return
        publisher.publish(String(data=json.dumps({
            "type": log_type,
            "text": text,
        }, separators=(",", ":"))))

    def request_patrol_handoff_if_needed(self, asset: Dict) -> None:
        patrol = asset.get("patrol")
        if not patrol or patrol.get("handoff_requested"):
            return

        battery = float(asset.get("battery", 0.0))
        required = self.estimated_return_battery_required_pct(asset)
        if battery > required:
            return

        target_node_id = patrol.get("target_node_id")
        if not target_node_id:
            return

        asset_type = str(asset.get("type", "UAV")).upper()
        patrol_radius_km = float(patrol.get("radius_m", 5000.0)) / 1000.0
        patrol_direction = patrol.get("direction", "clockwise")
        replacement = self.find_or_create_hq_replacement_asset(asset)
        return_request_id = f"AUTO_RETURN_{self.sequence}_{normalize_vehicle_id(asset.get('id'))}"
        handoff_request_id = f"AUTO_HANDOFF_{self.sequence}_{normalize_vehicle_id(replacement.get('id'))}"

        patrol["handoff_requested"] = True
        asset["patrol"] = None
        asset["target_position"] = None
        asset["route_queue"] = []
        asset["pending_move"] = {
            "request_id": return_request_id,
            "target_position": {"lat": HEADQUARTERS["lat"], "lon": HEADQUARTERS["lon"], "alt_m": asset.get("alt_m", 0.0)},
            "target_name": HEADQUARTERS["name"],
        }
        asset["mission_status"] = "planning"
        asset["current_mission"] = f"PLANNING RETURN_HOME {HEADQUARTERS['name']}"

        replacement["pending_move"] = {
            "request_id": handoff_request_id,
            "target_name": target_node_id,
        }
        replacement["target_position"] = None
        replacement["route_queue"] = []
        replacement["patrol"] = None
        replacement["mission_status"] = "planning"
        replacement["current_mission"] = f"PLANNING PATROL {target_node_id}"

        self.publish_planner_request({
            "schema": "missiondeck.planner.request.v1",
            "request_id": return_request_id,
            "target_node_id": "HEADQUARTERS",
            "vehicle_id": asset.get("id"),
            "asset_id": asset.get("id"),
            "selected_vehicle_id": asset.get("id"),
            "vehicle_type": asset_type,
            "selected_category": asset_type,
            "command": "RETURN_HOME",
            "mission_type": "RETURN_HOME",
            "source": "UXV_SPAWNER_AUTO_HANDOFF",
        })
        self.publish_planner_request({
            "schema": "missiondeck.planner.request.v1",
            "request_id": handoff_request_id,
            "target_node_id": target_node_id,
            "vehicle_id": replacement.get("id"),
            "asset_id": replacement.get("id"),
            "selected_vehicle_id": replacement.get("id"),
            "vehicle_type": asset_type,
            "selected_category": asset_type,
            "command": "PATROL",
            "mission_type": "PATROL",
            "patrol_radius_km": patrol_radius_km,
            "patrol_direction": patrol_direction,
            "source": "UXV_SPAWNER_AUTO_HANDOFF",
        })
        self.publish_autopilot_log(
            "auto",
            (
                f"Patrol handoff triggered: {asset.get('id')} battery {battery:.1f}% "
                f"<= return threshold {required:.1f}%. Return request {return_request_id} -> HEADQUARTERS; "
                f"replacement {replacement.get('id')} request {handoff_request_id} -> {target_node_id} "
                f"({patrol_radius_km:.1f} km {patrol_direction})."
            ),
        )
        self.get_logger().info(
            f"Patrol handoff triggered: {asset.get('id')} battery={battery:.1f}% "
            f"<= return_required={required:.1f}%; {asset.get('id')} returning, "
            f"{replacement.get('id')} launching to {target_node_id}"
        )

    def advance_asset_on_patrol(self, asset: Dict, step_m: float) -> float:
        patrol = asset.get("patrol")
        if not patrol:
            return 0.0

        radius_m = max(1.0, float(patrol.get("radius_m", 1.0)))
        center = patrol.get("center") or {}
        if center.get("lat") is None or center.get("lon") is None:
            asset["patrol"] = None
            asset["mission_status"] = "available"
            asset["current_mission"] = None
            return 0.0

        direction = str(patrol.get("direction", "clockwise")).lower()
        sign = 1.0 if direction == "clockwise" else -1.0
        angle_rad = (float(patrol.get("angle_rad", 0.0)) + sign * (step_m / radius_m)) % math.tau
        alt_m = float(patrol.get("alt_m", asset.get("alt_m", 0.0)))
        next_position = point_from_center_angle(center, radius_m, angle_rad, alt_m)

        asset["position"] = {"lat": next_position["lat"], "lon": next_position["lon"]}
        asset["alt_m"] = next_position["alt_m"]
        asset["target_position"] = None
        asset["route_queue"] = []
        asset["mission_status"] = "assigned"
        asset["current_mission"] = f"PATROL {patrol.get('target_node_id', 'target')}"
        patrol["angle_rad"] = angle_rad
        patrol["alt_m"] = next_position["alt_m"]
        return step_m

    def advance_asset_toward_target(self, asset: Dict) -> float:
        target = asset.get("target_position")
        speed_mps = max(0.1, float(asset.get("speed_mps", 1.0)))
        step_m = speed_mps * self.command_speed_multiplier / self.publish_hz
        if not target:
            return self.advance_asset_on_patrol(asset, step_m)

        position = asset.get("position") or {}
        current_lat = float(position.get("lat", 0.0))
        current_lon = float(position.get("lon", 0.0))
        target_lat = float(target["lat"])
        target_lon = float(target["lon"])
        remaining_m = haversine_m(current_lat, current_lon, target_lat, target_lon)

        if remaining_m <= max(step_m, 8.0):
            asset["position"] = {"lat": round(target_lat, 7), "lon": round(target_lon, 7)}
            asset["alt_m"] = round(float(target.get("alt_m", asset.get("alt_m", 0.0))), 1)
            route_queue = asset.get("route_queue") or []
            if route_queue:
                asset["target_position"] = route_queue.pop(0)
                asset["route_queue"] = route_queue
                asset["mission_status"] = "returning" if str(asset.get("current_mission", "")).startswith("RETURN_HOME") else "assigned"
            else:
                asset["target_position"] = None
                if asset.get("patrol"):
                    asset["mission_status"] = "assigned"
                    asset["current_mission"] = f"PATROL {asset['patrol'].get('target_node_id', 'target')}"
                    patrol_step_m = max(0.0, step_m - remaining_m)
                    return remaining_m + self.advance_asset_on_patrol(asset, patrol_step_m)
                else:
                    asset["mission_status"] = "available"
                    asset["current_mission"] = None
            return remaining_m
        else:
            ratio = step_m / remaining_m
            asset["position"] = {
                "lat": round(current_lat + (target_lat - current_lat) * ratio, 7),
                "lon": round(current_lon + (target_lon - current_lon) * ratio, 7),
            }
            asset["mission_status"] = "returning" if str(asset.get("current_mission", "")).startswith("RETURN_HOME") else "assigned"
            return step_m

    def jitter_assets(self) -> None:
        rng = random.Random(self.random_seed + self.sequence)
        for asset in list(self.assets):
            distance_m = self.advance_asset_toward_target(asset)
            if distance_m > 0.0:
                battery_drain = self.estimated_battery_used_for_distance_pct(asset, distance_m / 1000.0)
            else:
                battery_drain = self.idle_battery_drain_pct(asset, rng)
            asset["battery"] = round(clamp(float(asset["battery"]) - battery_drain, 0.0, 100.0), 3)
            self.request_patrol_handoff_if_needed(asset)
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