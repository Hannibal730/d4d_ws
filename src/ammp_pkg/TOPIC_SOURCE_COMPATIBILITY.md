# AMMP Topic Source Compatibility

This note checks whether the topics required by `topics.md` can be produced from PX4 or ArduPilot telemetry.

## Summary

AMMP topics are planner-level JSON topics, not native autopilot topics. PX4 and ArduPilot can provide most vehicle telemetry needed for `/missiondeck/uxv_states`, but both require a small ROS adapter to reshape native autopilot messages into the AMMP JSON schema.

Map, risk-zone, planner request, and planner output topics are MissionDeck/AMMP application data. They should be published by MissionDeck nodes or UI/backend nodes, not by PX4 or ArduPilot.

## Required Input Topics

| AMMP topic | Can PX4 publish it directly? | Can ArduPilot publish it directly? | Practical source |
|---|---:|---:|---|
| `/missiondeck/map/graph_geojson` | No | No | MissionDeck map/scenario node publishes `std_msgs/msg/String` GeoJSON with transient local QoS. |
| `/missiondeck/map/risk_zones_geojson` | No | No | MissionDeck map/scenario node publishes `std_msgs/msg/String` GeoJSON with transient local QoS. |
| `/missiondeck/uxv_states` | Not directly | Not directly | PX4 or ArduPilot telemetry adapter publishes AMMP JSON. |
| `/missiondeck/planner/request` | No | No | UI/backend mission request node publishes selected target and UxV category. |
| `/missiondeck/planner/cost_weights` | No | No | Optional AMMP config node or ROS parameters. |

## `/missiondeck/uxv_states` Field Mapping

| AMMP field | PX4 source | ArduPilot source | Notes |
|---|---|---|---|
| `id` | Adapter-defined, for example `PX4_GJ_01` | Adapter-defined, for example `AP_GJ_01` | Autopilots do not define AMMP asset IDs. |
| `type` | Adapter-defined `UAV` for PX4 drone | Adapter-defined `UAV`, `UGV`, or `USV` depending vehicle | Derived from configured platform, not raw telemetry. |
| `battery` | `/fmu/out/battery_status` | MAVROS `/mavros/battery` or equivalent | Convert to percent `0..100`. |
| `comm_quality` | Adapter-derived | Adapter-derived from heartbeat/link stats | Not a standard AMMP field from autopilot; compute or set default. |
| `device_state` | `/fmu/out/vehicle_status` plus failsafe/health if available | `/mavros/state`, diagnostics, EKF/failsafe status | Adapter maps to `good/caution/critical/disabled`. |
| `mission_status` | PX4 nav/arming state from `/fmu/out/vehicle_status` | MAVROS state/mission status | Adapter maps to `available/assigned/returning`. |
| `speed_mps` | `/fmu/out/vehicle_odometry` or local position velocity | MAVROS local velocity or odometry | Compute vector magnitude. |
| `assignment_possible` | Adapter policy from state/failsafe/battery | Adapter policy from state/failsafe/battery | AMMP planner decision flag. |
| `position.lat` | `/fmu/out/vehicle_global_position.lat` | `/mavros/global_position/global.latitude` | Available when global position estimate is valid. |
| `position.lon` | `/fmu/out/vehicle_global_position.lon` | `/mavros/global_position/global.longitude` | Available when global position estimate is valid. |
| `current_mission` | Adapter/MissionDeck assignment state | Adapter/MissionDeck assignment state | Autopilot mission ID is not the same as AMMP mission ID. |

## Current CoreCenter Bridge Status

`src/CoreCenter/ros/px4_to_c2_bridge.py` already proves the PX4 telemetry side for a UAV:

| Current bridge topic | Role |
|---|---|
| subscribes `/fmu/out/vehicle_global_position` | position and altitude |
| subscribes `/fmu/out/battery_status` | battery percent |
| subscribes `/fmu/out/vehicle_odometry` | speed |
| subscribes `/fmu/out/vehicle_status` | PX4 state |
| publishes `/c2/fleet/state` | CoreCenter UI JSON state |

The missing step for AMMP is only schema/topic adaptation:

```text
/fmu/out/*  ->  px4_to_missiondeck_adapter  ->  /missiondeck/uxv_states
```

The existing `/c2/fleet/state` payload is close, but its field names are CoreCenter-specific:

| Current `/c2/fleet/state` | AMMP `/missiondeck/uxv_states` |
|---|---|
| `vehicle_id` | `id` |
| `vehicle_type` | `type` |
| `battery_pct` | `battery` |
| `link_quality` | `comm_quality` |
| `mission_state` | `mission_status` after mapping |
| `lat`, `lon` | `position.lat`, `position.lon` |
| `current_mission` | `current_mission` |
| `assignable` | `assignment_possible` |

## Planner Output Topics

These are not PX4 or ArduPilot telemetry topics. They are produced by the AMMP planner node:

| Topic | Publisher |
|---|---|
| `/missiondeck/planner/route_candidates` | `ammp_planner_node` |
| `/missiondeck/planner/selected_route` | `ammp_planner_node` |
| `/missiondeck/planner/no_feasible_route` | `ammp_planner_node` |

## Verdict

PX4 can supply the live UAV telemetry needed for AMMP, but it cannot publish the AMMP topics directly without an adapter.

ArduPilot can also supply the needed telemetry, usually through MAVROS or an ArduPilot ROS bridge, but it also needs an adapter to publish AMMP JSON.

MissionDeck itself must publish map/risk/request topics and AMMP planner output topics.
