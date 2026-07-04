# MissionDeck AMMP ROS2 Topics

This document defines the ROS2 Humble topic interface for the MissionDeck AMMP cost planner.

The planner does not receive a user-selected start point.  
Each UxV's current `position` is treated as that asset's start point.

---

## 1. Cost Planner Node

Recommended node name:

```text
/missiondeck/ammp_planner_node
```

Main responsibility:

```text
1. Receive map graph, risk zones, UxV states, and planner request.
2. Generate feasible routes from each candidate asset's current position to the target.
3. Reject any route that crosses a forbidden risk zone.
4. Compute route cost, condition penalty, alert cost, and approval cost.
5. Publish all route candidates and the selected route.
```

---

## 2. Required Input Topics

The cost planner should subscribe to these topics.

| Topic | Message Type | Description |
|---|---|---|
| `/missiondeck/map/graph_geojson` | `std_msgs/msg/String` | GeoJSON map graph containing nodes and edges |
| `/missiondeck/map/risk_zones_geojson` | `std_msgs/msg/String` | GeoJSON forbidden risk-zone polygons |
| `/missiondeck/uxv_states` | `std_msgs/msg/String` | Current UGV/UAV/USV condition states |
| `/missiondeck/planner/request` | `std_msgs/msg/String` | Target and selected UxV category |

For the MVP, each `std_msgs/msg/String.data` field should contain JSON or GeoJSON text.

---

## 3. `/missiondeck/map/graph_geojson`

### Message Type

```text
std_msgs/msg/String
```

### Purpose

This topic provides the route graph used by UGV and USV path planning.

The graph contains:

- Nodes
- Land edges
- Water edges
- Edge distance values

All GeoJSON `Point` features are treated as nodes.

The planner distinguishes feature roles by GeoJSON geometry type:

| Geometry Type | Planner Meaning |
|---|---|
| `Point` | Node |
| `LineString` | Edge |
| `Polygon` | Forbidden risk zone |

### Example Payload

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [126.9780, 37.5665]
      },
      "properties": {
        "id": "SEOUL",
        "domain": "land"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [129.0756, 35.1796]
      },
      "properties": {
        "id": "BUSAN",
        "domain": "land"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [126.9780, 37.5665],
          [129.0756, 35.1796]
        ]
      },
      "properties": {
        "id": "EDGE_SEOUL_BUSAN",
        "from": "SEOUL",
        "to": "BUSAN",
        "domain": "land",
        "distance_m": 325000.0
      }
    }
  ]
}
```

### Required Node Properties

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique node ID |
| `domain` | string | `land` or `water` |

### Required Edge Properties

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique edge ID |
| `from` | string | Start node ID of this edge |
| `to` | string | End node ID of this edge |
| `domain` | string | `land` or `water` |
| `distance_m` | number | Edge distance in meters |

### Planner Usage

```text
UGV uses only domain = land edges.
USV uses only domain = water edges.
UAV does not need graph edges for normal direct flight.
```

---

## 4. `/missiondeck/map/risk_zones_geojson`

### Message Type

```text
std_msgs/msg/String
```

### Purpose

This topic provides forbidden risk zones.

Risk zones are not treated as high-cost areas.  
They are treated as hard constraints.

```text
Risk-zone crossing route = infeasible route
```

### Example Payload

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [128.10, 35.10],
            [128.40, 35.10],
            [128.40, 35.40],
            [128.10, 35.40],
            [128.10, 35.10]
          ]
        ]
      },
      "properties": {
        "id": "RISK_ZONE_001",
        "name": "forbidden_area",
        "risk_type": "blocked"
      }
    }
  ]
}
```

### Required Properties

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique risk-zone ID |
| `name` | string | Human-readable name |
| `risk_type` | string | Recommended value: `blocked` |

### Planner Usage

```text
1. Before UGV/USV path search, remove graph edges that intersect risk-zone polygons.
2. Before accepting a UAV route, check whether the direct segment intersects risk-zone polygons.
3. If all routes cross risk zones, publish no feasible route.
```

---

## 5. `/missiondeck/uxv_states`

### Message Type

```text
std_msgs/msg/String
```

### Purpose

This topic provides the current state of every UxV.

Each asset's `position` is the route start point for that asset.

### Example Payload

```json
{
  "assets": [
    {
      "id": "UGV-1",
      "type": "UGV",
      "battery": 82,
      "comm_quality": 0.91,
      "device_state": "good",
      "mission_status": "available",
      "speed_mps": 12.0,
      "position": {
        "lat": 37.5665,
        "lon": 126.9780
      },
      "current_mission": null
    },
    {
      "id": "USV-1",
      "type": "USV",
      "battery": 76,
      "comm_quality": 0.73,
      "device_state": "caution",
      "mission_status": "available",
      "speed_mps": 8.0,
      "position": {
        "lat": 35.1000,
        "lon": 129.2000
      },
      "current_mission": null
    },
    {
      "id": "UAV-1",
      "type": "UAV",
      "battery": 88,
      "comm_quality": 0.84,
      "device_state": "good",
      "mission_status": "available",
      "speed_mps": 18.0,
      "position": {
        "lat": 36.3504,
        "lon": 127.3845
      },
      "current_mission": null
    }
  ]
}
```

### Required Asset Fields

| Field | Type | Allowed Values | Planner Usage |
|---|---|---|---|
| `id` | string | Any unique ID | Identify selected/rejected asset |
| `type` | string | `UGV`, `UAV`, `USV` | Match selected category and domain |
| `battery` | number | `0` to `100` | Battery margin and warning penalty |
| `comm_quality` | number | `0.0` to `1.0` | Communication penalty and alert prediction |
| `device_state` | string | `good`, `caution`, `critical`, `disabled` | Device condition penalty or exclusion |
| `mission_status` | string | `available`, `assigned`, `returning` | Availability judgement |
| `speed_mps` | number | Positive number | ETA calculation |
| `position.lat` | number | Latitude | Asset-specific start point |
| `position.lon` | number | Longitude | Asset-specific start point |
| `current_mission` | string or null | Mission ID or `null` | Role conflict and reassignment judgement |

### Device State Rules

| `device_state` | Meaning | Planner Handling |
|---|---|---|
| `good` | Normal condition | Candidate, no penalty |
| `caution` | Low-risk warning condition | Candidate, mild penalty |
| `critical` | High-risk condition | Candidate only if allowed, high penalty |
| `disabled` | Off or unusable | Exclude from candidates |

### Mission Status Rules

| `mission_status` | Meaning | Planner Handling |
|---|---|---|
| `available` | Ready for new mission | Normal candidate |
| `assigned` | Already assigned to another mission | Candidate only if reassignment is allowed |
| `returning` | Returning to base or recovery point | Usually exclude |

### Communication Display Rule

The planner and UI both use `comm_quality`.

```text
0.80 to 1.00 -> 3 signal bars
0.50 to 0.79 -> 2 signal bars
0.00 to 0.49 -> 1 signal bar
```

---

## 6. `/missiondeck/planner/request`

### Message Type

```text
std_msgs/msg/String
```

### Purpose

This topic sends the user's planning request.

The request contains only the target and selected UxV category.  
It must not contain a start point.

### Target Node Example

```json
{
  "request_id": "REQ-001",
  "target_node_id": "BUSAN",
  "selected_category": "UGV"
}
```

### Target Coordinate Example

```json
{
  "request_id": "REQ-002",
  "target": {
    "lat": 35.1796,
    "lon": 129.0756
  },
  "selected_category": "UAV"
}
```

### Required Fields

| Field | Type | Allowed Values | Description |
|---|---|---|---|
| `request_id` | string | Any unique ID | Planning request ID |
| `target_node_id` | string | Existing graph node ID | Target node selected by the user |
| `target` | object | `{ "lat": number, "lon": number }` | Optional direct target coordinate |
| `selected_category` | string | `UGV`, `UAV`, `USV` | User-selected UxV category |

Use either `target_node_id` or `target`.

### Planner Usage

```text
1. Filter assets by selected_category.
2. Use each candidate asset's current position as its start point.
3. For UGV/USV, snap the asset position to the nearest compatible graph node.
4. For UAV, plan from the asset position to the target directly or through safe waypoints.
5. Reject routes that cross risk zones.
6. Compute total cost for each feasible candidate.
```

---

## 7. Optional Input Topic

## `/missiondeck/planner/cost_weights`

### Message Type

```text
std_msgs/msg/String
```

### Purpose

This topic can override cost-function weights at runtime.

For the MVP, these values can also be ROS2 parameters instead of a topic.

### Example Payload

```json
{
  "w_distance": 1.0,
  "w_eta": 0.5,
  "w_battery": 40.0,
  "w_comm": 20.0,
  "w_device_state": 25.0,
  "w_alert": 10.0,
  "w_approval": 30.0
}
```

### Required Fields

| Field | Type | Description |
|---|---|---|
| `w_distance` | number | Weight for route distance |
| `w_eta` | number | Weight for ETA |
| `w_battery` | number | Weight for battery penalty |
| `w_comm` | number | Weight for communication penalty |
| `w_device_state` | number | Weight for device condition penalty |
| `w_alert` | number | Weight for expected alert count |
| `w_approval` | number | Weight for expected approval count |

---

## 8. Planner Output Topics

The cost planner should publish these topics.

| Topic | Message Type | Description |
|---|---|---|
| `/missiondeck/planner/route_candidates` | `std_msgs/msg/String` | Feasible and rejected asset-route candidates |
| `/missiondeck/planner/selected_route` | `std_msgs/msg/String` | Recommended asset and path |
| `/missiondeck/planner/no_feasible_route` | `std_msgs/msg/String` | Published when all candidates are infeasible |

---

## 9. `/missiondeck/planner/route_candidates`

### Message Type

```text
std_msgs/msg/String
```

### Example Payload

```json
{
  "request_id": "REQ-001",
  "candidates": [
    {
      "asset_id": "UGV-1",
      "asset_type": "UGV",
      "asset_position": {
        "lat": 37.5665,
        "lon": 126.9780
      },
      "snapped_asset_node_id": "SEOUL",
      "target_node_id": "BUSAN",
      "route_node_ids": ["SEOUL", "DAEJEON", "DAEGU", "BUSAN"],
      "distance_m": 325000.0,
      "eta_sec": 27083.3,
      "route_cost": 338541.7,
      "condition_penalty": 15.0,
      "alert_cost": 10.0,
      "approval_cost": 0.0,
      "total_cost": 338566.7,
      "feasible": true,
      "rejected_reason": null
    },
    {
      "asset_id": "UGV-2",
      "asset_type": "UGV",
      "asset_position": {
        "lat": 37.4000,
        "lon": 127.1000
      },
      "snapped_asset_node_id": null,
      "target_node_id": "BUSAN",
      "route_node_ids": [],
      "distance_m": null,
      "eta_sec": null,
      "route_cost": null,
      "condition_penalty": null,
      "alert_cost": null,
      "approval_cost": null,
      "total_cost": null,
      "feasible": false,
      "rejected_reason": "device_state is disabled"
    }
  ]
}
```

### Candidate Fields

| Field | Type | Description |
|---|---|---|
| `asset_id` | string | Candidate asset ID |
| `asset_type` | string | `UGV`, `UAV`, or `USV` |
| `asset_position` | object | Actual asset start position |
| `snapped_asset_node_id` | string or null | Nearest compatible graph node for UGV/USV |
| `target_node_id` | string or null | Target node ID |
| `route_node_ids` | array | Graph path node IDs |
| `distance_m` | number or null | Route distance |
| `eta_sec` | number or null | Estimated travel time |
| `route_cost` | number or null | Distance and ETA cost |
| `condition_penalty` | number or null | Battery, comm, device-state, and availability penalty |
| `alert_cost` | number or null | Expected alert cost |
| `approval_cost` | number or null | Expected approval cost |
| `total_cost` | number or null | Final AMMP cost |
| `feasible` | boolean | Whether this candidate can be used |
| `rejected_reason` | string or null | Rejection reason if infeasible |

---

## 10. `/missiondeck/planner/selected_route`

### Message Type

```text
std_msgs/msg/String
```

### Example Payload

```json
{
  "request_id": "REQ-001",
  "selected": {
    "asset_id": "UGV-1",
    "asset_type": "UGV",
    "asset_position": {
      "lat": 37.5665,
      "lon": 126.9780
    },
    "snapped_asset_node_id": "SEOUL",
    "target_node_id": "BUSAN",
    "route_node_ids": ["SEOUL", "DAEJEON", "DAEGU", "BUSAN"],
    "distance_m": 325000.0,
    "eta_sec": 27083.3,
    "total_cost": 338566.7,
    "expected_alerts": [
      {
        "type": "battery_warning",
        "severity": "medium",
        "message": "Expected battery below return threshold near target."
      }
    ],
    "expected_approvals": []
  }
}
```

### Planner Usage

This topic is consumed by:

- UI route display
- Mission assignment node
- Decision packet node
- Metrics node

---

## 11. `/missiondeck/planner/no_feasible_route`

### Message Type

```text
std_msgs/msg/String
```

### Example Payload

```json
{
  "request_id": "REQ-001",
  "selected_category": "UGV",
  "target_node_id": "BUSAN",
  "reason": "No feasible UGV route to target.",
  "details": [
    {
      "asset_id": "UGV-1",
      "reason": "All land graph paths cross forbidden risk zones."
    },
    {
      "asset_id": "UGV-2",
      "reason": "device_state is disabled"
    }
  ]
}
```

---

## 12. Cost Function Inputs Derived From Topics

The cost function should not subscribe to topics directly if it is implemented as a pure Python function.

Instead, the ROS2 planner node subscribes to the topics, parses the messages, generates route objects, and passes these values into the cost function.

```text
route_distance_m
eta_sec
battery_penalty
comm_penalty
device_state_penalty
availability_penalty
alert_cost
approval_cost
```

Recommended cost structure:

```text
total_cost =
w_distance * route_distance_m
+ w_eta * eta_sec
+ w_battery * battery_penalty
+ w_comm * comm_penalty
+ w_device_state * device_state_penalty
+ w_alert * expected_alert_count
+ w_approval * expected_approval_count
```

Risk zones are not included as a weighted cost term.

```text
If route intersects risk zone:
    feasible = false
```

---

## 13. Route Distance Definition

### UGV / USV

```text
route_distance_m =
distance(asset.position, snapped_asset_node)
+ sum(edge.distance_m for graph path from snapped_asset_node to target_node)
```

### UAV

```text
route_distance_m =
direct or waypoint distance from asset.position to target position
```

If a direct UAV segment crosses a risk zone, the planner should either generate safe waypoints or mark the route infeasible.

---

## 14. Recommended MVP QoS

For simple simulator usage:

```text
Reliability: reliable
Durability: transient_local for map topics
Durability: volatile for state/request topics
History: keep_last
Depth: 1 for map topics
Depth: 10 for state/request/output topics
```

Recommended per topic:

| Topic | Reliability | Durability | Depth |
|---|---|---|---|
| `/missiondeck/map/graph_geojson` | reliable | transient_local | 1 |
| `/missiondeck/map/risk_zones_geojson` | reliable | transient_local | 1 |
| `/missiondeck/uxv_states` | reliable | volatile | 10 |
| `/missiondeck/planner/request` | reliable | volatile | 10 |
| `/missiondeck/planner/route_candidates` | reliable | volatile | 10 |
| `/missiondeck/planner/selected_route` | reliable | volatile | 10 |
| `/missiondeck/planner/no_feasible_route` | reliable | volatile | 10 |
