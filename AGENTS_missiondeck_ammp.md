# AGENTS.md

# MissionDeck AMMP: Alert-Minimizing Mission Planning

## 0. Purpose of This File

This file acts as the primary development guide for Codex or any AI coding agent working on the MissionDeck AMMP project.

The project is designed for the D4D Seoul T1 challenge:

> **1인 다중 무인기 동시 통제 / Multi-UxV Control**

The goal is to develop a 2D web-based simulator and mission control interface where a single operator can assign, monitor, and supervise 3 or more heterogeneous unmanned systems across air, ground, and maritime domains.

The core technical concept is:

> **Alert-Minimizing Mission Planning, AMMP**

AMMP is a mission planning method that considers not only distance, speed, risk, and vehicle condition, but also expected alerts, approval requests, replanning likelihood, and operator cognitive load increase. The system recommends a plan that allows the operator to maintain or improve mission success while intervening as little as possible.

---

## 1. Challenge Guideline Summary

The hackathon prompt states:

> 최근 전장에서 드론을 비롯한 UGV, USV 등 다양한 무인 시스템의 운용 비중이 급증하고 있습니다. 그러나 현행 운용 방식은 장비 증가에 비례해 운용 인력 또한 동반 요구되는 선형적 구조 한계를 지니고 있습니다. 이는 인구 절벽 및 병력 감소 직면국, 한국 및 APAC의 장기 전력 운용 측면에서 지속 불가능합니다. 따라서 미래 전장은 단일 운용자가 다수의 무인체계를 통합 감독·제어하는 유무인 복합 체계로의 전환이 필수적입니다.

Required system:

> 단일 운용자가 공중·지상·해상의 이종 UxV 무인체계 3대 이상을 동시에 임무 부여, 감시, 통제할 수 있는 체계를 개발하라.  
> 운용자 인지부하, Cognitive Load를 최소화하면서도 임무 성공률을 유지하거나 향상시킬 수 있는 방안을 제시할 것.

Required components:

- 임무 단위 추상화, 개별 조종 → 임무 의도 입력 인터페이스
- 다수 무인기의 자율 임무 분산·역할 할당
- 운용자 인지부하 모니터링 및 우선순위 알림
- 이상·위협 발생 시 사람 개입 지점, human-in-the-loop 설계
- 인력 절감률·임무 성공률 측정 프레임워크

---

## 2. Core Interpretation

The most important interpretation of the challenge is:

> The real-world problem is not simply controlling drones.  
> The real problem is that as UAV, UGV, and USV assets increase, operator workload, alerts, approvals, and decision burden increase linearly or worse.

MissionDeck AMMP should demonstrate that one operator can supervise multiple heterogeneous UxVs by shifting from vehicle-level control to mission-level intent.

### Requirement Mapping

| Host Requirement | AMMP Response |
|---|---|
| Mission-level abstraction | Operator enters "A구역 복합 정찰" instead of "move UAV-1" |
| Autonomous mission distribution | System assigns UAV, UGV, USV based on condition |
| Cognitive load monitoring | Cognitive Load Score and Attention Budget |
| Priority alerts | Low-priority alerts are suppressed or grouped |
| Human-in-the-loop | Risk zone entry, mission abort, relay reassignment require approval |
| Measurement framework | Mission success rate, alert reduction, approval reduction, response time, manpower reduction |

### Key Novelty

> Cognitive load reduction is not treated only as a UI problem.  
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
센서가 맞는 기체를 고른다.
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

This route is efficient for the vehicle, but noisy and cognitively expensive for the operator.

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
   - Sensors
   - Communication quality
   - Current mission
   - Health
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

6. System estimates alert, approval, replanning, and cognitive burden for each route.

7. System recommends the final plan based on Cognitive Load Score.

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
- Cognitive Load Score
- Alert prediction
- Approval prediction
- Decision Packet generation
- Human-in-the-loop approval UI
- Mission metrics and final report

### Nice to Have

- ROS2 Humble nodes
- WebSocket real-time updates
- Attention Peak Smoothing
- Natural language mission input
- ROSBridge support
- Gazebo or Webots integration

### Not Required for MVP

- Real drone control
- Full physics simulation
- Full ROS2 Nav2 integration
- Reinforcement learning
- Real sensor input
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
│   │   ├── cognitive_load.py
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
│       │   ├── CognitiveLoadPanel.tsx
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
                ├── cognitive_load_node.py
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
  "position": { "x": 4, "y": 4 },
  "battery": 82,
  "speed": 4,
  "sensors": ["EO", "IR"],
  "comm_quality": 0.91,
  "health": "normal",
  "status": "available",
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
| position | x, y | 2D grid position |
| battery | number | 0 to 100 |
| speed | number | cells per tick or relative speed |
| sensors | array | EO, IR, RF, LiDAR |
| comm_quality | number | 0.0 to 1.0 |
| health | normal / degraded / fail | Asset health |
| status | available / assigned / returning / disabled | Current state |
| risk_tolerance | low / medium / high | Risk acceptance |
| autonomy_level | 1 to 5 | Human approval level |
| current_mission | string or null | Assigned mission |

### 9.2 Default Assets

| Asset | Type | Role |
|---|---|---|
| UAV-1 | UAV | Air recon, EO/IR |
| UAV-2 | UAV | Relay, auxiliary recon |
| UGV-1 | UGV | Ground check, LiDAR |
| USV-1 | USV | Maritime watch, RF/EO |

### 9.3 Mission

```json
{
  "id": "M-001",
  "type": "complex_recon",
  "target": { "x": 30, "y": 12 },
  "priority": "high",
  "required_actions": ["air_recon", "ground_check", "maritime_watch", "relay"],
  "required_sensors": ["EO"],
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

### 9.4 Operator State

```json
{
  "cognitive_load_score": 24,
  "active_missions": 4,
  "critical_alerts": 1,
  "pending_approvals": 2,
  "comm_degraded_assets": 1,
  "failed_assets": 0,
  "high_risk_routes": 1
}
```

### 9.5 Route Candidate

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
  "cognitive_load_delta": 2,
  "total_cost": 430
}
```

### 9.6 Decision Packet

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
| risk_zone | Dangerous area | 50 |
| comm_shadow | Communication shadow | 20 |
| civilian_sensitive | Civilian-sensitive zone | 40 |
| obstacle | Obstacle | blocked |
| water | Maritime area | USV only |
| land | Ground area | UGV possible |
| air_corridor | Air route | UAV possible |

### Movement Rules

| Asset Type | Movement Rule |
|---|---|
| UAV | Can move over most cells except hard no-fly obstacles if configured |
| UGV | Can move on land/normal cells, cannot move on water |
| USV | Can move on water cells, cannot move on land |
| Relay UAV | Similar to UAV, but route selection prioritizes stable communication coverage |

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
| UAV-1 | battery 82%, EO/IR, fast, good comm |
| UAV-2 | battery 65%, relay capable, available |
| UGV-1 | battery 74%, LiDAR, ground mobility, slow |
| USV-1 | battery 88%, RF/EO, maritime watch capable |

### Mission Fit Score

Use this conceptual equation:

```text
Mission Fit Score =
Sensor Match
+ Distance Score
+ Battery Margin
+ Communication Quality
+ Availability Score
+ Domain Match
- Risk Exposure Penalty
- Health Penalty
- Operator Burden Penalty
```

### Operator Burden Penalty

```text
Operator Burden Penalty =
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
| Safe Route | Avoids risk zones |
| Quiet Route | Minimizes alerts, approvals, and replanning burden |

### Example Route Comparison

| Route | ETA | Alerts | Approvals | Comm Risk | Cognitive Load Delta | Recommendation |
|---|---:|---:|---:|---:|---:|---|
| Fast Route | 4m 20s | 5 | 2 | high | +9 | Not recommended |
| Safe Route | 5m 40s | 2 | 1 | low | +5 | Secondary |
| Quiet Route | 5m 10s | 1 | 0 | low | +2 | Recommended |

### Explanation Text

```text
현재 운용자 인지부하가 24점으로 과부하 상태입니다.
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
+ Operator Burden Cost
```

### Detailed Equation

```text
AMMP Cost =
Distance Cost
+ Risk Zone Cost
+ Communication Cost
+ Battery Cost
+ Replanning Cost
+ Alert Cost × Load Multiplier
+ Approval Cost × Load Multiplier
+ Attention Peak Cost
```

### Implementation Form

```python
def compute_ammp_cost(route, alerts, approvals, attention_peak, cognitive_load_score):
    W_DISTANCE = 1.0
    W_RISK = 50
    W_COMM = 20
    W_BATTERY = 40
    W_REPLAN = 12
    W_ALERT = 10
    W_APPROVAL = 30
    W_PEAK = 0.5

    load_multiplier = 1.0 + cognitive_load_score / 30.0

    return (
        route.distance * W_DISTANCE
        + route.risk_cells * W_RISK
        + route.comm_shadow_cells * W_COMM
        + route.battery_warning * W_BATTERY
        + route.replanning_events * W_REPLAN
        + len(alerts) * W_ALERT * load_multiplier
        + len(approvals) * W_APPROVAL * load_multiplier
        + attention_peak * W_PEAK
    )
```

### Load Multiplier

```text
Load Multiplier = 1 + Cognitive Load Score / 30
```

| Cognitive Load Score | Load Multiplier |
|---:|---:|
| 0 | 1.0 |
| 15 | 1.5 |
| 30 | 2.0 |

When operator load is high, Alert Cost and Approval Cost become more expensive.  
This makes Quiet Route more likely to be selected.

---

## 15. Cognitive Load Score

The host guideline explicitly requires cognitive load minimization.  
Therefore, this score must be visible and must influence planning.

### Equation

```text
Cognitive Load Score =
active_missions × 2
+ critical_alerts × 5
+ pending_approvals × 4
+ comm_degraded_assets × 3
+ failed_assets × 5
+ high_risk_routes × 4
```

### Score Bands

| Score | State | System Behavior |
|---:|---|---|
| 0 to 10 | Stable | Balanced Fast/Safe/Quiet recommendation |
| 11 to 20 | Caution | Penalize alert-heavy routes |
| 21+ | Overload | Prefer Quiet Route, compress alerts into Decision Packets |

### Cognitive Load Panel Example

```text
Cognitive Load Score: 24 / Overload

원인:
- 활성 임무 4개
- 긴급 알림 1개
- 승인 대기 2개
- 통신저하 예상 1개

시스템 조치:
- 일반 알림 접힘 처리
- Quiet Route 우선 추천
- Decision Packet 생성
```

---

## 16. Alert Prediction

### Expected Alert Types

| Condition | Alert |
|---|---|
| comm_quality expected below 0.5 | Communication degradation alert |
| expected battery below 30% | Return-to-base or battery warning |
| near risk zone | Risk-zone approval request |
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

```text
Approval Cost =
risk_zone_approvals × 30
+ mission_abort_approvals × 25
+ civilian_sensitive_approvals × 35
+ asset_loss_risk_approvals × 40
```

Approval is more expensive than normal alert because it requires responsible human judgment.

---

## 17. Attention Peak Smoothing

Attention Peak Smoothing is an advanced novelty feature.  
It reduces not only total alerts but also alert clustering.

### Bad Plan

```text
4분 10초: UAV-1 위험구역 승인
4분 15초: UGV-1 장애물 재계획
4분 20초: USV-1 통신저하 경고
```

The operator must handle three decisions within 10 seconds.

### Better Plan

```text
4분 10초: UAV-1 위험구역 승인
5분 00초: UGV-1 장애물 재계획
5분 40초: USV-1 통신저하 경고
```

The total number of alerts may be the same, but the decision burden is distributed.

### Pitch Sentence

> AMMP는 알림 개수뿐 아니라 특정 시간대에 알림이 몰리는 Attention Peak도 줄이도록 계획을 조정합니다.

### MVP Implementation

Use a simple time-window approach.

```python
def compute_attention_peak(events, window_sec=60):
    if not events:
        return 0

    max_time = max(event["time_sec"] for event in events)
    peak = 0

    for start in range(0, max_time + window_sec, window_sec):
        end = start + window_sec
        score = sum(
            event["weight"]
            for event in events
            if start <= event["time_sec"] < end
        )
        peak = max(peak, score)

    return peak
```

---

## 18. Human-in-the-Loop Policy

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
| Risk zone entry | Potential asset loss or threat exposure |
| Civilian-sensitive zone approach | Collateral risk |
| Mission abort | Operational impact |
| Unknown target tracking | Misidentification risk |
| Reassigning relay asset | May affect entire mission network |

---

## 19. Decision Packet

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

This is one of the clearest visual demonstrations of cognitive load reduction.

---

## 20. Web UI Specification

### Layout

```text
┌───────────────────────────────┬────────────────────────────┐
│                               │ Mission Intent Panel        │
│         2D Mission Map         ├────────────────────────────┤
│                               │ Asset Condition Panel       │
│ UAV / UGV / USV               ├────────────────────────────┤
│ Risk / Comm / Water Zones      │ Cognitive Load Panel        │
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
| CognitiveLoadPanel | Display score and causes |
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

## 21. Route Comparison Panel

Example:

```text
Route Comparison for UAV-1

Fast Route
ETA 4:20
Alerts 5
Approvals 2
Load Delta +9

Safe Route
ETA 5:40
Alerts 2
Approvals 1
Load Delta +5

Quiet Route
ETA 5:10
Alerts 1
Approvals 0
Load Delta +2

Recommended: Quiet Route
Reason: Current operator load is high.
```

The panel must show:

- ETA
- Alerts
- Approvals
- Cognitive Load Delta
- Total AMMP Cost
- Recommended route
- Reason

---

## 22. ROS2 Humble Architecture

If ROS2 is implemented, use these nodes.

| Node | Role |
|---|---|
| scenario_manager_node | Map, scenario, environment |
| asset_state_node | Publishes UAV/UGV/USV states |
| mission_intent_node | Converts mission intent into subtasks |
| task_allocator_node | Assigns assets based on condition |
| ammp_planner_node | Runs AMMP planning |
| alert_predictor_node | Predicts alerts and approvals |
| cognitive_load_node | Computes operator load |
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
| `/cognitive_load` | Cognitive Load Score |
| `/mission_metrics` | Mission results |

---

## 23. AMMP Planner Input and Output

### Input

```json
{
  "mission": {
    "type": "complex_recon",
    "target": { "x": 30, "y": 12 },
    "priority": "high",
    "required_actions": ["air_recon", "ground_check", "maritime_watch", "relay"],
    "deadline_sec": 480
  },
  "operator_state": {
    "cognitive_load_score": 24,
    "pending_approvals": 2,
    "active_missions": 4
  },
  "assets": [
    {
      "id": "UAV-1",
      "type": "UAV",
      "battery": 82,
      "sensors": ["EO", "IR"],
      "comm_quality": 0.91,
      "status": "available"
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
        "EO/IR 센서 보유",
        "임무 제한시간 내 도착 가능",
        "Fast Route 대비 알림 4개 감소",
        "승인 요청 2회 감소"
      ]
    }
  ],
  "cognitive_load_delta": 2,
  "decision_packets": []
}
```

---

## 24. Backend API Specification

### GET `/api/assets`

Return all assets.

### PATCH `/api/assets/{asset_id}`

Update asset condition.

Request:

```json
{
  "battery": 45,
  "comm_quality": 0.62,
  "health": "degraded"
}
```

### POST `/api/missions`

Create mission.

Request:

```json
{
  "type": "complex_recon",
  "target": { "x": 30, "y": 12 },
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
      "cognitive_load_delta": 9,
      "total_cost": 540
    },
    {
      "id": "quiet",
      "eta_sec": 310,
      "distance": 510,
      "expected_alerts": 1,
      "expected_approvals": 0,
      "cognitive_load_delta": 2,
      "total_cost": 430
    }
  ],
  "recommended_route": "quiet",
  "reason": [
    "현재 Cognitive Load Score가 24로 과부하 상태입니다.",
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
- `sensor_failure`
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

## 25. Core Algorithm Pseudocode

### Full Planning Flow

```python
def plan_mission(mission, assets, map_data, operator_state):
    subtasks = decompose_mission(mission)

    assignments = []

    for subtask in subtasks:
        candidate_assets = filter_assets_by_domain_and_health(subtask, assets)

        scored_assets = []
        for asset in candidate_assets:
            fit_score = compute_mission_fit(asset, subtask, operator_state)
            scored_assets.append((asset, fit_score))

        selected_asset = max(scored_assets, key=lambda x: x[1])[0]

        routes = generate_route_candidates(selected_asset, subtask, map_data)

        scored_routes = []
        for route in routes:
            alerts = predict_alerts(route, selected_asset, subtask)
            approvals = predict_approvals(route, selected_asset, subtask)
            attention_peak = compute_attention_peak(alerts + approvals)

            cost = compute_ammp_cost(
                route=route,
                alerts=alerts,
                approvals=approvals,
                attention_peak=attention_peak,
                cognitive_load_score=operator_state.cognitive_load_score
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

### Cognitive Load

```python
def compute_cognitive_load(state):
    return (
        state.active_missions * 2
        + state.critical_alerts * 5
        + state.pending_approvals * 4
        + state.comm_degraded_assets * 3
        + state.failed_assets * 5
        + state.high_risk_routes * 4
    )
```

---

## 26. Demo Scenario

### Scenario Name

**해안·도심 복합지역 미상 이동체 확인 임무**

### Initial Assets

| Asset | State |
|---|---|
| UAV-1 | battery 82%, EO/IR, fast, recon suitable |
| UAV-2 | battery 65%, relay capable |
| UGV-1 | battery 74%, LiDAR, ground check capable |
| USV-1 | battery 88%, RF/EO, maritime watch capable |

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

| Route | ETA | Alerts | Approvals | Cognitive Load Delta |
|---|---:|---:|---:|---:|
| Fast | 4:20 | 5 | 2 | +9 |
| Safe | 5:40 | 2 | 1 | +5 |
| Quiet | 5:10 | 1 | 0 | +2 |

Current load:

```text
Cognitive Load Score = 24, Overload
```

Recommendation:

```text
Quiet Route
```

### Step 4: Simulated Event

Button click:

```text
UAV-1 battery drop
```

System state:

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
Cognitive Load Peak 감소: 31 → 19
예상 인력 절감률: 75%
```

---

## 27. Metrics

### Required Metrics

| Metric | Meaning |
|---|---|
| Mission Success Rate | completed subtasks / total subtasks |
| Operator Interventions | approvals, manual reassignments, manual route changes |
| Expected Alerts Reduced | alert reduction compared to Fast Route baseline |
| Approvals Reduced | approval reduction compared to Fast Route baseline |
| Cognitive Load Delta | before/after load difference |
| Cognitive Load Peak | max load during mission |
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

## 28. Host Requirement Presentation Points

### Mission-Level Abstraction

> 운용자는 UAV, UGV, USV를 각각 조종하지 않고 “A구역 복합 정찰”이라는 임무 의도를 입력합니다. 시스템은 이를 상공 정찰, 지상 확인, 해안 감시, 통신 중계로 자동 분해합니다.

### Autonomous Role Allocation

> 각 기체의 배터리, 센서, 위치, 통신상태, 현재 임무를 비교해 적합한 역할을 자동으로 배정합니다.

### Cognitive Load Monitoring and Priority Alerts

> Cognitive Load Score를 계산하고, 운용자 과부하 시 일반 알림은 접고 Decision Packet 형태로 핵심 판단만 제공합니다.

### Human-in-the-Loop

> 낮은 위험의 반복 판단은 자동 처리하고, 위험구역 진입·임무 포기·통신중계 자산 전환처럼 책임 판단이 필요한 경우에만 승인 요청합니다.

### Measurement Framework

> Fast Route 대비 알림 감소 수, 승인 요청 감소 수, Cognitive Load Peak 감소, 임무 성공률, 대응시간, 인력 절감률을 측정합니다.

---

## 29. Implementation Priorities

### Phase 1: Pure Web + Backend MVP

1. Create static 2D grid map.
2. Render UAV, UGV, USV.
3. Add asset condition editor.
4. Add mission intent input.
5. Implement mission decomposition.
6. Implement simple condition-based task allocation.
7. Generate three route candidates: Fast, Safe, Quiet.
8. Compute alerts, approvals, load delta, AMMP cost.
9. Display route comparison.
10. Generate Decision Packet for battery drop or risk-zone case.
11. Display final metrics.

### Phase 2: ROS2 Humble Integration

1. Create ROS2 package `missiondeck_ros`.
2. Implement `asset_state_node`.
3. Implement `mission_intent_node`.
4. Implement `task_allocator_node`.
5. Implement `ammp_planner_node`.
6. Implement `cognitive_load_node`.
7. Publish results to topics.
8. Connect web UI via FastAPI bridge or rosbridge.

### Phase 3: Demo Polish

1. Add animated movement.
2. Add event buttons.
3. Add route colors.
4. Add Korean presentation labels.
5. Add explainability text.
6. Add final mission report card.
7. Add screenshot-friendly UI layout.

---

## 30. Acceptance Criteria

The MVP is complete when all of the following are true:

- The web UI shows a 2D map.
- UAV, UGV, USV are visible.
- At least 3 heterogeneous UxVs are controllable, preferably 4 assets.
- The operator can edit battery, sensor, communication quality, and health.
- The operator can create a complex recon mission.
- The system decomposes complex recon into air recon, ground check, maritime watch, and relay.
- The system assigns suitable assets automatically.
- The system generates Fast, Safe, and Quiet routes.
- The system computes expected alerts and approvals for each route.
- The system computes Cognitive Load Score.
- High cognitive load makes Quiet Route more likely.
- A battery drop event generates a Decision Packet.
- The UI shows why a route was recommended.
- The final report shows alert reduction, approval reduction, cognitive load peak reduction, mission success rate, and manpower reduction.

---

## 31. Development Rules for Codex

When modifying this project:

1. Preserve the core concept of AMMP.
2. Do not reduce AMMP to simple shortest-path planning.
3. Always include operator burden in scoring.
4. Prefer explainable rule-based logic over black-box ML for MVP.
5. Keep the UI simple but decision-focused.
6. Avoid military weaponization features. This is a command-and-control simulator for mission allocation, monitoring, and operator burden reduction.
7. Human-in-the-loop must remain visible.
8. Do not hide why the system made a recommendation.
9. Keep Korean labels available for demo.
10. Make the system robust enough for a short live demo.

---

## 32. Final Concept Text

Use this in README, presentation, or project intro:

```text
AMMP, Alert-Minimizing Mission Planning은 단일 운용자가 UAV·UGV·USV를 동시에 운용할 때 발생하는 알림 과잉과 승인 부담을 줄이기 위한 임무계획 방식이다. 시스템은 임무 성공률만 최적화하지 않고, 예상 알림 수, 승인 요청 수, 재계획 가능성, 운용자 인지부하 증가량을 함께 계산해 현재 운용자가 가장 안정적으로 감독할 수 있는 임무배정과 경로를 추천한다.
```

Final soul of the project:

> **AMMP는 가장 빠른 계획이 아니라, 한 명의 운용자가 가장 적게 개입해도 임무가 무너지지 않는 계획을 찾는다.**