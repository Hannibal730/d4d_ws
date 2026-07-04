#!/usr/bin/env python3

import json
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

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
        "  ros2 run ammp_pkg map_node_publisher\n"
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


def ring_bbox(ring: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
    lons = [float(point[0]) for point in ring]
    lats = [float(point[1]) for point in ring]
    return min(lons), min(lats), max(lons), max(lats)


def geometry_bbox(coordinates) -> Tuple[float, float, float, float] | None:
    bbox = [float("inf"), float("inf"), float("-inf"), float("-inf")]

    def visit_coordinate(coordinate):
        if not isinstance(coordinate, list):
            return
        if len(coordinate) >= 2 and isinstance(coordinate[0], (int, float)) and isinstance(coordinate[1], (int, float)):
            bbox[0] = min(bbox[0], float(coordinate[0]))
            bbox[1] = min(bbox[1], float(coordinate[1]))
            bbox[2] = max(bbox[2], float(coordinate[0]))
            bbox[3] = max(bbox[3], float(coordinate[1]))
            return
        for child in coordinate:
            visit_coordinate(child)

    visit_coordinate(coordinates)
    return tuple(bbox) if all(math.isfinite(value) for value in bbox) else None


def point_in_ring(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
    inside = False
    if len(ring) < 3:
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


def load_geojson(path: str) -> Dict:
    geojson_path = Path(path).expanduser()
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON file does not exist: {geojson_path}")
    with geojson_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_land_mask(geojson: Dict, fallback_bbox: Tuple[float, float, float, float]) -> LandMask:
    rings = []
    for feature in geojson.get("features", []):
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
            rings.append({
                "outer": outer,
                "holes": polygon[1:],
                "bbox": ring_bbox(outer),
            })
    return LandMask(rings, fallback_bbox)


def generate_land_nodes(geojson: Dict) -> List[Dict]:
    nodes = []
    for index, feature in enumerate(geojson.get("features", []), start=1):
        bbox = geometry_bbox((feature.get("geometry") or {}).get("coordinates"))
        if not bbox:
            continue
        properties = feature.get("properties") or {}
        code = properties.get("CTPRVN_CD") or f"{index:02d}"
        name = properties.get("CTP_KOR_NM") or properties.get("CTP_ENG_NM") or properties.get("name") or f"Land node {index}"
        min_lon, min_lat, max_lon, max_lat = bbox
        nodes.append({
            "id": f"LAND-{code}",
            "name": name,
            "domain": "land",
            "node_kind": "destination_waypoint",
            "allowed_types": ["UGV", "UAV"],
            "lat": round((min_lat + max_lat) / 2, 7),
            "lon": round((min_lon + max_lon) / 2, 7),
        })
    return nodes


def generate_water_nodes(land_mask: LandMask, step_deg: float) -> List[Dict]:
    min_lon, min_lat, max_lon, max_lat = land_mask.bbox
    nodes = []
    index = 1
    lon = min_lon
    while lon <= max_lon + step_deg / 2:
        lat = min_lat
        while lat <= max_lat + step_deg / 2:
            if not land_mask.contains_land(lon, lat):
                nodes.append({
                    "id": f"WATER-{index:04d}",
                    "name": f"Water grid {index}",
                    "domain": "water",
                    "node_kind": "destination_waypoint",
                    "allowed_types": ["USV", "UAV"],
                    "lat": round(lat, 7),
                    "lon": round(lon, 7),
                })
                index += 1
            lat += step_deg
        lon += step_deg
    return nodes


class MapNodePublisher(Node):
    def __init__(self):
        super().__init__("map_node_publisher")

        self.declare_parameter("land_geojson_path", DEFAULT_LAND_GEOJSON)
        self.declare_parameter("water_grid_step_deg", 0.25)
        self.declare_parameter("publish_hz", 0.5)
        self.declare_parameter("topic_name", "/missiondeck/map/waypoint_nodes")

        self.land_geojson_path = str(self.get_parameter("land_geojson_path").value)
        self.water_grid_step_deg = max(0.05, float(self.get_parameter("water_grid_step_deg").value))
        self.topic_name = str(self.get_parameter("topic_name").value)
        publish_hz = max(0.1, float(self.get_parameter("publish_hz").value))

        self.geojson = load_geojson(self.land_geojson_path)
        self.land_mask = extract_land_mask(self.geojson, KOREA_BBOX)
        if not self.land_mask.rings:
            raise RuntimeError("No land polygons found. Check land_geojson_path.")

        self.land_nodes = generate_land_nodes(self.geojson)
        self.water_nodes = generate_water_nodes(self.land_mask, self.water_grid_step_deg)
        self.publisher = self.create_publisher(String, self.topic_name, 10)
        self.sequence = 0

        self.create_timer(1.0 / publish_hz, self.publish_nodes)
        self.get_logger().info(
            f"Map node publisher ready: {len(self.land_nodes)} land nodes, "
            f"{len(self.water_nodes)} water nodes -> {self.topic_name}"
        )

    def publish_nodes(self) -> None:
        payload = {
            "schema": "missiondeck.map.waypoint_nodes.v1",
            "sequence": self.sequence,
            "land_geojson_path": self.land_geojson_path,
            "water_grid_step_deg": self.water_grid_step_deg,
            "bbox": list(KOREA_BBOX),
            "nodes": self.land_nodes + self.water_nodes,
        }
        self.publisher.publish(String(data=json.dumps(payload, separators=(",", ":"))))
        self.sequence += 1


def main(args=None):
    rclpy.init(args=args)
    node = MapNodePublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
