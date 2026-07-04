#!/usr/bin/env python3

import heapq
import json
import math
import time
from typing import Dict, List, Optional, Tuple

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
        "  ros2 run ammp_pkg route_planner_node\n"
    ) from exc


EARTH_RADIUS_KM = 6371.0088


def normalize_type(value: str) -> str:
    return str(value or "").upper()


def normalize_vehicle_id(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def haversine_km(a: Dict, b: Dict) -> float:
    lat1 = math.radians(float(a["lat"]))
    lon1 = math.radians(float(a["lon"]))
    lat2 = math.radians(float(b["lat"]))
    lon2 = math.radians(float(b["lon"]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def point_segment_distance_km(point: Dict, start: Dict, end: Dict) -> float:
    lat0 = math.radians((float(start["lat"]) + float(end["lat"])) / 2)
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * max(math.cos(lat0), 0.01)

    px = (float(point["lon"]) - float(start["lon"])) * km_per_deg_lon
    py = (float(point["lat"]) - float(start["lat"])) * km_per_deg_lat
    ex = (float(end["lon"]) - float(start["lon"])) * km_per_deg_lon
    ey = (float(end["lat"]) - float(start["lat"])) * km_per_deg_lat
    length_sq = ex * ex + ey * ey
    if length_sq <= 0:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * ex + py * ey) / length_sq))
    return math.hypot(px - t * ex, py - t * ey)


def edge_blocked_by_risk(start: Dict, end: Dict, risk_zones: List[Dict], margin_km: float = 0.0) -> bool:
    for zone in risk_zones:
        radius = float(zone.get("radius_km", 0.0)) + max(0.0, margin_km)
        if radius <= 0:
            continue
        if point_segment_distance_km(zone, start, end) <= radius:
            return True
    return False


def node_inside_risk(node: Dict, risk_zones: List[Dict], margin_km: float = 0.0) -> bool:
    return any(
        haversine_km(node, zone) <= float(zone.get("radius_km", 0.0)) + max(0.0, margin_km)
        for zone in risk_zones
    )


def allowed_node_for_type(node: Dict, vehicle_type: str) -> bool:
    vehicle_type = normalize_type(vehicle_type)
    allowed_types = node.get("allowed_types")
    if isinstance(allowed_types, list) and vehicle_type in {normalize_type(item) for item in allowed_types}:
        return True
    if vehicle_type == "UAV":
        return node.get("domain") in ("land", "water")
    if vehicle_type == "UGV":
        return node.get("domain") == "land"
    if vehicle_type == "USV":
        return node.get("domain") == "water"
    return False


def device_penalty(device_state: str) -> float:
    return {
        "good": 0.0,
        "caution": 35.0,
        "critical": 120.0,
        "disabled": 100000.0,
    }.get(str(device_state or "").lower(), 60.0)


def state_multiplier(multipliers: Dict[str, float], device_state: str) -> float:
    return multipliers.get(str(device_state or "").lower(), multipliers["unknown"])


def offset_point_km(origin: Dict, north_km: float, east_km: float, point_id: str) -> Dict:
    lat = float(origin["lat"]) + north_km / 111.32
    lon_scale = 111.32 * max(math.cos(math.radians(float(origin["lat"]))), 0.01)
    lon = float(origin["lon"]) + east_km / lon_scale
    return {
        "id": point_id,
        "name": point_id,
        "lat": lat,
        "lon": lon,
        "domain": "air",
    }


class RoutePlannerNode(Node):
    def __init__(self):
        super().__init__("route_planner_node")

        self.declare_parameter("battery_weight", 5.0)
        self.declare_parameter("comm_weight", 40.0)
        self.declare_parameter("min_start_battery_pct", 5.0)
        self.declare_parameter("min_arrival_battery_pct", 3.0)
        self.declare_parameter("battery_drain_scale", 1.0)
        self.declare_parameter("uav_battery_pct_per_km", 0.18)
        self.declare_parameter("ugv_battery_pct_per_km", 0.08)
        self.declare_parameter("usv_battery_pct_per_km", 0.06)
        self.declare_parameter("good_battery_multiplier", 1.0)
        self.declare_parameter("caution_battery_multiplier", 1.35)
        self.declare_parameter("critical_battery_multiplier", 2.0)
        self.declare_parameter("unknown_battery_multiplier", 1.5)
        self.declare_parameter("allow_risk_crossing_edges", False)
        self.declare_parameter("risk_crossing_edge_cost_km", math.inf)
        self.declare_parameter("risk_clearance_margin_km", 3.0)
        self.battery_weight = float(self.get_parameter("battery_weight").value)
        self.comm_weight = float(self.get_parameter("comm_weight").value)
        self.allow_risk_crossing_edges = bool(self.get_parameter("allow_risk_crossing_edges").value)
        self.risk_crossing_edge_cost_km = float(self.get_parameter("risk_crossing_edge_cost_km").value)
        if self.risk_crossing_edge_cost_km < 0.0:
            self.risk_crossing_edge_cost_km = math.inf
        self.risk_clearance_margin_km = max(
            0.0,
            float(self.get_parameter("risk_clearance_margin_km").value),
        )
        self.min_start_battery_pct = float(self.get_parameter("min_start_battery_pct").value)
        self.min_arrival_battery_pct = float(self.get_parameter("min_arrival_battery_pct").value)
        self.battery_drain_scale = max(0.0, float(self.get_parameter("battery_drain_scale").value))
        self.battery_pct_per_km = {
            "UAV": max(0.0, float(self.get_parameter("uav_battery_pct_per_km").value)),
            "UGV": max(0.0, float(self.get_parameter("ugv_battery_pct_per_km").value)),
            "USV": max(0.0, float(self.get_parameter("usv_battery_pct_per_km").value)),
        }
        self.battery_multipliers = {
            "good": max(0.0, float(self.get_parameter("good_battery_multiplier").value)),
            "caution": max(0.0, float(self.get_parameter("caution_battery_multiplier").value)),
            "critical": max(0.0, float(self.get_parameter("critical_battery_multiplier").value)),
            "unknown": max(0.0, float(self.get_parameter("unknown_battery_multiplier").value)),
        }

        self.nodes: List[Dict] = []
        self.graph_nodes: Dict[str, Dict] = {}
        self.edges: List[Dict] = []
        self.assets: List[Dict] = []
        self.risk_zones: List[Dict] = []

        self.create_subscription(String, "/missiondeck/map/waypoint_nodes", self.on_nodes, 10)
        self.create_subscription(String, "/missiondeck/map/graph_geojson", self.on_graph, 10)
        self.create_subscription(String, "/missiondeck/map/risk_zones", self.on_risk_zones, 10)
        self.create_subscription(String, "/missiondeck/uxv_states", self.on_assets, 10)
        self.create_subscription(String, "/missiondeck/planner/request", self.on_request, 10)
        self.candidates_publisher = self.create_publisher(String, "/missiondeck/planner/route_candidates", 10)
        self.selected_publisher = self.create_publisher(String, "/missiondeck/planner/selected_route", 10)
        self.log_publisher = self.create_publisher(String, "/c2/autopilot_log", 10)

        self.get_logger().info("Route planner ready: /missiondeck/planner/request -> selected route")

    def on_nodes(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid waypoint node JSON")
            return
        nodes = payload if isinstance(payload, list) else payload.get("nodes", [])
        self.nodes = [node for node in nodes if isinstance(node, dict)]

    def on_graph(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid map graph JSON")
            return

        graph_nodes: Dict[str, Dict] = {}
        edges: List[Dict] = []
        for feature in payload.get("features", []):
            if not isinstance(feature, dict):
                continue
            geometry = feature.get("geometry") or {}
            properties = feature.get("properties") or {}
            geometry_type = geometry.get("type")
            coordinates = geometry.get("coordinates") or []
            if geometry_type == "Point" and len(coordinates) >= 2 and properties.get("id"):
                node = {
                    "id": properties["id"],
                    "name": properties.get("name") or properties["id"],
                    "domain": properties.get("domain"),
                    "node_kind": properties.get("node_kind"),
                    "allowed_types": properties.get("allowed_types", []),
                    "lat": float(coordinates[1]),
                    "lon": float(coordinates[0]),
                }
                graph_nodes[node["id"]] = node
            elif geometry_type == "LineString" and len(coordinates) >= 2:
                if not properties.get("from") or not properties.get("to"):
                    continue
                edges.append({
                    "id": properties.get("id") or f"EDGE-{properties['from']}-{properties['to']}",
                    "from": properties["from"],
                    "to": properties["to"],
                    "domain": properties.get("domain"),
                    "distance_m": float(properties.get("distance_m", 0.0)),
                    "coordinates": coordinates,
                })

        if graph_nodes:
            self.graph_nodes = graph_nodes
            self.edges = edges
            self.nodes = list(graph_nodes.values())

    def on_risk_zones(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid risk zone JSON")
            return
        zones = payload if isinstance(payload, list) else payload.get("zones", [])
        self.risk_zones = [zone for zone in zones if isinstance(zone, dict)]

    def on_assets(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid UxV state JSON")
            return
        assets = payload if isinstance(payload, list) else payload.get("assets", [])
        self.assets = [asset for asset in assets if isinstance(asset, dict)]

    def on_request(self, msg: String) -> None:
        try:
            request = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning("Ignoring invalid planner request JSON")
            return

        target_node_id = request.get("target_node_id")
        vehicle_type = normalize_type(request.get("vehicle_type") or request.get("selected_category"))
        requested_asset_id = request.get("vehicle_id") or request.get("asset_id") or request.get("selected_vehicle_id")
        request_id = request.get("request_id") or f"REQ-{int(time.time() * 1000)}"
        mission_type = str(request.get("mission_type") or request.get("command") or "MOVE_TO").upper()
        try:
            patrol_radius_km = max(0.0, float(request.get("patrol_radius_km", 0.0)))
        except (TypeError, ValueError):
            patrol_radius_km = 0.0
        patrol_direction = str(request.get("patrol_direction") or "clockwise").lower()
        if patrol_direction not in ("clockwise", "counterclockwise"):
            patrol_direction = "clockwise"
        if not target_node_id or not vehicle_type:
            self.publish_no_route(
                request_id,
                "request must include target_node_id and vehicle_type",
                requested_asset_id=requested_asset_id,
                target_node_id=target_node_id,
            )
            return

        target_node = next((node for node in self.nodes if node.get("id") == target_node_id), None)
        if not target_node:
            self.publish_no_route(
                request_id,
                f"target node not found: {target_node_id}",
                requested_asset_id=requested_asset_id,
                target_node_id=target_node_id,
            )
            return
        if not allowed_node_for_type(target_node, vehicle_type):
            self.publish_no_route(
                request_id,
                f"{vehicle_type} cannot use target node {target_node_id}",
                requested_asset_id=requested_asset_id,
                target_node_id=target_node_id,
            )
            return

        candidates = []
        for asset in self.assets:
            if normalize_type(asset.get("type")) != vehicle_type:
                continue
            if requested_asset_id and normalize_vehicle_id(asset.get("id")) != normalize_vehicle_id(requested_asset_id):
                continue
            candidates.append(self.plan_for_asset(
                request_id,
                asset,
                target_node,
                vehicle_type,
                mission_type,
                allow_manual_override=bool(requested_asset_id),
            ))

        if requested_asset_id and not candidates:
            self.publish_no_route(
                request_id,
                f"selected asset not found or type mismatch: {requested_asset_id}",
                requested_asset_id=requested_asset_id,
                target_node_id=target_node_id,
            )
            return

        feasible = [candidate for candidate in candidates if candidate.get("feasible")]
        selected = min(feasible, key=lambda candidate: candidate["total_cost"]) if feasible else None
        payload = {
            "schema": "missiondeck.planner.route_candidates.v1",
            "request_id": request_id,
            "target_node_id": target_node_id,
            "vehicle_type": vehicle_type,
            "mission_type": mission_type,
            "patrol_radius_km": patrol_radius_km,
            "patrol_direction": patrol_direction,
            "requested_asset_id": requested_asset_id,
            "candidates": candidates,
        }
        self.candidates_publisher.publish(String(data=json.dumps(payload, separators=(",", ":"))))

        if not selected:
            self.publish_no_route(
                request_id,
                "no feasible route",
                candidates,
                requested_asset_id=requested_asset_id,
                target_node_id=target_node_id,
            )
            return

        selected["mission_type"] = mission_type
        selected["command"] = mission_type
        if mission_type == "PATROL":
            selected["patrol_radius_km"] = patrol_radius_km
            selected["patrol_direction"] = patrol_direction

        selected_payload = {
            "schema": "missiondeck.planner.selected_route.v1",
            "request_id": request_id,
            "mission_type": mission_type,
            "patrol_radius_km": patrol_radius_km,
            "patrol_direction": patrol_direction,
            "selected": selected,
            "target_node": target_node,
            "risk_zones": self.risk_zones,
        }
        self.selected_publisher.publish(String(data=json.dumps(selected_payload, separators=(",", ":"))))
        self.log_publisher.publish(String(data=json.dumps({
            "type": "auto",
            "text": (
                f"Planner selected {selected['asset_id']} for {target_node_id}: "
                f"{selected['distance_km']:.1f} km, cost {selected['total_cost']:.1f}, "
                f"battery estimate {selected['estimated_battery_after_pct']:.1f}%."
            ),
        }, separators=(",", ":"))))

    def publish_no_route(
        self,
        request_id: str,
        reason: str,
        candidates: Optional[List[Dict]] = None,
        requested_asset_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
    ) -> None:
        payload = {
            "schema": "missiondeck.planner.selected_route.v1",
            "request_id": request_id,
            "requested_asset_id": requested_asset_id,
            "target_node_id": target_node_id,
            "selected": None,
            "reason": reason,
            "candidates": candidates or [],
        }
        self.selected_publisher.publish(String(data=json.dumps(payload, separators=(",", ":"))))
        self.log_publisher.publish(String(data=json.dumps({
            "type": "warning",
            "text": f"Planner found no feasible route: {reason}",
        }, separators=(",", ":"))))

    def plan_for_asset(
        self,
        request_id: str,
        asset: Dict,
        target_node: Dict,
        vehicle_type: str,
        mission_type: str = "MOVE_TO",
        allow_manual_override: bool = False,
    ) -> Dict:
        asset_id = asset.get("id", "UNKNOWN")
        position = asset.get("position") or {}
        start = {
            "id": f"{asset_id}:START",
            "name": f"{asset_id} current position",
            "lat": float(position.get("lat", asset.get("lat", 0.0))),
            "lon": float(position.get("lon", asset.get("lon", 0.0))),
            "domain": "air" if vehicle_type == "UAV" else target_node.get("domain"),
        }
        device_state_value = str(asset.get("device_state", "unknown")).lower()
        battery = float(asset.get("battery", 0.0))
        comm_quality = float(asset.get("comm_quality", 0.0))
        speed = max(0.1, float(asset.get("speed_mps", 1.0)))

        if device_state_value == "disabled":
            return self.rejected_asset(request_id, asset_id, target_node, "device_state is disabled")
        if battery <= self.min_start_battery_pct:
            return self.rejected_asset(request_id, asset_id, target_node, "battery too low")

        if node_inside_risk(target_node, self.risk_zones, self.risk_clearance_margin_km):
            return self.rejected_asset(request_id, asset_id, target_node, "target node is inside a risk zone")

        if normalize_type(mission_type) == "RETURN_HOME":
            route_plan = self.plan_return_home_route(start, target_node, vehicle_type)
        elif vehicle_type == "UAV":
            route_plan = self.plan_uav_route(start, target_node)
        else:
            route_plan = self.plan_graph_route(start, target_node, vehicle_type)
        if not route_plan.get("feasible"):
            return self.rejected_asset(request_id, asset_id, target_node, route_plan.get("reason", "no feasible route"))

        route_nodes = route_plan["route_nodes"]
        crossing_segments = self.risk_crossing_route_segments(route_nodes)
        if crossing_segments and not self.allow_risk_crossing_edges:
            return self.rejected_asset(
                request_id,
                asset_id,
                target_node,
                f"route crosses risk zone: {', '.join(crossing_segments[:3])}",
            )
        if crossing_segments:
            route_plan["risk_crossing_edge_ids"] = list(dict.fromkeys(
                route_plan.get("risk_crossing_edge_ids", []) + crossing_segments
            ))
            route_plan["risk_cost"] = float(route_plan.get("risk_cost", 0.0)) + (
                len(crossing_segments) * self.risk_crossing_edge_cost_km
            )
        distance_km = route_plan["distance_km"]
        battery_used = self.estimate_battery_used(distance_km, asset, vehicle_type)
        battery_after = battery - battery_used
        if battery_after < self.min_arrival_battery_pct and not allow_manual_override:
            return self.rejected_asset(
                request_id,
                asset_id,
                target_node,
                f"estimated battery after route is below {self.min_arrival_battery_pct:.1f}%",
            )

        risk_cost = float(route_plan.get("risk_cost", 0.0))
        if math.isinf(risk_cost):
            return self.rejected_asset(request_id, asset_id, target_node, "route crosses risk zone with infinite cost")
        route_cost = distance_km
        battery_cost = max(0.0, 35.0 - battery_after) * self.battery_weight
        comm_cost = max(0.0, 1.0 - comm_quality) * self.comm_weight
        condition_cost = device_penalty(device_state_value)
        total_cost = route_cost + risk_cost + battery_cost + comm_cost + condition_cost

        return {
            "request_id": request_id,
            "asset_id": asset_id,
            "vehicle_type": vehicle_type,
            "target_node_id": target_node.get("id"),
            "route_node_ids": [node.get("id") for node in route_nodes],
            "route_points": [{"lat": node["lat"], "lon": node["lon"], "id": node.get("id")} for node in route_nodes],
            "snapped_asset_node_id": route_plan.get("snapped_asset_node_id"),
            "edge_ids": route_plan.get("edge_ids", []),
            "risk_crossing_edge_ids": route_plan.get("risk_crossing_edge_ids", []),
            "distance_m": round(distance_km * 1000.0, 1),
            "distance_km": round(distance_km, 3),
            "eta_sec": round(distance_km * 1000.0 / speed, 1),
            "estimated_battery_used_pct": round(battery_used, 2),
            "estimated_battery_after_pct": round(battery_after, 2),
            "route_cost": round(route_cost, 2),
            "risk_cost": round(risk_cost, 2),
            "battery_cost": round(battery_cost, 2),
            "comm_cost": round(comm_cost, 2),
            "condition_cost": round(condition_cost, 2),
            "total_cost": round(total_cost, 2),
            "feasible": True,
        }

    def rejected_asset(self, request_id: str, asset_id: str, target_node: Dict, reason: str) -> Dict:
        return {
            "request_id": request_id,
            "asset_id": asset_id,
            "target_node_id": target_node.get("id"),
            "route_node_ids": [],
            "route_points": [],
            "total_cost": 100000.0,
            "feasible": False,
            "reason": reason,
        }

    def estimate_battery_used(self, distance_km: float, asset: Dict, vehicle_type: str) -> float:
        base_rate = self.battery_pct_per_km.get(vehicle_type, 0.10)
        multiplier = state_multiplier(self.battery_multipliers, str(asset.get("device_state", "unknown")).lower())
        return distance_km * base_rate * multiplier * self.battery_drain_scale

    def plan_graph_route(self, start: Dict, target: Dict, vehicle_type: str) -> Dict:
        if not self.graph_nodes or not self.edges:
            return {"feasible": False, "reason": "map graph has no explicit edges"}
        if target.get("id") not in self.graph_nodes:
            return {"feasible": False, "reason": f"target node is not in map graph: {target.get('id')}"}

        snap_node = self.snap_asset_to_graph_node(start, vehicle_type)
        if not snap_node:
            return {"feasible": False, "reason": "no graph node can be reached from asset position"}

        path = self.shortest_graph_path(snap_node["id"], target["id"], vehicle_type)
        if not path:
            return {"feasible": False, "reason": "no explicit graph path to target"}

        path_node_ids, edge_ids, graph_distance_km, risk_crossing_edge_ids, risk_cost = path
        path_nodes = [self.graph_nodes[node_id] for node_id in path_node_ids]
        snap_distance_km = haversine_km(start, snap_node)
        route_nodes = [start] + path_nodes
        return {
            "feasible": True,
            "route_nodes": route_nodes,
            "snapped_asset_node_id": snap_node["id"],
            "edge_ids": edge_ids,
            "risk_crossing_edge_ids": risk_crossing_edge_ids,
            "risk_cost": risk_cost,
            "distance_km": snap_distance_km + graph_distance_km,
        }

    def plan_return_home_route(self, start: Dict, target: Dict, vehicle_type: str) -> Dict:
        if vehicle_type in ("UGV", "USV") and target.get("id") in self.graph_nodes:
            graph_route = self.plan_graph_route(start, target, vehicle_type)
            if graph_route.get("feasible"):
                return graph_route
        return self.plan_direct_detour_route(start, target)

    def snap_asset_to_graph_node(self, start: Dict, vehicle_type: str) -> Optional[Dict]:
        candidates = sorted(
            self.graph_nodes.values(),
            key=lambda node: haversine_km(start, node),
        )
        for node in candidates:
            if not allowed_node_for_type(node, vehicle_type):
                continue
            if node_inside_risk(node, self.risk_zones, self.risk_clearance_margin_km):
                continue
            if edge_blocked_by_risk(start, node, self.risk_zones, self.risk_clearance_margin_km):
                continue
            return node
        return None

    def shortest_graph_path(
        self,
        start_node_id: str,
        target_node_id: str,
        vehicle_type: str,
    ) -> Optional[Tuple[List[str], List[str], float, List[str], float]]:
        graph = {node_id: [] for node_id in self.graph_nodes}
        for edge in self.edges:
            edge_domain = edge.get("domain")
            if vehicle_type == "UGV" and edge_domain != "land":
                continue
            if vehicle_type == "USV" and edge_domain != "water":
                continue
            start_node = self.graph_nodes.get(edge.get("from"))
            end_node = self.graph_nodes.get(edge.get("to"))
            if not start_node or not end_node:
                continue
            crosses_risk = (
                node_inside_risk(start_node, self.risk_zones, self.risk_clearance_margin_km)
                or node_inside_risk(end_node, self.risk_zones, self.risk_clearance_margin_km)
                or edge_blocked_by_risk(start_node, end_node, self.risk_zones, self.risk_clearance_margin_km)
            )
            if crosses_risk and not self.allow_risk_crossing_edges:
                continue
            distance_km = max(0.0, float(edge.get("distance_m", 0.0))) / 1000.0
            if distance_km <= 0.0:
                distance_km = haversine_km(start_node, end_node)
            search_cost_km = distance_km + (self.risk_crossing_edge_cost_km if crosses_risk else 0.0)
            graph[start_node["id"]].append((end_node["id"], distance_km, search_cost_km, edge["id"], crosses_risk))
            graph[end_node["id"]].append((start_node["id"], distance_km, search_cost_km, edge["id"], crosses_risk))

        queue = [(0.0, 0.0, start_node_id, [], [], [])]
        visited = set()
        while queue:
            search_cost, travel_cost, node_id, node_path, edge_path, risk_edge_path = heapq.heappop(queue)
            if node_id in visited:
                continue
            next_node_path = node_path + [node_id]
            if node_id == target_node_id:
                return next_node_path, edge_path, travel_cost, risk_edge_path, search_cost - travel_cost
            visited.add(node_id)
            for neighbor_id, travel_edge_cost, search_edge_cost, edge_id, crosses_risk in graph.get(node_id, []):
                if neighbor_id not in visited:
                    heapq.heappush(queue, (
                        search_cost + search_edge_cost,
                        travel_cost + travel_edge_cost,
                        neighbor_id,
                        next_node_path,
                        edge_path + [edge_id],
                        risk_edge_path + ([edge_id] if crosses_risk else []),
                    ))
        return None

    def plan_uav_route(self, start: Dict, target: Dict) -> Dict:
        return self.plan_direct_detour_route(start, target)

    def plan_direct_detour_route(self, start: Dict, target: Dict) -> Dict:
        candidate_routes: List[List[Dict]] = [[start, target]]
        waypoints = self.uav_detour_waypoints()
        candidate_routes.extend([start, waypoint, target] for waypoint in waypoints)
        candidate_routes.extend(
            [start, first, second, target]
            for first in waypoints
            for second in waypoints
            if first["id"] != second["id"]
        )

        best_route = None
        best_distance = float("inf")
        for route_nodes in candidate_routes:
            if any(node_inside_risk(node, self.risk_zones, self.risk_clearance_margin_km) for node in route_nodes[1:]):
                continue
            if any(
                edge_blocked_by_risk(
                    route_nodes[index],
                    route_nodes[index + 1],
                    self.risk_zones,
                    self.risk_clearance_margin_km,
                )
                for index in range(len(route_nodes) - 1)
            ):
                continue
            distance_km = sum(
                haversine_km(route_nodes[index], route_nodes[index + 1])
                for index in range(len(route_nodes) - 1)
            )
            if distance_km < best_distance:
                best_distance = distance_km
                best_route = route_nodes

        if not best_route:
            return {"feasible": False, "reason": "no UAV direct or detour segment avoids risk zones"}
        return {
            "feasible": True,
            "route_nodes": best_route,
            "snapped_asset_node_id": None,
            "edge_ids": [],
            "risk_crossing_edge_ids": [],
            "risk_cost": 0.0,
            "distance_km": best_distance,
        }

    def uav_detour_waypoints(self) -> List[Dict]:
        waypoints = []
        for zone in self.risk_zones:
            radius_km = float(zone.get("radius_km", 0.0)) + 8.0
            if radius_km <= 0.0:
                continue
            for bearing_deg in range(0, 360, 30):
                bearing = math.radians(bearing_deg)
                waypoint = offset_point_km(
                    zone,
                    north_km=math.cos(bearing) * radius_km,
                    east_km=math.sin(bearing) * radius_km,
                    point_id=f"UAV-WP-{zone.get('id', 'RISK')}-{bearing_deg:03d}",
                )
                if not node_inside_risk(waypoint, self.risk_zones, self.risk_clearance_margin_km):
                    waypoints.append(waypoint)
        return waypoints

    def risk_crossing_route_segments(self, route_nodes: List[Dict]) -> List[str]:
        crossing_segments = []
        for index in range(len(route_nodes) - 1):
            start = route_nodes[index]
            end = route_nodes[index + 1]
            if (
                node_inside_risk(start, self.risk_zones, self.risk_clearance_margin_km)
                or node_inside_risk(end, self.risk_zones, self.risk_clearance_margin_km)
                or edge_blocked_by_risk(start, end, self.risk_zones, self.risk_clearance_margin_km)
            ):
                crossing_segments.append(f"{start.get('id', index)}->{end.get('id', index + 1)}")
        return crossing_segments


def main(args=None):
    rclpy.init(args=args)
    node = RoutePlannerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
