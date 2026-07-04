# AGENTS.md

# MissionDeck AMMP: Alert-Minimizing Mission Planning

## 0. Purpose of This File

This file acts as the primary development guide for Codex or any AI coding agent working on the MissionDeck AMMP project.

The project is designed for the D4D Seoul T1 challenge:

> **1인 다중 무인기 동시 통제 / Multi-UxV Control**

The goal is to develop a 2D web-based simulator and mission control interface where a single operator can assign, monitor, and supervise 3 or more heterogeneous unmanned systems across air, ground, and maritime domains.

The core technical concept is:

> **Alert-Minimizing Mission Planning, AMMP**

AMMP is a mission planning method that considers not only distance, speed, risk, and vehicle condition, but also expected alerts, approval requests, and replanning likelihood. The system recommends a plan that allows the operator to maintain or improve mission success while intervening as little as possible.

---

## 1. Challenge Guideline Summary

The hackathon prompt states:

> 최근 전장에서 드론을 비롯한 UGV, USV 등 다양한 무인 시스템의 운용 비중이 급증하고 있습니다. 그러나 현행 운용 방식은 장비 증가에 비례해 운용 인력 또한 동반 요구되는 선형적 구조 한계를 지니고 있습니다. 이는 인구 절벽 및 병력 감소 직면국, 한국 및 APAC의 장기 전력 운용 측면에서 지속 불가능합니다. 따라서 미래 전장은 단일 운용자가 다수의 무인체계를 통합 감독·제어하는 유무인 복합 체계로의 전환이 필수적입니다.

Required system:

> 단일 운용자가 공중·지상·해상의 이종 UxV 무인체계 3대 이상을 동시에 임무 부여, 감시, 통제할 수 있는 체계를 개발하라.  
> 단일 운용자의 불필요한 개입과 반복 판단을 줄이면서도 임무 성공률을 유지하거나 향상시킬 수 있는 방안을 제시할 것.

Required components:

- 임무 단위 추상화, 개별 조종 → 임무 의도 입력 인터페이스
- 다수 무인기의 자율 임무 분산·역할 할당
- 우선순위 알림 및 불필요한 알림 억제
- 이상·위협 발생 시 사람 개입 지점, human-in-the-loop 설계
- 인력 절감률·임무 성공률 측정 프레임워크

---

## 2. Core Interpretation

The most important interpretation of the challenge is:

> The real-world problem is not simply controlling drones.  
> The real problem is that as UAV, UGV, and USV assets increase, alerts, approvals, manual interventions, and decision burden increase linearly or worse.

MissionDeck AMMP should demonstrate that one operator can supervise multiple heterogeneous UxVs by shifting from vehicle-level control to mission-level intent.

### Requirement Mapping

| Host Requirement | AMMP Response |
|---|---|
| Mission-level abstraction | Operator enters "A구역 복합 정찰" instead of "move UAV-1" |
| Autonomous mission distribution | System assigns UAV, UGV, USV based on condition |
| Alert prioritization | Low-priority alerts are suppressed or grouped |
| Priority alerts | Low-priority alerts are suppressed or grouped |
| Human-in-the-loop | Risk-zone blockage, mission abort, relay reassignment require approval |
| Measurement framework | Mission success rate, alert reduction, approval reduction, response time, manpower reduction |

### Key Novelty

> Alert reduction is not treated only as a UI problem.  
> It is included directly in the mission planning objective function.

The system should not merely display less information.  
It should plan differently so that the operator receives fewer unnecessary alerts, fewer approval requests, and fewer replanning burdens.

---

## 3. Project Identity

### Project Name

**MissionDeck AMMP**

### Full Name

**MissionDeck: Alert-Minimizing Mission Planning for Single-Operator Multi-UxV Control**

### Short Technical Name

**AMMP**

### UI Feature Name

**Quiet Mission Mode**

### One-Line Concept

> AMMP는 가장 빠른 계획이 아니라, 한 명의 운용자가 가장 적게 개입해도 임무가 무너지지 않는 계획을 찾는다.

### Pitch Sentence

> 기존 계획은 기체의 효율을 최적화했다면, AMMP는 기체의 효율과 운용자의 주의력을 함께 최적화합니다.

Another strong pitch sentence:

> AMMP는 최단경로가 아니라 최저개입경로를 찾습니다.

---

## 4. Problem Framing

Traditional Multi-UxV control systems often choose:

```text
가장 가까운 기체를 보낸다.
가장 빠른 경로를 고른다.
배터리가 충분한 기체를 고른다.
임무 가능한 상태의 기체를 고른다.
```

However, this can be suboptimal in a single-operator environment.

Example:

```text
Fast Route:
- 가장 빠름
- 하지만 통신저하 알림 3회 예상
- 위험구역 접근 승인 1회 필요
- 배터리 복귀 경고 1회 예상
```

This route is efficient for the vehicle, but noisy and intervention-heavy for the operator.

AMMP instead assumes:

```text
조금 느리더라도,
알림이 적고,
승인 요청이 적고,
재계획 가능성이 낮고,
현재 운용자가 감당 가능한 경로가 더 좋은 경로일 수 있다.
```

---

## 5. System Overview

The simulator should operate as follows:

```text
1. Operator enters mission intent.
   Example: A구역 복합 정찰

2. System decomposes mission into subtasks.
   - Air reconnaissance
   - Ground check
   - Maritime watch
   - Communication relay

3. System checks UAV, UGV, USV conditions.
   - Position
   - Battery
   - Communication quality
   - Current mission
   - State
   - Autonomy level

4. System allocates roles.
   - UAV-1: air reconnaissance
   - UGV-1: ground check
   - USV-1: maritime watch
   - UAV-2: relay

5. System generates route candidates for each vehicle.
   - Fast Route
   - Safe Route
   - Quiet Route

6. System estimates alert, approval, and replanning burden for each route.

7. System recommends the final plan based on route cost, asset condition, expected alerts, and expected approvals.

8. If the situation requires responsible human judgment, the system generates a Decision Packet for human approval.
```

---

## 6. MVP Scope

The MVP must be a 2D web-based simulator.  
Actual drone flight control, physical robot control, and full 3D physics simulation are not required.

### Must Implement

- 2D mission map
- UAV, UGV, USV display
- At least 3 UxVs, preferably 4:
  - UAV-1
  - UAV-2
  - UGV-1
  - USV-1
- Asset condition editor
- Mission intent panel
- Automatic mission decomposition
- Condition-aware task allocation
- Fast / Safe / Quiet route comparison
- AMMP cost function
- Alert prediction
- Approval prediction
- Decision Packet generation
- Human-in-the-loop approval UI
- Mission metrics and final report

### Nice to Have

- ROS2 Humble nodes
- WebSocket real-time updates
- Natural language mission input
- ROSBridge support
- Gazebo or Webots integration

### Not Required for MVP

- Real drone control
- Full physics simulation
- Full ROS2 Nav2 integration
- Reinforcement learning
- Real video input
- Military-grade geospatial map

---

## 7. Recommended Technology Stack

| Area | Recommended Tech |
|---|---|
| Frontend | React + TypeScript |
| 2D Map | SVG, HTML Canvas, or Konva.js |
| Backend | FastAPI |
| ROS | ROS2 Humble + rclpy |
| Communication | REST + WebSocket |
| Algorithm | Python |
| Data | JSON files or SQLite |
| Visualization | 2D grid map |

If time is limited, implement the simulator first with React + FastAPI + Python logic.  
Then optionally wrap backend logic into ROS2 nodes.

---

## 8. Repository Structure

Use this structure unless there is a strong reason not to:

```text
missiondeck-ammp/
├── AGENTS.md
├── README.md
├── docs/
│   ├── concept.md
│   ├── demo_scenario.md
│   └── architecture.md
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── assets.py
│   │   ├── missions.py
│   │   ├── routes.py
│   │   ├── decisions.py
│   │   └── metrics.py
│   ├── core/
│   │   ├── models.py
│   │   ├── mission_intent.py
│   │   ├── task_allocation.py
│   │   ├── path_planning.py
│   │   ├── alert_prediction.py
│   │   ├── decision_packet.py
│   │   ├── metrics.py
│   │   └── ammp.py
│   └── data/
│       ├── default_assets.json
│       ├── default_map.json
│       └── default_scenario.json
├── frontend/
│   ├── package.json
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts
│       ├── components/
│       │   ├── MapCanvas.tsx
│       │   ├── MissionIntentPanel.tsx
│       │   ├── AssetConditionPanel.tsx
│       │   ├── RouteComparisonPanel.tsx
│       │   ├── DecisionPacketPanel.tsx
│       │   └── MetricsPanel.tsx
│       └── types.ts
└── ros2_ws/
    └── src/
        └── missiondeck_ros/
            ├── package.xml
            ├── setup.py
            └── missiondeck_ros/
                ├── scenario_manager_node.py
                ├── asset_state_node.py
                ├── mission_intent_node.py
                ├── task_allocator_node.py
                ├── ammp_planner_node.py
                ├── alert_predictor_node.py
                ├── decision_packet_node.py
                ├── metrics_node.py
                └── web_bridge_node.py
```

---

## 9. Data Models

### 9.1 Asset

```json
{
  "id": "UAV-1",
  "type": "UAV",
  "position": { "lat": 37.5665, "lon": 126.9780 },
  "battery": 82,
  "speed_mps": 18,
  "comm_quality": 0.91,
  "device_state": "good",
  "mission_status": "available",
  "assignment_possible": true,
  "video_topic": "/missiondeck/uxv/UAV-1/video/compressed",
  "risk_tolerance": "medium",
  "autonomy_level": 3,
  "current_mission": null
}
```

### Asset Fields

| Field | Type | Meaning |
|---|---|---|
| id | string | Asset identifier |
| type | UAV / UGV / USV | Vehicle domain |
| position | lat, lon | Geographic position |
| battery | number | 0 to 100 |
| speed_mps | number | Speed in meters per second |
| comm_quality | number | 0.0 to 1.0, used for both planning cost and UI signal display |
| device_state | good / caution / critical / disabled | Physical/device condition state |
| mission_status | available / assigned / returning | Mission/lifecycle status |
| assignment_possible | boolean | Whether this asset can receive a new mission |
| video_topic | string or null | Video stream topic for selected asset detail |
| risk_tolerance | low / medium / high | Risk acceptance |
| autonomy_level | 1 to 5 | Human approval level |
| current_mission | string or null | Assigned mission |

### Communication Display

Use `comm_quality` for both planning and UI display.

```text
comm_quality 0.80 to 1.00 -> 3 signal bars
comm_quality 0.50 to 0.79 -> 2 signal bars
comm_quality 0.00 to 0.49 -> 1 signal bar
```

### 9.2 Default Assets

| Asset | Type | Role |
|---|---|---|
| UAV-1 | UAV | Air recon |
| UAV-2 | UAV | Relay, auxiliary recon |
| UGV-1 | UGV | Ground check |
| USV-1 | USV | Maritime watch |

### 9.3 Mission

```json
{
  "id": "M-001",
  "type": "complex_recon",
  "target_node_id": "BUSAN",
  "target": { "lat": 35.1796, "lon": 129.0756 },
  "priority": "high",
  "required_actions": ["air_recon", "ground_check", "maritime_watch", "relay"],
  "domain_preference": "auto",
  "risk_level": "medium",
  "autonomy_level": 3,
  "deadline_sec": 480,
  "constraints": {
    "avoid_risk_zone": true,
    "return_battery_threshold": 30
  }
}
```

### 9.4 Route Candidate

```json
{
  "id": "quiet",
  "asset_id": "UAV-1",
  "mission_id": "M-001",
  "route_type": "Quiet Route",
  "path": [
    { "x": 4, "y": 4 },
    { "x": 5, "y": 4 },
    { "x": 6, "y": 5 }
  ],
  "eta_sec": 310,
  "distance": 510,
  "expected_alerts": 1,
  "expected_approvals": 0,
  "risk_score": 31,
  "comm_risk": 0.18,
  "total_cost": 430
}
```

### 9.5 Decision Packet

```json
{
  "id": "DP-003",
  "title": "A구역 정찰 임무 인계",
  "severity": "high",
  "summary": "UAV-1 battery dropped to 18%. UAV-2 can take over recon, but relay quality may decrease by 12%.",
  "recommendation": "UAV-1 복귀 + UAV-2 정찰 인계",
  "options": [
    {
      "id": "approve_recommended",
      "label": "추천안 승인",
      "effects": {
        "mission_success_rate": 0.84,
        "comm_quality_delta": -0.12,
        "additional_approvals": 1
      }
    },
    {
      "id": "keep_relay",
      "label": "통신중계 유지",
      "effects": {
        "mission_success_rate": 0.72,
        "comm_quality_delta": 0.0,
        "additional_approvals": 0
      }
    },
    {
      "id": "pause_recon",
      "label": "정찰 임무 보류",
      "effects": {
        "mission_success_rate": 0.58,
        "comm_quality_delta": 0.0,
        "additional_approvals": 0
      }
    }
  ]
}
```

---

## 10. 2D Map Model

### Cell Types

| Cell Type | Meaning | Default Cost |
|---|---|---:|
| normal | Normal area | 1 |
| risk_zone | Forbidden dangerous area | blocked |
| comm_shadow | Communication shadow | 20 |
| civilian_sensitive | Civilian-sensitive zone | 40 |
| obstacle | Obstacle | blocked |
| water | Maritime area | USV only |
| land | Ground area | UGV possible |
| air_corridor | Air route | UAV possible |

### Movement Rules

| Asset Type | Movement Rule |
|---|---|
| UAV | Can fly direct or via waypoints, but cannot cross risk zones |
| UGV | Can move on land/normal edges only, cannot move on water or risk zones |
| USV | Can move on water edges only, cannot move on land or risk zones |
| Relay UAV | Similar to UAV, but route selection prioritizes stable communication coverage |

### Hard Constraint Zones

Risk zones are not high-cost areas.  
They are hard constraints.

```text
If an edge or UAV line segment intersects a risk zone:
- Remove that edge or segment from the candidate graph.
- Do not include it in route candidates.
- Return no feasible route if every path requires risk-zone entry.
```

This means the planner should not model risk-zone entry as a large cost penalty.  
Risk-zone violation is infeasible, not merely expensive.

### Geospatial Input Format

Use GeoJSON as the primary map input format.

GeoJSON is preferred over CSV because MissionDeck AMMP needs to represent:

- nodes as `Point` features
- UGV and USV paths as `LineString` features
- risk zones as `Polygon` features
- route visualization on a 2D geographic map
- geometric intersection checks between routes and risk zones

CSV can still be supported as a simple test/debug import format, but it should not be the main source of truth for map geometry.

Recommended files:

```text
data/
├── map_graph.geojson
├── risk_zones.geojson
└── default_assets.json
```

Node example:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [126.9780, 37.5665]
  },
  "properties": {
    "id": "SEOUL",
    "name": "Seoul",
    "domain": "land"
  }
}
```

Edge example:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [126.9780, 37.5665],
      [127.3845, 36.3504]
    ]
  },
  "properties": {
    "id": "E_SEOUL_DAEJEON",
    "from": "SEOUL",
    "to": "DAEJEON",
    "domain": "land",
    "allowed_types": ["UGV"],
    "distance_m": 160000
  }
}
```

### Destination and Detour Waypoint Nodes

MissionDeck AMMP uses map nodes for both mission destinations and risk-zone detour waypoints.

Node generation is owned by ROS2, not by the browser UI:

- `map_node_publisher.py` publishes `/missiondeck/map/waypoint_nodes`.
- `app.js` subscribes to that ROS2 topic through ROSBridge and only visualizes the received nodes.
- Land nodes are generated from the center of each administrative city/province feature in `TL_SCCO_CTPRVN.json`.
- Water nodes are generated at every configured grid intersection that is not inside a land polygon.
- UAV can use both land and water nodes as optional waypoints.
- UGV can use only land nodes.
- USV can use only water nodes.

Waypoint-node topic example:

```json
{
  "schema": "missiondeck.map.waypoint_nodes.v1",
  "water_grid_step_deg": 0.25,
  "nodes": [
    {
      "id": "LAND-11",
      "name": "서울특별시",
      "domain": "land",
      "node_kind": "destination_waypoint",
      "allowed_types": ["UGV", "UAV"],
      "lat": 37.5665,
      "lon": 126.9780
    },
    {
      "id": "WATER-0001",
      "name": "Water grid 1",
      "domain": "water",
      "node_kind": "destination_waypoint",
      "allowed_types": ["USV", "UAV"],
      "lat": 34.0000,
      "lon": 128.0000
    }
  ]
}
```

---

## 11. Mission Intent Parser

The operator should not select each vehicle manually as the default mode.  
Instead, the operator sets mission intent.

### Example Input

```text
임무유형: 복합 정찰
대상지역: A구역
우선순위: 높음
작전환경: 해안 + 도심
위협수준: 보통
필요행동:
- 상공 정찰
- 지상 확인
- 해안 감시
- 통신 중계
자율수준: Level 3
```

### Decomposition

| Subtask | Suitable Asset |
|---|---|
| air_recon | UAV |
| ground_check | UGV |
| maritime_watch | USV |
| relay | Relay UAV |

The parser can initially be simple rule-based logic.  
Do not use LLM-based parsing in MVP unless it is already easy to add.

---

## 12. Condition-Aware Task Allocation

Each asset has different condition values.

Example:

| Asset | Condition |
|---|---|
| UAV-1 | battery 82%, fast, good comm |
| UAV-2 | battery 65%, relay capable, available |
| UGV-1 | battery 74%, ground mobility, slow |
| USV-1 | battery 88%, maritime watch capable |

### Mission Fit Score

Before scoring, apply hard feasibility filters:

```text
Reject asset or route if:
- device_state is disabled
- assignment is impossible
- required domain does not match asset type
- UGV route leaves land edges
- USV route leaves sea edges
- UAV direct or waypoint segment crosses a risk zone
- any graph edge crosses a risk zone
```

Use this conceptual equation:

```text
Mission Fit Score =
Distance Score
+ Battery Margin
+ Communication Quality
+ Availability Score
+ Domain Match
- Device State Penalty
- Intervention Burden Penalty
```

### Intervention Burden Penalty

```text
Intervention Burden Penalty =
Expected Approval Count
+ Expected Alert Count
+ Manual Monitoring Need
+ Role Conflict Probability
```

The important idea:

> Even if an asset is technically best, it should be penalized if assigning it causes too many alerts, approvals, or manual monitoring needs.

---

## 13. Route Modes

Each candidate asset should generate or simulate three route options.

| Route | Meaning |
|---|---|
| Fast Route | Shortest or fastest path |
| Safe Route | Maximizes margin from risk zones and unstable areas |
| Quiet Route | Minimizes alerts, approvals, and replanning burden |

### Example Route Comparison

| Route | ETA | Alerts | Approvals | Comm Risk | Recommendation |
|---|---:|---:|---:|---:|---|
| Fast Route | 4m 20s | 5 | 2 | high | Not recommended |
| Safe Route | 5m 40s | 2 | 1 | low | Secondary |
| Quiet Route | 5m 10s | 1 | 0 | low | Recommended |

### Explanation Text

```text
Quiet Route는 Fast Route보다 50초 느리지만,
예상 알림 4개와 승인 요청 2회를 줄일 수 있습니다.
임무 제한시간 내 도착 가능하므로 Quiet Route를 추천합니다.
```

---

## 14. AMMP Cost Function

### High-Level Equation

```text
AMMP Cost =
Mission Cost
+ Vehicle Risk Cost
+ Intervention Burden Cost
```

### Detailed Equation

```text
AMMP Cost =
Distance Cost
+ Communication Cost
+ Battery Cost
+ Device State Cost
+ Replanning Cost
+ Alert Cost
+ Approval Cost
```

Risk-zone crossing is handled before this equation as a feasibility filter.  
Routes that enter or cross risk zones must not reach the cost function.

### Route Cost

For the dedicated ROS2 cost-planning node, compute route-only cost first.

```text
RouteCost =
w_distance * route_distance_km
+ w_eta * eta_min
+ w_deadline * deadline_delay_min
```

`route_distance_m` is asset-specific.  
It is measured from each candidate asset's current position to the selected target, not from a user-selected start node.

```text
UGV / USV route_distance_m =
distance(asset.position, snapped_asset_node)
+ sum(edge.distance_m for graph path from snapped_asset_node to target_node)

UAV route_distance_m =
direct or waypoint distance from asset.position to target position
```

Risk-zone violation is not included here because it is infeasible.  
Before calculating `RouteCost`, remove any UGV/USV edge or UAV segment that intersects a risk-zone polygon.

Movement model:

```text
UGV:
- Use only land edges.
- Compute the path over land-domain nodes.

USV:
- Use only sea edges.
- Compute the path over water-domain nodes.

UAV:
- Use direct asset-position-to-target segment if it does not cross risk zones.
- If direct flight crosses a risk zone, generate waypoint candidates around the risk-zone boundary.
```

ETA:

```text
eta_sec = route_distance_m / asset.speed_mps
eta_min = eta_sec / 60
```

### Implementation Form

```python
def compute_ammp_cost(route, alerts, approvals):
    W_DISTANCE = 1.0
    W_COMM = 20
    W_BATTERY = 40
    W_DEVICE_STATE = 25
    W_REPLAN = 12
    W_ALERT = 10
    W_APPROVAL = 30

    return (
        route.distance * W_DISTANCE
        + route.comm_shadow_cells * W_COMM
        + route.battery_warning * W_BATTERY
        + route.device_state_penalty * W_DEVICE_STATE
        + route.replanning_events * W_REPLAN
        + len(alerts) * W_ALERT
        + len(approvals) * W_APPROVAL
    )
```

### Device State Cost

Use these device condition states:

| Device State | Meaning | Suggested Penalty | Planner Behavior |
|---|---|---:|---|
| good | 정상, 즉시 임무 가능 | 0 | Normal candidate |
| caution | 저위험군, 주의 필요 | 1 | Candidate with mild penalty |
| critical | 고위험군, 실패 가능성 높음 | 3 | Candidate only when no better option exists |
| disabled | 전원 꺼짐 또는 통신/동작 불가 | infeasible | Exclude from candidates |

The `device_state` value is separate from `mission_status`.  
For example, an asset can be `device_state: "good"` and `mission_status: "assigned"`.

## 15. Alert Prediction

### Expected Alert Types

Expected alerts are system-predicted notifications that may appear if a route is selected.  
The operator does not input these values manually.  
The planner estimates them from route geometry, ETA, battery margin, communication quality, and asset mission status.

| Condition | Alert |
|---|---|
| comm_quality expected below 0.5 | Communication degradation alert |
| expected battery below 30% | Return-to-base or battery warning |
| near risk zone boundary | Risk-zone proximity alert |
| obstacle-induced detour | Replanning alert |
| deadline violation | Mission delay alert |
| reassigning an already assigned asset | Role conflict alert |

### Alert Cost

```text
Alert Cost =
comm_alerts × 8
+ battery_alerts × 10
+ replanning_alerts × 12
+ delay_alerts × 6
```

### Approval Cost

Expected approvals are system-predicted human-in-the-loop decisions that may be required if a plan is selected.  
They are not the operator's current subjective input.  
They are estimated from mission rules and route/asset conditions.

```text
Approval Cost =
mission_abort_approvals × 25
+ civilian_sensitive_approvals × 35
+ asset_loss_risk_approvals × 40
+ relay_reassignment_approvals × 30
```

Approval is more expensive than normal alert because it requires responsible human judgment.

---

## 16. Human-in-the-Loop Policy

The system must not claim full autonomy for all decisions.  
It should clearly distinguish automatic decisions from human approval decisions.

### Auto-Handled

| Situation | Behavior |
|---|---|
| Normal recon route planning | Automatic |
| Low-risk route replanning | Automatic |
| Battery below pre-approved threshold | Automatic return if pre-approved |
| Short communication degradation | Continue automatically |
| Normal mission completion | Auto report |

### Requires Human Approval

| Situation | Reason |
|---|---|
| Risk zone entry | Not allowed in MVP; reroute or return no feasible route |
| Civilian-sensitive zone approach | Collateral risk |
| Mission abort | Operational impact |
| Unknown target tracking | Misidentification risk |
| Reassigning relay asset | May affect entire mission network |

---

## 17. Decision Packet

### Purpose

Do not display every alert as a separate notification.  
Group related alerts into a single operator decision.

### Bad Alert Display

```text
UAV-1 배터리 18%
A구역 정찰 60% 완료
UAV-2가 대체 가능
UAV-2는 통신중계 중
통신품질 12% 저하 예상
```

### AMMP Decision Packet

```text
Decision Packet #03

결정 필요: A구역 정찰 임무 인계

상황:
UAV-1 배터리가 18%로 하락했습니다.
A구역 정찰은 60% 완료되었습니다.
UAV-2가 정찰 임무를 인계할 수 있습니다.
단, UAV-2가 통신중계를 이탈하면 통신품질이 12% 저하될 수 있습니다.

추천:
UAV-1 복귀 + UAV-2 정찰 인계

선택지:
[추천안 승인]
[통신중계 유지]
[정찰 임무 보류]
```

### Key UI Principle

> Convert many alerts into one decision.

This is one of the clearest visual demonstrations of alert reduction and human-in-the-loop control.

---

## 18. Web UI Specification

### Layout

```text
┌───────────────────────────────┬────────────────────────────┐
│                               │ Mission Intent Panel        │
│         2D Mission Map         ├────────────────────────────┤
│                               │ Asset Condition Panel       │
│ UAV / UGV / USV               ├────────────────────────────┤
│ Risk / Comm / Water Zones      │ Alert Summary Panel         │
│ Routes                        ├────────────────────────────┤
│                               │ Decision Packet Panel       │
└───────────────────────────────┴────────────────────────────┘
│ Route Comparison / Metrics Summary                           │
└───────────────────────────────────────────────────────────────┘
```

### Components

| Component | Purpose |
|---|---|
| MapCanvas | 2D mission map |
| MissionIntentPanel | Operator mission input |
| AssetConditionPanel | Edit UAV/UGV/USV condition |
| RouteComparisonPanel | Fast/Safe/Quiet comparison |
| AlertSummaryPanel | Display predicted and active alerts |
| DecisionPacketPanel | Human approval cards |
| MetricsPanel | Mission success and manpower metrics |

### Map Visuals

| Element | Visual Suggestion |
|---|---|
| UAV | Triangle |
| UGV | Circle |
| USV | Square |
| Risk Zone | Red grid |
| Comm Shadow | Purple grid |
| Water Zone | Blue grid |
| Civilian Sensitive Zone | Orange grid |
| Fast Route | Dotted line |
| Safe Route | Thin solid line |
| Quiet Route | Thick solid line |

Do not overfocus on visual perfection.  
The logic and explainability matter more than decorative visuals.

---

## 19. Route Comparison Panel

Example:

```text
Route Comparison for UAV-1

Fast Route
ETA 4:20
Alerts 5
Approvals 2

Safe Route
ETA 5:40
Alerts 2
Approvals 1

Quiet Route
ETA 5:10
Alerts 1
Approvals 0

Recommended: Quiet Route
Reason: It has the lowest predicted alerts and approvals while still meeting the deadline.
```

The panel must show:

- ETA
- Alerts
- Approvals
- Total AMMP Cost
- Recommended route
- Reason

---

## 20. ROS2 Humble Architecture

If ROS2 is implemented, use these nodes.

| Node | Role |
|---|---|
| scenario_manager_node | Map, scenario, environment |
| asset_state_node | Publishes UAV/UGV/USV states |
| px4_to_missiondeck_adapter | Converts PX4 `/fmu/out/*` telemetry into `/missiondeck/uxv_states` |
| mission_intent_node | Converts mission intent into subtasks |
| task_allocator_node | Assigns assets based on condition |
| ammp_planner_node | Runs AMMP planning |
| alert_predictor_node | Predicts alerts and approvals |
| decision_packet_node | Groups alerts into decisions |
| metrics_node | Computes success, reduction, response metrics |
| web_bridge_node | Connects ROS2 to web UI |

### Suggested Topics

| Topic | Content |
|---|---|
| `/uxv_states` | Asset states |
| `/mission_intent` | Operator mission intent |
| `/task_assignment` | Asset assignment result |
| `/route_candidates` | Fast/Safe/Quiet routes |
| `/selected_route` | Chosen route |
| `/operator_alerts` | Raw or prioritized alerts |
| `/decision_packets` | HITL approval cards |
| `/mission_metrics` | Mission results |

### Cost Planner Topics

For ROS2 Humble MVP, the route/cost planner can use JSON payloads over `std_msgs/msg/String`.  
Later, these can be replaced with custom messages or a planning action.

Input topics:

| Topic | Type | Content |
|---|---|---|
| `/missiondeck/map/graph_geojson` | `std_msgs/msg/String` | GeoJSON nodes and edges |
| `/missiondeck/map/waypoint_nodes` | `std_msgs/msg/String` | Destination and detour waypoint nodes for UGV/USV/UAV |
| `/missiondeck/map/risk_zones_geojson` | `std_msgs/msg/String` | GeoJSON forbidden risk-zone polygons |
| `/missiondeck/uxv_states` | `std_msgs/msg/String` | Current UGV/UAV/USV condition states |
| `/missiondeck/planner/request` | `std_msgs/msg/String` | Target node and selected asset category |

Planner request example:

```json
{
  "request_id": "REQ-001",
  "target_node_id": "BUSAN",
  "selected_category": "UGV"
}
```

The request contains only the target and selected asset category.  
The planner derives each candidate route from the candidate asset's current `position`.  
For UGV and USV graph planning, the asset position is snapped to the nearest domain-compatible graph node before route search.

UxV device-state example:

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
      "assignment_possible": true,
      "position": { "lat": 37.5665, "lon": 126.9780 }
    }
  ]
}
```

### PX4 MissionDeck Adapter

The PX4 adapter lives at:

```text
src/CoreCenter/ros/px4_to_missiondeck_adapter.py
```

Its job is to adapt PX4 simulator or PX4 vehicle telemetry into the AMMP planner input topic:

```text
PX4 /fmu/out/*
        -> px4_to_missiondeck_adapter
        -> /missiondeck/uxv_states
        -> ammp_planner_node
```

The adapter subscribes to:

| PX4 topic | Purpose |
|---|---|
| `/fmu/out/vehicle_global_position` | Asset latitude and longitude |
| `/fmu/out/battery_status` | Battery remaining ratio converted to `0..100` percent |
| `/fmu/out/vehicle_odometry` | Velocity vector converted to `speed_mps` |
| `/fmu/out/vehicle_status` | PX4 nav/failsafe state used for AMMP status mapping |

The adapter publishes:

| Topic | Type | Content |
|---|---|---|
| `/missiondeck/uxv_states` | `std_msgs/msg/String` | AMMP asset-state JSON |

Adapter output example:

```json
{
  "assets": [
    {
      "id": "PX4_GJ_01",
      "type": "UAV",
      "battery": 87.2,
      "comm_quality": 1.0,
      "device_state": "good",
      "mission_status": "available",
      "speed_mps": 3.4,
      "assignment_possible": true,
      "position": {
        "lat": 35.1595,
        "lon": 126.8526
      },
      "current_mission": null
    }
  ]
}
```

Recommended run command:

```bash
source /opt/ros/humble/setup.bash
source ~/px4_ros2_ws/install/setup.bash
python3 /home/hannibal/d4d_ws/src/CoreCenter/ros/px4_to_missiondeck_adapter.py
```

Recommended verification:

```bash
ros2 topic echo /missiondeck/uxv_states
```

Adapter parameter defaults:

| Parameter | Default | Meaning |
|---|---:|---|
| `asset_id` | `PX4_GJ_01` | AMMP asset ID |
| `asset_type` | `UAV` | AMMP asset type |
| `default_battery_pct` | `100.0` | Used before battery telemetry arrives |
| `default_comm_quality` | `1.0` | Base communication quality while telemetry is fresh |
| `current_mission` | empty string | Empty maps to JSON `null`; non-empty maps to `assigned` |
| `link_timeout_sec` | `3.0` | Position freshness timeout |
| `battery_caution_pct` | `30.0` | Battery threshold for `caution` |
| `battery_critical_pct` | `15.0` | Battery threshold for `critical` |
| `publish_hz` | `5.0` | Output publish rate |

Status mapping rules:

| AMMP field | Adapter logic |
|---|---|
| `battery` | `BatteryStatus.remaining * 100`, clamped to `0..100` |
| `comm_quality` | Uses fresh position telemetry as a link freshness proxy; decays after timeout |
| `speed_mps` | Euclidean magnitude of `VehicleOdometry.velocity` |
| `device_state` | `critical` for stale position, failsafe, critical battery, or very low comm; `caution` for incomplete telemetry, low battery, or degraded comm; otherwise `good` |
| `mission_status` | PX4 RTL/land states map to `returning`; configured `current_mission` or PX4 auto mission-like states map to `assigned`; otherwise `available` |
| `assignment_possible` | `true` only when state is not critical/disabled, mission is not assigned/returning, and position telemetry is fresh |

### CoreCenter Bridge and AMMP Connection Analysis

`src/CoreCenter/ros/px4_to_c2_bridge.py` and `src/CoreCenter/ros/px4_to_missiondeck_adapter.py` should be treated as sibling adapters that share the same PX4 telemetry source, not as a required chain.

Recommended topology:

```text
                 -> px4_to_c2_bridge -> /c2/fleet/state -> CoreCenter UI
PX4 /fmu/out/*
                 -> px4_to_missiondeck_adapter -> /missiondeck/uxv_states -> AMMP planner
```

This connection is compatible because both adapters read the same PX4 source topics and derive the overlapping fields needed by their consumers:

| PX4-derived value | CoreCenter `/c2/fleet/state` | AMMP `/missiondeck/uxv_states` |
|---|---|---|
| Asset ID | `vehicle_id` | `id` |
| Asset type | `vehicle_type` | `type` |
| Battery percent | `battery_pct` | `battery` |
| Link quality | `link_quality` | `comm_quality` |
| Speed | `speed_mps` | `speed_mps` |
| Position | `lat`, `lon` | `position.lat`, `position.lon` |
| Assignability | `assignable` | `assignment_possible` |
| Mission state | `mission_state` | `mission_status` |
| Mission label | `current_mission` | `current_mission` |

However, `/c2/fleet/state` is not an AMMP-compatible input by itself. It is a CoreCenter UI schema with fields such as `vehicle_id`, `vehicle_type`, `battery_pct`, `link_quality`, `lat`, and `lon`. The AMMP planner expects `id`, `type`, `battery`, `comm_quality`, and nested `position`. Therefore AMMP should subscribe to `/missiondeck/uxv_states`, not `/c2/fleet/state`.

The current bridge remains useful for the UI, but it has values that are intentionally UI-oriented or simplified:

```text
link_quality = 1.0
assignable = true
mission_state = PX4_ACTIVE or PX4_LINK_WAIT
current_mission = "PX4 SITL at Gwangju"
```

Those values should not be passed directly into AMMP without mapping. The MissionDeck adapter performs that mapping and emits the planner-safe schema.

Integration verdict:

```text
PX4 telemetry -> CoreCenter UI: connected through px4_to_c2_bridge.py.
PX4 telemetry -> AMMP planner: connected through px4_to_missiondeck_adapter.py.
CoreCenter UI -> AMMP planner: not connected by this adapter; use planner request/output topics or a separate web/mission node.
```

For a full AMMP run, the adapter only satisfies the live UAV state input. The remaining required planner inputs must still be published by MissionDeck nodes:

| Required topic | Source |
|---|---|
| `/missiondeck/map/graph_geojson` | scenario/map node |
| `/missiondeck/map/risk_zones_geojson` | scenario/map node |
| `/missiondeck/planner/request` | UI/backend mission request node |
| `/missiondeck/uxv_states` | PX4 adapter for PX4 UAV plus other asset-state publishers/adapters |

If multiple independent adapters publish `/missiondeck/uxv_states`, add an asset-state aggregator node so the planner receives one coherent `{"assets": [...]}` snapshot instead of competing partial snapshots.

Output topics:

| Topic | Type | Content |
|---|---|---|
| `/missiondeck/planner/route_candidates` | `std_msgs/msg/String` | Feasible and rejected asset-route candidates |
| `/missiondeck/planner/selected_route` | `std_msgs/msg/String` | Recommended asset and path |
| `/missiondeck/planner/no_feasible_route` | `std_msgs/msg/String` | Published when all candidates are infeasible |

Route candidate example:

```json
{
  "request_id": "REQ-001",
  "candidates": [
    {
      "asset_id": "UGV-1",
      "asset_position": { "lat": 37.5665, "lon": 126.9780 },
      "snapped_asset_node_id": "SEOUL",
      "target_node_id": "BUSAN",
      "route_node_ids": ["SEOUL", "DAEJEON", "DAEGU", "BUSAN"],
      "distance_m": 390000,
      "eta_sec": 32500,
      "route_cost": 932.0,
      "condition_penalty": 25.0,
      "total_cost": 957.0,
      "feasible": true
    },
    {
      "asset_id": "UGV-2",
      "route_node_ids": [],
      "feasible": false,
      "reason": "device_state is disabled"
    }
  ]
}
```

In this example, `SEOUL` is not user input.  
It is the nearest graph node to `UGV-1`'s current position.

The cost planner must apply feasibility checks before scoring:

```text
Reject asset if:
- asset.type does not match selected_category
- assignment_possible is false
- device_state is disabled
- speed_mps <= 0
- battery is insufficient for the planned route

Reject route if:
- UGV route uses non-land edges
- USV route uses non-sea edges
- UAV segment crosses a risk-zone polygon
- any edge intersects a risk-zone polygon
```

---

## 21. AMMP Planner Input and Output

### Input

```json
{
  "mission": {
    "type": "complex_recon",
    "target_node_id": "BUSAN",
    "target": { "lat": 35.1796, "lon": 129.0756 },
    "priority": "high",
    "required_actions": ["air_recon", "ground_check", "maritime_watch", "relay"],
    "deadline_sec": 480
  },
  "assets": [
    {
      "id": "UAV-1",
      "type": "UAV",
      "battery": 82,
      "speed_mps": 18,
      "comm_quality": 0.91,
      "device_state": "good",
      "mission_status": "available",
      "assignment_possible": true,
      "position": { "lat": 37.5665, "lon": 126.9780 }
    }
  ]
}
```

### Output

```json
{
  "assignments": [
    {
      "mission": "air_recon",
      "asset": "UAV-1",
      "route": "quiet",
      "reason": [
        "임무 제한시간 내 도착 가능",
        "Fast Route 대비 알림 4개 감소",
        "승인 요청 2회 감소"
      ]
    }
  ],
  "decision_packets": []
}
```

---

## 22. Backend API Specification

### GET `/api/assets`

Return all assets.

### PATCH `/api/assets/{asset_id}`

Update asset condition.

Request:

```json
{
  "battery": 45,
  "comm_quality": 0.62,
  "device_state": "caution"
}
```

### POST `/api/missions`

Create mission.

Request:

```json
{
  "type": "complex_recon",
  "target_node_id": "BUSAN",
  "target": { "lat": 35.1796, "lon": 129.0756 },
  "priority": "high",
  "required_actions": ["air_recon", "ground_check", "maritime_watch", "relay"],
  "autonomy_level": 3
}
```

### POST `/api/plan`

Run task allocation and AMMP route planning.

Response:

```json
{
  "mission_id": "M-001",
  "assignments": [
    {
      "subtask": "air_recon",
      "asset_id": "UAV-1",
      "recommended_route": "quiet"
    }
  ],
  "routes": [
    {
      "id": "fast",
      "eta_sec": 260,
      "distance": 420,
      "expected_alerts": 5,
      "expected_approvals": 2,
      "total_cost": 540
    },
    {
      "id": "quiet",
      "eta_sec": 310,
      "distance": 510,
      "expected_alerts": 1,
      "expected_approvals": 0,
      "total_cost": 430
    }
  ],
  "recommended_route": "quiet",
  "reason": [
    "Quiet Route는 Fast Route보다 50초 늦지만 예상 알림 4개와 승인 요청 2회를 줄입니다.",
    "임무 제한시간 480초 이내 도착 가능합니다."
  ]
}
```

### POST `/api/events/{event_type}`

Trigger simulated event.

Allowed event types:

- `battery_drop`
- `comm_degradation`
- `new_risk_zone`
- `asset_disabled`
- `unknown_contact_detected`

### POST `/api/approvals/{packet_id}`

Submit decision packet choice.

Request:

```json
{
  "choice": "approve_recommended"
}
```

---

## 23. Core Algorithm Pseudocode

### Full Planning Flow

```python
def plan_mission(mission, assets, map_data):
    subtasks = decompose_mission(mission)

    assignments = []

    for subtask in subtasks:
        candidate_assets = filter_assets_by_domain_and_state(subtask, assets)

        scored_assets = []
        for asset in candidate_assets:
            fit_score = compute_mission_fit(asset, subtask)
            scored_assets.append((asset, fit_score))

        selected_asset = max(scored_assets, key=lambda x: x[1])[0]

        routes = generate_route_candidates(selected_asset, subtask, map_data)

        scored_routes = []
        for route in routes:
            alerts = predict_alerts(route, selected_asset, subtask)
            approvals = predict_approvals(route, selected_asset, subtask)

            cost = compute_ammp_cost(
                route=route,
                alerts=alerts,
                approvals=approvals
            )

            scored_routes.append((route, cost, alerts, approvals))

        selected_route, selected_cost, selected_alerts, selected_approvals = min(
            scored_routes,
            key=lambda x: x[1]
        )

        decision_packet = build_decision_packet_if_needed(
            subtask=subtask,
            asset=selected_asset,
            route=selected_route,
            alerts=selected_alerts,
            approvals=selected_approvals
        )

        assignments.append({
            "subtask": subtask,
            "asset": selected_asset,
            "route": selected_route,
            "cost": selected_cost,
            "alerts": selected_alerts,
            "approvals": selected_approvals,
            "decision_packet": decision_packet
        })

    return assignments
```

## 24. Demo Scenario

### Scenario Name

**해안·도심 복합지역 미상 이동체 확인 임무**

### Initial Assets

| Asset | State |
|---|---|
| UAV-1 | battery 82%, fast, recon suitable |
| UAV-2 | battery 65%, relay capable |
| UGV-1 | battery 74%, ground check capable |
| USV-1 | battery 88%, maritime watch capable |

### Map Zones

| Zone | Meaning |
|---|---|
| A Area | Suspected unknown contact area |
| Risk Zone | Dangerous zone |
| Comm Shadow | Communication shadow |
| Water Zone | USV navigable area |
| Urban Zone | UGV navigable area |
| Civilian Sensitive Zone | Civilian-sensitive area |

### Step 1: Mission Intent

```text
임무유형: 복합 정찰
목표지역: A구역
우선순위: 높음
작전환경: 해안 + 도심
필요행동:
- 상공 정찰
- 지상 확인
- 해안 감시
- 통신 중계
자율수준: Level 3
```

### Step 2: Mission Decomposition

| Subtask | Recommended Asset |
|---|---|
| air_recon | UAV-1 |
| relay | UAV-2 |
| ground_check | UGV-1 |
| maritime_watch | USV-1 |

### Step 3: AMMP Route Candidates for UAV-1

| Route | ETA | Alerts | Approvals |
|---|---:|---:|---:|
| Fast | 4:20 | 5 | 2 |
| Safe | 5:40 | 2 | 1 |
| Quiet | 5:10 | 1 | 0 |

Recommendation:

```text
Quiet Route
Reason: Fast Route보다 느리지만 예상 알림과 승인 요청이 가장 적고 제한시간 내 도착 가능합니다.
```

### Step 4: Simulated Event

Button click:

```text
UAV-1 battery drop
```

System event state:

```text
UAV-1 battery 18%
A Area recon 60% complete
UAV-2 can take over recon
But UAV-2 is currently acting as relay
```

Generate Decision Packet:

```text
결정 필요: A구역 정찰 인계

추천:
UAV-1 복귀
UAV-2 정찰 인계
UGV-1 지상 확인 유지
USV-1 해안 감시 유지

예상 영향:
임무 성공률 84%
통신품질 12% 저하
추가 승인 1회
```

### Step 5: Mission Report

```text
Mission Summary

운용자 수: 1명
운용 UxV: 4대
완료 임무: 3/4
자동 임무배정: 4건
자동 재계획: 1건
Decision Packet: 2건
Fast Route 대비 예상 알림 감소: 6개
Fast Route 대비 승인 요청 감소: 3회
예상 인력 절감률: 75%
```

---

## 25. Metrics

### Required Metrics

| Metric | Meaning |
|---|---|
| Mission Success Rate | completed subtasks / total subtasks |
| Operator Interventions | approvals, manual reassignments, manual route changes |
| Expected Alerts Reduced | alert reduction compared to Fast Route baseline |
| Approvals Reduced | approval reduction compared to Fast Route baseline |
| Response Time | time from event to decision |
| Manpower Reduction Rate | reduction compared with one-operator-per-vehicle baseline |

### Manpower Reduction

```text
Baseline:
4 UxVs = 4 operators

MissionDeck AMMP:
4 UxVs = 1 operator

Manpower Reduction Rate = (4 - 1) / 4 * 100 = 75%
```

---

## 26. Host Requirement Presentation Points

### Mission-Level Abstraction

> 운용자는 UAV, UGV, USV를 각각 조종하지 않고 “A구역 복합 정찰”이라는 임무 의도를 입력합니다. 시스템은 이를 상공 정찰, 지상 확인, 해안 감시, 통신 중계로 자동 분해합니다.

### Autonomous Role Allocation

> 각 기체의 배터리, 위치, 통신상태, 현재 임무를 비교해 적합한 역할을 자동으로 배정합니다.

### Alert Prioritization

> 예상 알림과 승인 요청을 계산하고, 관련 알림은 Decision Packet 형태로 묶어 핵심 판단만 제공합니다.

### Human-in-the-Loop

> 낮은 위험의 반복 판단은 자동 처리하고, 위험구역 진입·임무 포기·통신중계 자산 전환처럼 책임 판단이 필요한 경우에만 승인 요청합니다.

### Measurement Framework

> Fast Route 대비 알림 감소 수, 승인 요청 감소 수, 임무 성공률, 대응시간, 인력 절감률을 측정합니다.

---

## 27. Implementation Priorities

### Phase 1: Pure Web + Backend MVP

1. Create static 2D grid map.
2. Render UAV, UGV, USV.
3. Add asset condition editor.
4. Add mission intent input.
5. Implement mission decomposition.
6. Implement simple condition-based task allocation.
7. Generate three route candidates: Fast, Safe, Quiet.
8. Compute alerts, approvals, and AMMP cost.
9. Display route comparison.
10. Generate Decision Packet for battery drop or risk-zone case.
11. Display final metrics.

### Phase 2: ROS2 Humble Integration

1. Create ROS2 package `missiondeck_ros`.
2. Implement `asset_state_node`.
3. Implement `mission_intent_node`.
4. Implement `task_allocator_node`.
5. Implement `ammp_planner_node`.
6. Publish results to topics.
7. Connect web UI via FastAPI bridge or rosbridge.

### Phase 3: Demo Polish

1. Add animated movement.
2. Add event buttons.
3. Add route colors.
4. Add Korean presentation labels.
5. Add explainability text.
6. Add final mission report card.
7. Add screenshot-friendly UI layout.

---

## 28. Acceptance Criteria

The MVP is complete when all of the following are true:

- The web UI shows a 2D map.
- UAV, UGV, USV are visible.
- At least 3 heterogeneous UxVs are controllable, preferably 4 assets.
- The operator can edit battery, communication quality, and device_state.
- The operator can create a complex recon mission.
- The system decomposes complex recon into air recon, ground check, maritime watch, and relay.
- The system assigns suitable assets automatically.
- The system generates Fast, Safe, and Quiet routes.
- The system computes expected alerts and approvals for each route.
- A battery drop event generates a Decision Packet.
- The UI shows why a route was recommended.
- The final report shows alert reduction, approval reduction, mission success rate, and manpower reduction.

---

## 29. Development Rules for Codex

When modifying this project:

1. Preserve the core concept of AMMP.
2. Do not reduce AMMP to simple shortest-path planning.
3. Always include alert, approval, and intervention burden in scoring.
4. Prefer explainable rule-based logic over black-box ML for MVP.
5. Keep the UI simple but decision-focused.
6. Avoid military weaponization features. This is a command-and-control simulator for mission allocation, monitoring, and unnecessary intervention reduction.
7. Human-in-the-loop must remain visible.
8. Do not hide why the system made a recommendation.
9. Keep Korean labels available for demo.
10. Make the system robust enough for a short live demo.

---

## 30. Final Concept Text

Use this in README, presentation, or project intro:

```text
AMMP, Alert-Minimizing Mission Planning은 단일 운용자가 UAV·UGV·USV를 동시에 운용할 때 발생하는 알림 과잉과 승인 부담을 줄이기 위한 임무계획 방식이다. 시스템은 임무 성공률만 최적화하지 않고, 예상 알림 수, 승인 요청 수, 재계획 가능성을 함께 계산해 운용자가 적게 개입해도 유지 가능한 임무배정과 경로를 추천한다.
```

Final soul of the project:

> **AMMP는 가장 빠른 계획이 아니라, 한 명의 운용자가 가장 적게 개입해도 임무가 무너지지 않는 계획을 찾는다.**
