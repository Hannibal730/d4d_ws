# Route Planner 비용 함수 설명

이 문서는 `route_planner_node.py`에서 각 UxV 후보 경로를 평가하고 최종 기체를 선택할 때 사용하는 비용 함수와 사전 필터링 조건을 정리한 것이다. 현재 구현에서 비용은 "거리", "위험구역", "배터리 여유", "통신 품질", "장비 상태"를 하나의 스칼라 점수로 합산하며, 점수가 가장 낮은 feasible 후보가 선택된다.

## 전체 선택 흐름

플래너 요청이 들어오면 다음 순서로 후보를 평가한다.

1. 요청의 `target_node_id`, `vehicle_type`을 확인한다.
2. 목표 노드가 존재하는지, 해당 차량 타입이 접근 가능한 노드인지 검사한다.
3. `self.assets` 중 요청 차량 타입과 일치하는 UxV만 후보로 삼는다.
4. 특정 `vehicle_id`가 요청되었으면 해당 UxV만 후보로 삼는다.
5. 각 후보마다 `plan_for_asset()`으로 경로를 만들고 비용을 계산한다.
6. `feasible == True`인 후보 중 `total_cost`가 가장 낮은 후보를 선택한다.

최종 선택식은 다음과 같다.

```text
selected = argmin(total_cost(candidate))
```

## Feasible 여부를 먼저 결정하는 조건

비용을 계산하기 전에 아래 조건 중 하나라도 걸리면 해당 후보는 탈락한다. 탈락 후보는 `feasible=False`, `total_cost=100000.0`으로 반환되지만, 최종 선택 대상에는 포함되지 않는다.

### 장비 상태

```text
device_state == "disabled" -> 탈락
```

`disabled` 상태인 장비는 비용을 크게 주는 방식이 아니라 경로 계획 전 단계에서 바로 제외된다.

### 출발 배터리

```text
battery <= min_start_battery_pct -> 탈락
```

기본값:

```text
min_start_battery_pct = 5.0
```

현재 배터리가 출발 최소 배터리 이하이면 경로를 계산하지 않는다.

### 목표 노드 위험구역 포함 여부

```text
target_node inside risk zone + clearance margin -> 탈락
```

위험구역 판정에는 `risk_clearance_margin_km`가 추가된다. 기본값은 다음과 같다.

```text
risk_clearance_margin_km = 3.0
```

즉, 위험구역 반경이 `radius_km`라면 실제 회피 판정 반경은 다음과 같다.

```text
effective_risk_radius_km = radius_km + risk_clearance_margin_km
```

### 도착 배터리

경로 산출 후 예상 도착 배터리가 최소 도착 배터리보다 낮으면 탈락한다.

```text
battery_after < min_arrival_battery_pct -> 탈락
```

기본값:

```text
min_arrival_battery_pct = 3.0
```

단, 사용자가 특정 `vehicle_id`를 지정한 경우 `allow_manual_override=True`가 되어 이 도착 배터리 탈락 조건은 무시된다. 그래도 비용 계산에는 낮은 배터리가 반영된다.

### 위험구역 교차

경로의 각 segment에 대해 시작점, 끝점, segment 자체가 위험구역과 겹치는지 검사한다.

```text
crossing_segments exists and allow_risk_crossing_edges == False -> 탈락
```

기본값:

```text
allow_risk_crossing_edges = False
```

따라서 기본 설정에서는 위험구역과 교차하는 경로는 비용이 커지는 것이 아니라 후보에서 제외된다.

## 총 비용 함수

후보가 feasible이면 다음 식으로 총 비용을 계산한다.

```text
total_cost =
    route_cost
  + risk_cost
  + battery_cost
  + comm_cost
  + condition_cost
```

각 항목은 아래와 같다.

```text
route_cost     = distance_km
risk_cost      = route_plan["risk_cost"]
battery_cost   = max(0.0, 35.0 - battery_after) * battery_weight
comm_cost      = max(0.0, 1.0 - comm_quality) * comm_weight
condition_cost = device_penalty(device_state)
```

기본 가중치:

```text
battery_weight = 5.0
comm_weight    = 40.0
```

따라서 기본값 기준으로 배터리 1% 부족분은 비용 5점, 통신 품질 0.1 부족분은 비용 4점이다.

## 거리 비용: route_cost

거리 비용은 경로 총 길이 km 값을 그대로 사용한다.

```text
route_cost = distance_km
```

예를 들어 경로가 12.3 km이면 `route_cost=12.3`이다. 거리 1 km가 비용 1점으로 반영된다.

거리 계산 방식은 차량 타입과 미션 타입에 따라 달라진다.

### UAV 또는 직접 우회 경로

UAV는 `plan_direct_detour_route()`를 사용한다.

1. 후보 경로 `[start, target]`을 먼저 만든다.
2. 각 위험구역 주변에 30도 간격으로 우회 waypoint를 생성한다.
3. `[start, waypoint, target]` 후보를 만든다.
4. `[start, waypoint1, waypoint2, target]` 후보도 만든다.
5. 위험구역과 겹치지 않는 후보 중 haversine 거리 합이 가장 짧은 경로를 선택한다.

각 segment 거리는 `haversine_km()`로 계산한다.

```text
distance_km = sum(haversine_km(route_nodes[i], route_nodes[i + 1]))
```

UAV 우회 waypoint는 각 위험구역 중심으로부터 다음 반경에 생성된다.

```text
waypoint_radius_km = risk_zone.radius_km + 8.0
```

그리고 waypoint 자체가 clearance margin을 포함한 위험구역 안에 있으면 제외된다.

### UGV/USV 그래프 경로

UGV와 USV는 지도 그래프가 있을 때 `plan_graph_route()`를 사용한다.

1. 현재 위치를 접근 가능한 그래프 노드에 snap한다.
2. snap 지점부터 target까지 Dijkstra 방식으로 최단 경로를 찾는다.
3. 최종 거리에는 현재 위치에서 snap 노드까지의 직선 거리와 그래프 경로 거리를 더한다.

```text
distance_km = snap_distance_km + graph_distance_km
```

edge의 거리 값은 다음 우선순위로 정한다.

```text
edge.distance_m > 0이면 edge.distance_m / 1000.0
그 외에는 haversine_km(edge.from, edge.to)
```

UGV는 `edge.domain == "land"`인 edge만 사용하고, USV는 `edge.domain == "water"`인 edge만 사용한다.

### RETURN_HOME

`mission_type == "RETURN_HOME"`일 때는 다음 순서로 경로를 선택한다.

1. UGV/USV이고 target이 그래프 노드이면 그래프 경로를 먼저 시도한다.
2. 그래프 경로가 없거나 UAV이면 직접/우회 경로를 사용한다.

## 위험구역 비용: risk_cost

위험구역은 두 단계에서 처리된다.

### 그래프 탐색 중 위험 비용

`shortest_graph_path()`에서는 edge가 위험구역을 지나면 탐색 비용에 `risk_crossing_edge_cost_km`를 더한다.

```text
search_edge_cost = distance_km + risk_crossing_edge_cost_km
```

다만 기본값은 다음과 같다.

```text
allow_risk_crossing_edges = False
risk_crossing_edge_cost_km = inf
```

기본 설정에서는 위험 edge가 그래프에서 제외되므로 이 penalty가 실제 선택에 쓰이지 않는다. 만약 `allow_risk_crossing_edges=True`로 바꾸고 `risk_crossing_edge_cost_km`를 유한한 값으로 설정하면, 위험 edge를 완전히 금지하지 않고 매우 비싼 edge로 취급할 수 있다.

그래프 탐색 결과의 `risk_cost`는 다음 값으로 반환된다.

```text
risk_cost = search_cost - travel_cost
```

즉, 순수 이동 거리 비용을 제외한 위험 penalty의 합이다.

### 최종 경로 segment 재검사

경로가 만들어진 뒤 `risk_crossing_route_segments()`가 전체 segment를 다시 검사한다. 여기서 위험구역 교차가 발견되면 다음 처리 중 하나를 한다.

```text
allow_risk_crossing_edges == False:
    후보 탈락

allow_risk_crossing_edges == True:
    risk_cost += number_of_crossing_segments * risk_crossing_edge_cost_km
```

만약 `risk_cost`가 무한대이면 후보는 탈락한다.

```text
isinf(risk_cost) -> 탈락
```

## 배터리 사용량과 배터리 비용

예상 배터리 사용량은 `estimate_battery_used()`에서 계산한다.

```text
battery_used =
    distance_km
  * battery_pct_per_km[vehicle_type]
  * battery_state_multiplier[device_state]
  * battery_drain_scale
```

기본 vehicle별 소모율:

```text
UAV = 0.18 %/km
UGV = 0.08 %/km
USV = 0.06 %/km
```

기본 장비 상태별 배터리 multiplier:

```text
good     = 1.0
caution  = 1.35
critical = 2.0
unknown  = 1.5
```

기본 전체 스케일:

```text
battery_drain_scale = 1.0
```

예상 도착 배터리는 다음과 같다.

```text
battery_after = battery - battery_used
```

배터리 비용은 도착 배터리가 35%보다 낮을 때만 발생한다.

```text
battery_cost = max(0.0, 35.0 - battery_after) * battery_weight
```

기본 `battery_weight=5.0`이므로 예상 도착 배터리가 30%이면:

```text
battery_cost = (35.0 - 30.0) * 5.0 = 25.0
```

예상 도착 배터리가 35% 이상이면 `battery_cost=0.0`이다.

## 통신 품질 비용

통신 품질은 `comm_quality`가 1.0에서 얼마나 부족한지를 비용으로 환산한다.

```text
comm_cost = max(0.0, 1.0 - comm_quality) * comm_weight
```

기본값:

```text
comm_weight = 40.0
```

예시:

```text
comm_quality = 0.8
comm_cost = (1.0 - 0.8) * 40.0 = 8.0
```

`comm_quality >= 1.0`이면 `comm_cost=0.0`이다.

## 장비 상태 비용

장비 상태 비용은 `device_penalty()`에서 고정 penalty로 계산한다.

```text
good     -> 0.0
caution  -> 35.0
critical -> 120.0
disabled -> 100000.0
unknown  -> 60.0
```

주의할 점은 `disabled`는 이 비용 계산까지 오기 전에 이미 탈락한다는 것이다. 따라서 `disabled -> 100000.0`은 함수 정의상 존재하지만 일반적인 평가 경로에서는 사용되지 않는다.

## 그래프 탐색 비용과 최종 후보 비용의 차이

코드에는 비용이 두 종류 있다.

### 그래프 탐색 비용

`shortest_graph_path()` 안에서 Dijkstra 우선순위를 정하기 위한 비용이다.

```text
search_cost = sum(distance_km + risk_penalty)
```

이 비용은 "어떤 경로를 선택할지"를 정하는 데 사용된다. 배터리, 통신 품질, 장비 상태는 여기서 고려하지 않는다.

### 최종 후보 비용

`plan_for_asset()`에서 각 UxV 후보를 비교하기 위한 비용이다.

```text
total_cost =
    distance_km
  + risk_cost
  + battery_cost
  + comm_cost
  + condition_cost
```

이 비용은 "어떤 UxV를 선택할지"를 정하는 데 사용된다.

즉, 그래프 내부에서는 거리와 위험구역 penalty로 경로를 고르고, 후보 비교 단계에서는 해당 경로를 가진 UxV의 배터리, 통신, 상태까지 합쳐 최종 점수를 만든다.

## 계산 예시

다음과 같은 UGV 후보가 있다고 가정한다.

```text
distance_km = 10.0
battery = 40.0
device_state = "caution"
comm_quality = 0.75
risk_cost = 0.0
```

UGV 기본 배터리 소모율은 `0.08 %/km`, caution multiplier는 `1.35`이다.

```text
battery_used = 10.0 * 0.08 * 1.35 * 1.0 = 1.08
battery_after = 40.0 - 1.08 = 38.92
```

도착 배터리가 35% 이상이므로:

```text
battery_cost = 0.0
```

통신 비용:

```text
comm_cost = (1.0 - 0.75) * 40.0 = 10.0
```

상태 비용:

```text
condition_cost = 35.0
```

총 비용:

```text
total_cost = 10.0 + 0.0 + 0.0 + 10.0 + 35.0 = 55.0
```

다른 후보와 비교할 때 이 후보의 점수는 `55.0`이며, feasible 후보 중 가장 낮은 점수를 가진 후보가 최종 선택된다.

## 튜닝 포인트

아래 ROS parameter를 조정하면 비용 함수의 성향을 바꿀 수 있다.

```text
battery_weight
comm_weight
min_start_battery_pct
min_arrival_battery_pct
battery_drain_scale
uav_battery_pct_per_km
ugv_battery_pct_per_km
usv_battery_pct_per_km
good_battery_multiplier
caution_battery_multiplier
critical_battery_multiplier
unknown_battery_multiplier
allow_risk_crossing_edges
risk_crossing_edge_cost_km
risk_clearance_margin_km
```

튜닝 방향 예시는 다음과 같다.

- 더 먼 경로라도 안전한 경로를 선호하려면 `risk_crossing_edge_cost_km`를 크게 유지하고 `allow_risk_crossing_edges=False`를 사용한다.
- 위험구역 통과를 완전히 금지하지 않고 최후의 선택지로 두려면 `allow_risk_crossing_edges=True`와 유한한 `risk_crossing_edge_cost_km`를 사용한다.
- 배터리 여유가 많은 UxV를 더 강하게 선호하려면 `battery_weight`를 키운다.
- 통신 품질이 좋은 UxV를 더 강하게 선호하려면 `comm_weight`를 키운다.
- 오래되거나 상태가 나쁜 장비를 더 피하고 싶으면 `device_penalty()`의 caution/critical penalty를 조정한다.
