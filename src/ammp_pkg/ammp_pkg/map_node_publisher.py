#!/usr/bin/env python3

import json
import math
from pathlib import Path
import random
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
EARTH_RADIUS_KM = 6371.0088
SEJONG_CITY_CENTER = {"lat": 36.480132, "lon": 127.289021}
HEADQUARTERS = {
    "id": "HEADQUARTERS",
    "name": "Headquarters",
    "lat": 35.124333,
    "lon": 129.064000,
    "domain": "land",
    "node_kind": "headquarters",
    "allowed_types": ["UAV", "UGV", "USV"],
}


def haversine_km(a: Dict, b: Dict) -> float:
    lat1 = math.radians(float(a["lat"]))
    lon1 = math.radians(float(a["lon"]))
    lat2 = math.radians(float(b["lat"]))
    lon2 = math.radians(float(b["lon"]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def find_default_geojson(filename: str) -> str:
    filename = Path("res") / filename
    candidates = [Path.cwd() / filename, Path("/home/hannibal/d4d_ws") / filename]
    candidates.extend(parent / filename for parent in Path(__file__).resolve().parents)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(Path("/home/hannibal/d4d_ws") / filename)


DEFAULT_LAND_MASK_GEOJSON = find_default_geojson("TL_SCCO_CTPRVN.json")
DEFAULT_MUNICIPALITY_GEOJSON = find_default_geojson("skorea_municipalities_geo_simple.json")
DEFAULT_ISLAND_LAND_NODE_NAMES = [
    "강화군",
    "거제시",
    "남해군",
    "서귀포시",
    "신안군",
    "옹진군",
    "완도군",
    "울릉군",
    "제주시",
    "진도군",
]


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


def top_level_metro_city(properties: Dict) -> bool:
    name = properties.get("CTP_KOR_NM") or properties.get("name") or ""
    return name.endswith(("특별시", "광역시", "특별자치시"))


def generate_metro_city_nodes(geojson: Dict) -> List[Dict]:
    nodes = []
    for index, feature in enumerate(geojson.get("features", []), start=1):
        properties = feature.get("properties") or {}
        if not top_level_metro_city(properties):
            continue
        bbox = geometry_bbox((feature.get("geometry") or {}).get("coordinates"))
        if not bbox:
            continue
        code = properties.get("CTPRVN_CD") or f"{index:02d}"
        name = properties.get("CTP_KOR_NM") or properties.get("CTP_ENG_NM") or properties.get("name") or f"Land node {index}"
        min_lon, min_lat, max_lon, max_lat = bbox
        nodes.append({
            "id": f"LAND-METRO-{code}",
            "name": name,
            "domain": "land",
            "node_kind": "metro_city_waypoint",
            "allowed_types": ["UGV", "UAV"],
            "lat": round((min_lat + max_lat) / 2, 7),
            "lon": round((min_lon + max_lon) / 2, 7),
        })
    return nodes


def city_county_group(properties: Dict) -> Tuple[str, str] | None:
    name = properties.get("name") or properties.get("SIG_KOR_NM") or properties.get("CTP_KOR_NM") or ""
    code = str(properties.get("code") or properties.get("SIG_CD") or "")
    if name.endswith("군"):
        return name, code
    if name.endswith("시"):
        return name, code
    if name.endswith("구") and "시" in name:
        return name.split("시", 1)[0] + "시", code
    return None


def generate_city_county_nodes(
    geojson: Dict,
    excluded_names: set[str],
    island_land_node_names: set[str],
) -> List[Dict]:
    groups: Dict[str, Dict] = {}
    for index, feature in enumerate(geojson.get("features", []), start=1):
        properties = feature.get("properties") or {}
        group = city_county_group(properties)
        if not group:
            continue
        name, code = group
        if name in excluded_names or name in island_land_node_names:
            continue
        bbox = geometry_bbox((feature.get("geometry") or {}).get("coordinates"))
        if not bbox:
            continue
        min_lon, min_lat, max_lon, max_lat = bbox
        group_entry = groups.setdefault(name, {
            "code": code or f"{index:05d}",
            "bbox": [min_lon, min_lat, max_lon, max_lat],
        })
        group_entry["bbox"][0] = min(group_entry["bbox"][0], min_lon)
        group_entry["bbox"][1] = min(group_entry["bbox"][1], min_lat)
        group_entry["bbox"][2] = max(group_entry["bbox"][2], max_lon)
        group_entry["bbox"][3] = max(group_entry["bbox"][3], max_lat)

    nodes = []
    for name, entry in sorted(groups.items(), key=lambda item: item[0]):
        min_lon, min_lat, max_lon, max_lat = entry["bbox"]
        node_kind = "county_waypoint" if name.endswith("군") else "city_waypoint"
        nodes.append({
            "id": f"LAND-MUNI-{entry['code']}",
            "name": name,
            "domain": "land",
            "node_kind": node_kind,
            "allowed_types": ["UGV", "UAV"],
            "lat": round((min_lat + max_lat) / 2, 7),
            "lon": round((min_lon + max_lon) / 2, 7),
        })
    return nodes


def generate_land_nodes(
    province_geojson: Dict,
    municipality_geojson: Dict,
    island_land_node_names: set[str],
) -> List[Dict]:
    metro_nodes = generate_metro_city_nodes(province_geojson)
    excluded_names = {"세종시" if node["name"] == "세종특별자치시" else node["name"] for node in metro_nodes}
    return metro_nodes + generate_city_county_nodes(
        municipality_geojson,
        excluded_names,
        island_land_node_names,
    )


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


def segment_matches_domain(
    land_mask: LandMask,
    start: Dict,
    end: Dict,
    domain: str,
    sample_count: int = 12,
) -> bool:
    for index in range(sample_count + 1):
        ratio = index / sample_count
        lat = float(start["lat"]) + (float(end["lat"]) - float(start["lat"])) * ratio
        lon = float(start["lon"]) + (float(end["lon"]) - float(start["lon"])) * ratio
        is_land = land_mask.contains_land(lon, lat)
        if domain == "land" and not is_land:
            return False
        if domain == "water" and is_land:
            return False
    return True


def make_edge(start: Dict, end: Dict, domain: str) -> Dict:
    distance_km = haversine_km(start, end)
    return {
        "id": f"EDGE-{domain.upper()}-{start['id']}-{end['id']}",
        "from": start["id"],
        "to": end["id"],
        "domain": domain,
        "distance_m": round(distance_km * 1000.0, 3),
        "coordinates": [
            [float(start["lon"]), float(start["lat"])],
            [float(end["lon"]), float(end["lat"])],
        ],
    }


def generate_land_edges(
    land_nodes: List[Dict],
    land_mask: LandMask,
    neighbor_count: int,
    max_edge_km: float,
) -> List[Dict]:
    edges_by_key = {}
    for node in land_nodes:
        neighbors = sorted(
            (candidate for candidate in land_nodes if candidate["id"] != node["id"]),
            key=lambda candidate: haversine_km(node, candidate),
        )
        for neighbor in neighbors[:neighbor_count]:
            distance_km = haversine_km(node, neighbor)
            if distance_km > max_edge_km:
                continue
            if not segment_matches_domain(land_mask, node, neighbor, "land"):
                continue
            key = tuple(sorted((node["id"], neighbor["id"])))
            edges_by_key[key] = make_edge(node, neighbor, "land")
    return list(edges_by_key.values())


def generate_water_edges(
    water_nodes: List[Dict],
    land_mask: LandMask,
    step_deg: float,
) -> List[Dict]:
    by_coordinate = {
        (round(float(node["lon"]), 7), round(float(node["lat"]), 7)): node
        for node in water_nodes
    }
    offsets = [
        (step_deg, 0.0),
        (0.0, step_deg),
        (step_deg, step_deg),
        (step_deg, -step_deg),
    ]
    edges = []
    for node in water_nodes:
        lon = float(node["lon"])
        lat = float(node["lat"])
        for delta_lon, delta_lat in offsets:
            neighbor = by_coordinate.get((round(lon + delta_lon, 7), round(lat + delta_lat, 7)))
            if not neighbor:
                continue
            if not segment_matches_domain(land_mask, node, neighbor, "water"):
                continue
            edges.append(make_edge(node, neighbor, "water"))
    return edges


def graph_geojson(nodes: List[Dict], edges: List[Dict]) -> Dict:
    features = []
    for node in nodes:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(node["lon"]), float(node["lat"])],
            },
            "properties": {
                "id": node["id"],
                "name": node.get("name"),
                "domain": node.get("domain"),
                "node_kind": node.get("node_kind"),
                "allowed_types": node.get("allowed_types", []),
            },
        })
    for edge in edges:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": edge["coordinates"],
            },
            "properties": {
                "id": edge["id"],
                "from": edge["from"],
                "to": edge["to"],
                "domain": edge["domain"],
                "distance_m": edge["distance_m"],
            },
        })
    return {
        "type": "FeatureCollection",
        "features": features,
    }


class MapNodePublisher(Node):
    def __init__(self):
        super().__init__("map_node_publisher")

        self.declare_parameter("land_geojson_path", DEFAULT_LAND_MASK_GEOJSON)
        self.declare_parameter("municipality_geojson_path", DEFAULT_MUNICIPALITY_GEOJSON)
        self.declare_parameter("water_grid_step_deg", 0.25)
        self.declare_parameter("risk_random_seed", 42)
        self.declare_parameter("risk_zone_count", 1)
        self.declare_parameter("risk_radius_km", 60.0)
        self.declare_parameter("risk_center_lat", SEJONG_CITY_CENTER["lat"])
        self.declare_parameter("risk_center_lon", SEJONG_CITY_CENTER["lon"])
        self.declare_parameter("land_edge_neighbor_count", 4)
        self.declare_parameter("land_edge_max_km", 260.0)
        self.declare_parameter("island_land_node_names", DEFAULT_ISLAND_LAND_NODE_NAMES)
        self.declare_parameter("publish_hz", 0.5)
        self.declare_parameter("topic_name", "/missiondeck/map/waypoint_nodes")
        self.declare_parameter("risk_topic_name", "/missiondeck/map/risk_zones")
        self.declare_parameter("graph_topic_name", "/missiondeck/map/graph_geojson")

        self.land_geojson_path = str(self.get_parameter("land_geojson_path").value)
        self.municipality_geojson_path = str(self.get_parameter("municipality_geojson_path").value)
        self.water_grid_step_deg = max(0.05, float(self.get_parameter("water_grid_step_deg").value))
        self.risk_random_seed = int(self.get_parameter("risk_random_seed").value)
        self.risk_zone_count = max(0, int(self.get_parameter("risk_zone_count").value))
        self.risk_radius_km = max(0.1, float(self.get_parameter("risk_radius_km").value))
        self.risk_center = {
            "lat": float(self.get_parameter("risk_center_lat").value),
            "lon": float(self.get_parameter("risk_center_lon").value),
        }
        self.land_edge_neighbor_count = max(1, int(self.get_parameter("land_edge_neighbor_count").value))
        self.land_edge_max_km = max(1.0, float(self.get_parameter("land_edge_max_km").value))
        self.island_land_node_names = {
            str(name).strip()
            for name in self.get_parameter("island_land_node_names").value
            if str(name).strip()
        }
        self.topic_name = str(self.get_parameter("topic_name").value)
        self.risk_topic_name = str(self.get_parameter("risk_topic_name").value)
        self.graph_topic_name = str(self.get_parameter("graph_topic_name").value)
        publish_hz = max(0.1, float(self.get_parameter("publish_hz").value))

        self.geojson = load_geojson(self.land_geojson_path)
        self.municipality_geojson = load_geojson(self.municipality_geojson_path)
        self.land_mask = extract_land_mask(self.geojson, KOREA_BBOX)
        if not self.land_mask.rings:
            raise RuntimeError("No land polygons found. Check land_geojson_path.")

        self.land_nodes = generate_land_nodes(
            self.geojson,
            self.municipality_geojson,
            self.island_land_node_names,
        )
        self.land_nodes.append(dict(HEADQUARTERS))
        self.water_nodes = generate_water_nodes(self.land_mask, self.water_grid_step_deg)
        self.nodes = self.land_nodes + self.water_nodes
        self.land_edges = generate_land_edges(
            self.land_nodes,
            self.land_mask,
            self.land_edge_neighbor_count,
            self.land_edge_max_km,
        )
        self.water_edges = generate_water_edges(self.water_nodes, self.land_mask, self.water_grid_step_deg)
        self.edges = self.land_edges + self.water_edges
        self.graph_payload = graph_geojson(self.nodes, self.edges)
        self.risk_zones = self.generate_risk_zones()
        self.publisher = self.create_publisher(String, self.topic_name, 10)
        self.risk_publisher = self.create_publisher(String, self.risk_topic_name, 10)
        self.graph_publisher = self.create_publisher(String, self.graph_topic_name, 10)
        self.sequence = 0

        self.create_timer(1.0 / publish_hz, self.publish_nodes)
        self.get_logger().info(
            f"Map node publisher ready: {len(self.land_nodes)} land nodes, "
            f"{len(self.water_nodes)} water nodes, "
            f"{len(self.land_edges)} land edges, {len(self.water_edges)} water edges -> "
            f"{self.topic_name}, {self.graph_topic_name}; "
            f"{len(self.risk_zones)} risk zones -> {self.risk_topic_name}"
        )

    def generate_risk_zones(self) -> List[Dict]:
        rng = random.Random(self.risk_random_seed)
        if self.risk_zone_count == 0:
            return []

        zones = [{
            "id": "RISK-01",
            "name": "Risk zone 1",
            "source_node_id": None,
            "source": "configured_center",
            "lat": self.risk_center["lat"],
            "lon": self.risk_center["lon"],
            "radius_km": self.risk_radius_km,
            "severity": "RED",
        }]
        if not self.nodes or self.risk_zone_count == 1:
            return zones

        sample_count = min(self.risk_zone_count - 1, len(self.nodes))
        selected_nodes = rng.sample(self.nodes, sample_count)
        zones.extend(
            {
                "id": f"RISK-{index:02d}",
                "name": f"Risk zone {index}",
                "source_node_id": node["id"],
                "source": "random_node",
                "lat": node["lat"],
                "lon": node["lon"],
                "radius_km": self.risk_radius_km,
                "severity": "RED",
            }
            for index, node in enumerate(selected_nodes, start=2)
        )
        return zones

    def publish_nodes(self) -> None:
        payload = {
            "schema": "missiondeck.map.waypoint_nodes.v1",
            "sequence": self.sequence,
            "land_geojson_path": self.land_geojson_path,
            "municipality_geojson_path": self.municipality_geojson_path,
            "water_grid_step_deg": self.water_grid_step_deg,
            "bbox": list(KOREA_BBOX),
            "nodes": self.nodes,
        }
        self.publisher.publish(String(data=json.dumps(payload, separators=(",", ":"))))
        graph_payload = dict(self.graph_payload)
        graph_payload["schema"] = "missiondeck.map.graph_geojson.v1"
        graph_payload["sequence"] = self.sequence
        self.graph_publisher.publish(String(data=json.dumps(graph_payload, separators=(",", ":"))))
        self.risk_publisher.publish(String(data=json.dumps({
            "schema": "missiondeck.map.risk_zones.v1",
            "sequence": self.sequence,
            "random_seed": self.risk_random_seed,
            "center": self.risk_center,
            "radius_km": self.risk_radius_km,
            "zones": self.risk_zones,
        }, separators=(",", ":"))))
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
