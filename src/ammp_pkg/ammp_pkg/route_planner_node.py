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


def edge_blocked_by_risk(start: Dict, end: Dict, risk_zones: List[Dict]) -> bool:
    for zone in risk_zones:
        radius = float(zone.get("radius_km", 0.0))
        if radius <= 0:
            continue
        if point_segment_distance_km(zone, start, end) <= radius:
            return True
    return False


def node_inside_risk(node: Dict, risk_zones: List[Dict]) -> bool:
    return any(haversine_km(node, zone) <= float(zone.get("radius_km", 0.0)) for zone in risk_zones)


def allowed_node_for_type(node: Dict, vehicle_type: str) -> bool:
    vehicle_type = normalize_type(vehicle_type)
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


def battery_drain_multiplier(device_state: str) -> float:
    return {
        "good": 1.0,
        "caution": 1.8,
        "critical": 3.4,
        "disabled": 10.0,
    }.get(str(device_state or "").lower(), 2.2)


class RoutePlannerNode(Node):
    def __init__(self):
        super().__init__("route_planner_node")

        self.declare_parameter("neighbor_count", 8)
        self.declare_parameter("battery_weight", 5.0)
        self.declare_parameter("comm_weight", 40.0)
        self.neighbor_count = max(2, int(self.get_parameter("neighbor_count").value))
        self.battery_weight = float(self.get_parameter("battery_weight").value)
        self.comm_weight = float(self.get_parameter("comm_weight").value)

        self.nodes: List[Dict] = []
        self.assets: List[Dict] = []
        self.risk_zones: List[Dict] = []

        self.create_subscription(String, "/missiondeck/map/waypoint_nodes", self.on_nodes, 10)
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

        selected_payload = {
            "schema": "missiondeck.planner.selected_route.v1",
            "request_id": request_id,
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
        if not allow_manual_override and not bool(asset.get("assignment_possible", asset.get("assignable", True))):
            return self.rejected_asset(request_id, asset_id, target_node, "assignment_possible is false")
        if battery <= 5.0:
            return self.rejected_asset(request_id, asset_id, target_node, "battery too low")

        domain_nodes = [
            node for node in self.nodes
            if allowed_node_for_type(node, vehicle_type) and not node_inside_risk(node, self.risk_zones)
        ]
        if target_node.get("id") not in {node.get("id") for node in domain_nodes}:
            domain_nodes.append(target_node)

        route_nodes = self.shortest_route(start, target_node, domain_nodes)
        if not route_nodes:
            return self.rejected_asset(request_id, asset_id, target_node, "all route edges cross risk zones")

        distance_km = sum(haversine_km(route_nodes[index], route_nodes[index + 1]) for index in range(len(route_nodes) - 1))
        battery_used = self.estimate_battery_used(distance_km, asset, vehicle_type)
        battery_after = battery - battery_used
        if battery_after < 8.0:
            return self.rejected_asset(request_id, asset_id, target_node, "estimated battery after route is below 8%")

        route_cost = distance_km
        battery_cost = max(0.0, 35.0 - battery_after) * self.battery_weight
        comm_cost = max(0.0, 1.0 - comm_quality) * self.comm_weight
        condition_cost = device_penalty(device_state_value)
        total_cost = route_cost + battery_cost + comm_cost + condition_cost

        return {
            "request_id": request_id,
            "asset_id": asset_id,
            "vehicle_type": vehicle_type,
            "target_node_id": target_node.get("id"),
            "route_node_ids": [node.get("id") for node in route_nodes],
            "route_points": [{"lat": node["lat"], "lon": node["lon"], "id": node.get("id")} for node in route_nodes],
            "distance_km": round(distance_km, 3),
            "eta_sec": round(distance_km * 1000.0 / speed, 1),
            "estimated_battery_used_pct": round(battery_used, 2),
            "estimated_battery_after_pct": round(battery_after, 2),
            "route_cost": round(route_cost, 2),
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
        base_rate = {"UAV": 0.55, "UGV": 0.32, "USV": 0.26}.get(vehicle_type, 0.45)
        return distance_km * base_rate * battery_drain_multiplier(str(asset.get("device_state", "unknown")).lower())

    def shortest_route(self, start: Dict, target: Dict, domain_nodes: List[Dict]) -> Optional[List[Dict]]:
        nodes = [start] + [node for node in domain_nodes if node.get("id") != target.get("id")]
        if not any(node.get("id") == target.get("id") for node in nodes):
            nodes.append(target)

        by_id = {node["id"]: node for node in nodes}
        graph = {node_id: [] for node_id in by_id}
        for node in nodes:
            neighbors = sorted(
                (candidate for candidate in nodes if candidate["id"] != node["id"]),
                key=lambda candidate: haversine_km(node, candidate),
            )[:self.neighbor_count]
            for neighbor in neighbors:
                if edge_blocked_by_risk(node, neighbor, self.risk_zones):
                    continue
                distance = haversine_km(node, neighbor)
                graph[node["id"]].append((neighbor["id"], distance))
                graph[neighbor["id"]].append((node["id"], distance))

        start_id = start["id"]
        target_id = target["id"]
        queue = [(0.0, start_id, [])]
        visited = set()
        while queue:
            cost, node_id, path = heapq.heappop(queue)
            if node_id in visited:
                continue
            next_path = path + [node_id]
            if node_id == target_id:
                return [by_id[route_node_id] for route_node_id in next_path]
            visited.add(node_id)
            for neighbor_id, edge_cost in graph.get(node_id, []):
                if neighbor_id not in visited:
                    heapq.heappush(queue, (cost + edge_cost, neighbor_id, next_path))
        return None


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
