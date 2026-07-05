# Route Planner 비용 함수 수식 정리

이 문서는 `route_planner_node.py`의 후보 UxV 선택 비용 함수를 수식적으로 정리한다. 플래너는 각 후보 UxV에 대해 경로를 생성하고, feasible 후보 중 총 비용이 가장 작은 후보를 선택한다.

## 1. 후보 선택 문제 정의

요청된 차량 타입을 `v`라 하고, 해당 타입에 맞는 후보 UxV 집합을 다음과 같이 둔다.

```math
\mathcal{A}_v = \{a \mid type(a) = v\}
```

각 후보 `a`에 대해 경로 `R_a`와 총 비용 `J(a)`를 계산한다. 최종 선택 후보 `a^*`는 feasible 후보 집합 안에서 총 비용이 최소인 후보이다.

```math
a^* = \arg\min_{a \in \mathcal{A}_v,\; F(a)=1} J(a)
```

여기서 `F(a)`는 후보의 feasible 여부이다.

```math
F(a) =
\begin{cases}
1, & \text{candidate is feasible} \\
0, & \text{candidate is rejected}
\end{cases}
```

구현에서는 `F(a)=0`인 후보를 최종 선택에서 제외한다. rejected 후보는 `total_cost = 100000.0`으로 반환되지만, 실제 선택은 `feasible == True`인 후보에 대해서만 수행된다.

## 2. 총 비용 함수

후보 `a`의 총 비용은 다음 5개 비용 항의 합이다.

```math
J(a)
= C_{route}(a)
+ C_{risk}(a)
+ C_{battery}(a)
+ C_{comm}(a)
+ C_{condition}(a)
```

코드 변수명으로 표현하면 다음과 같다.

```text
total_cost =
    route_cost
  + risk_cost
  + battery_cost
  + comm_cost
  + condition_cost
```

각 구성 요소는 아래 수식으로 계산된다.

```math
C_{route}(a) = D(R_a)
```

```math
C_{risk}(a) = P_{risk}(R_a)
```

```math
C_{battery}(a)
= w_b \cdot \max(0,\; B_{safe} - B_{after}(a))
```

```math
C_{comm}(a)
= w_c \cdot \max(0,\; 1 - q_{comm}(a))
```

```math
C_{condition}(a)
= P_{state}(s_a)
```

기본 상수는 다음과 같다.

```text
w_b = battery_weight = 5.0
w_c = comm_weight = 40.0
B_safe = 35.0
```

## 3. 경로 거리 비용

경로 `R`을 waypoint sequence로 둔다.

```math
R = (p_0, p_1, \dots, p_n)
```

여기서 `p_0`는 UxV의 현재 위치, `p_n`은 target node이다. 거리 비용은 경로 총 길이 `D(R)`와 같다.

```math
C_{route}(a) = D(R_a)
```

### 3.1 직접/우회 경로의 거리

UAV 또는 직접 우회 경로에서는 각 segment의 haversine 거리 합을 사용한다.

```math
D(R) = \sum_{i=0}^{n-1} d_H(p_i, p_{i+1})
```

`d_H`는 haversine 거리이다.

```math
d_H(p_i, p_j)
= 2R_E \cdot
\arcsin
\left(
\sqrt{
\sin^2\left(\frac{\Delta\phi}{2}\right)
+ \cos\phi_i\cos\phi_j\sin^2\left(\frac{\Delta\lambda}{2}\right)
}
\right)
```

```text
R_E = EARTH_RADIUS_KM = 6371.0088 km
```

여기서 `phi`는 위도 radian, `lambda`는 경도 radian이다.

### 3.2 그래프 경로의 거리

UGV/USV 그래프 경로에서는 먼저 현재 위치를 그래프 노드 `s`에 snap한다.

```math
s = snap(p_0)
```

그래프 경로 edge sequence를 다음과 같이 둔다.

```math
E_R = (e_1, e_2, \dots, e_m)
```

전체 경로 거리는 snap 거리와 그래프 edge 거리 합이다.

```math
D(R) = d_H(p_0, s) + \sum_{k=1}^{m} d(e_k)
```

각 edge 거리 `d(e)`는 다음과 같이 계산된다.

```math
d(e) =
\begin{cases}
\frac{distance\_m(e)}{1000}, & distance\_m(e) > 0 \\
d_H(from(e), to(e)), & distance\_m(e) \le 0
\end{cases}
```

차량 타입별 edge domain 제약은 다음과 같다.

```math
UGV: domain(e) = land
```

```math
USV: domain(e) = water
```

## 4. 위험구역 비용

위험구역 집합을 다음과 같이 둔다.

```math
\mathcal{Z} = \{z_1, z_2, \dots, z_l\}
```

각 위험구역 `z`는 중심점 `c_z`와 반경 `r_z`를 가진다. 코드에서는 clearance margin을 반영한 유효 위험 반경을 사용한다.

```math
\bar{r}_z = r_z + r_{margin}
```

```text
r_margin = risk_clearance_margin_km = 3.0
```

### 4.1 노드 위험 판정

노드 `p`가 위험구역 내부에 있는지 나타내는 indicator를 다음과 같이 정의한다.

```math
I_{node}(p) =
\begin{cases}
1, & \exists z \in \mathcal{Z}: d_H(p, c_z) \le \bar{r}_z \\
0, & \text{otherwise}
\end{cases}
```

### 4.2 Segment 위험 판정

segment `(p_i, p_j)`가 위험구역을 통과하는지 나타내는 indicator를 다음과 같이 정의한다.

```math
I_{seg}(p_i, p_j) =
\begin{cases}
1, & \exists z \in \mathcal{Z}: d_{\perp}(c_z, \overline{p_i p_j}) \le \bar{r}_z \\
0, & \text{otherwise}
\end{cases}
```

`d_perp`는 위험구역 중심점에서 segment까지의 최단거리이다. 구현에서는 위경도를 local km 좌표로 근사한 뒤 point-to-segment distance를 계산한다.

최종 segment 위험 indicator는 노드 포함 여부와 segment 교차 여부를 함께 본다.

```math
X(p_i, p_j)
= I_{node}(p_i) \lor I_{node}(p_j) \lor I_{seg}(p_i, p_j)
```

### 4.3 위험구역 통과 금지 조건

기본 설정에서는 위험구역 교차가 있는 경로를 허용하지 않는다.

```text
allow_risk_crossing_edges = False
```

따라서 다음 조건이면 후보는 infeasible이다.

```math
\exists i \in \{0,\dots,n-1\}: X(p_i, p_{i+1}) = 1
\quad \Rightarrow \quad F(a)=0
```

위험구역 통과를 허용하는 경우에는 segment당 penalty를 더한다.

```math
C_{risk}(a)
= \lambda_r \sum_{i=0}^{n-1} X(p_i, p_{i+1})
```

```text
lambda_r = risk_crossing_edge_cost_km
```

기본값은 무한대이다.

```text
risk_crossing_edge_cost_km = inf
```

따라서 기본 설정에서는 위험구역 교차 경로가 비용 경쟁을 하는 것이 아니라 제외된다.

### 4.4 그래프 탐색 내부의 위험 비용

그래프 탐색에서는 Dijkstra 우선순위용 edge search cost를 따로 계산한다.

edge `e=(u,w)`의 위험 indicator를 다음과 같이 둔다.

```math
X_e = I_{node}(u) \lor I_{node}(w) \lor I_{seg}(u,w)
```

그래프 탐색용 edge 비용은 다음과 같다.

```math
c_{search}(e) = d(e) + \lambda_r X_e
```

경로의 탐색 비용과 실제 이동 거리 비용은 다음과 같다.

```math
S(R) = \sum_{e \in E_R} c_{search}(e)
```

```math
T(R) = \sum_{e \in E_R} d(e)
```

그래프 탐색에서 반환되는 위험 비용은 다음과 같다.

```math
C_{risk}^{graph}(R) = S(R) - T(R)
```

즉,

```math
C_{risk}^{graph}(R) = \lambda_r \sum_{e \in E_R} X_e
```

단, `allow_risk_crossing_edges=False`이면 `X_e=1`인 edge는 그래프에서 제거된다.

## 5. 배터리 비용

후보 `a`의 현재 배터리를 `B_0(a)`라고 둔다.

```math
B_0(a) = battery(a)
```

차량 타입별 km당 배터리 소모율을 `rho_v`라 한다.

```math
\rho_v =
\begin{cases}
0.18, & v=UAV \\
0.08, & v=UGV \\
0.06, & v=USV
\end{cases}
```

장비 상태별 배터리 소모 multiplier를 `m(s_a)`라 한다.

```math
m(s_a) =
\begin{cases}
1.00, & s_a=good \\
1.35, & s_a=caution \\
2.00, & s_a=critical \\
1.50, & s_a=unknown
\end{cases}
```

전체 배터리 소모 scale을 `gamma_b`라 둔다.

```text
gamma_b = battery_drain_scale = 1.0
```

예상 배터리 사용량은 다음과 같다.

```math
B_{used}(a) = D(R_a) \cdot \rho_v \cdot m(s_a) \cdot \gamma_b
```

예상 도착 배터리는 다음과 같다.

```math
B_{after}(a) = B_0(a) - B_{used}(a)
```

배터리 비용은 도착 배터리가 안전 기준 `B_safe=35.0`보다 낮은 경우에만 증가한다.

```math
C_{battery}(a)
= w_b \cdot \max(0,\; B_{safe} - B_{after}(a))
```

기본값을 대입하면 다음과 같다.

```math
C_{battery}(a)
= 5.0 \cdot \max(0,\; 35.0 - B_{after}(a))
```

## 6. 통신 품질 비용

후보 `a`의 통신 품질을 `q_comm(a)`라 한다.

```math
q_{comm}(a) = comm\_quality(a)
```

통신 품질 비용은 1.0에서 부족한 만큼 선형 penalty를 부여한다.

```math
C_{comm}(a)
= w_c \cdot \max(0,\; 1 - q_{comm}(a))
```

기본값을 대입하면 다음과 같다.

```math
C_{comm}(a)
= 40.0 \cdot \max(0,\; 1 - q_{comm}(a))
```

예를 들어 `q_comm=0.75`이면 다음과 같다.

```math
C_{comm} = 40.0 \cdot (1 - 0.75) = 10.0
```

## 7. 장비 상태 비용

후보 `a`의 장비 상태를 `s_a`라 한다.

```math
s_a = device\_state(a)
```

장비 상태 비용은 piecewise penalty 함수이다.

```math
C_{condition}(a) = P_{state}(s_a)
```

```math
P_{state}(s_a) =
\begin{cases}
0, & s_a=good \\
35, & s_a=caution \\
120, & s_a=critical \\
100000, & s_a=disabled \\
60, & \text{otherwise}
\end{cases}
```

단, 실제 평가 흐름에서는 `disabled` 상태가 비용 계산 전에 infeasible 처리된다.

```math
s_a=disabled \quad \Rightarrow \quad F(a)=0
```

## 8. Feasibility 제약 조건

총 비용 `J(a)`는 아래 제약 조건을 통과한 후보에 대해서만 최종 선택에 사용된다.

### 8.1 출발 배터리 제약

```math
B_0(a) > B_{start,min}
```

```text
B_start,min = min_start_battery_pct = 5.0
```

코드에서는 `battery <= min_start_battery_pct`이면 탈락한다.

### 8.2 도착 배터리 제약

```math
B_{after}(a) \ge B_{arrival,min}
```

```text
B_arrival,min = min_arrival_battery_pct = 3.0
```

단, 특정 `vehicle_id`를 사용자가 직접 지정한 경우에는 manual override로 이 제약을 적용하지 않는다.

### 8.3 목표 노드 위험구역 제약

target node를 `p_n`이라 하면 다음 조건을 만족해야 한다.

```math
I_{node}(p_n) = 0
```

즉 target node가 clearance margin을 포함한 위험구역 내부에 있으면 후보는 infeasible이다.

### 8.4 위험구역 교차 제약

기본 설정에서는 모든 경로 segment가 위험구역을 통과하지 않아야 한다.

```math
\sum_{i=0}^{n-1} X(p_i, p_{i+1}) = 0
```

`allow_risk_crossing_edges=True`인 경우에는 이 제약을 완화하고 `C_risk`에 penalty로 반영한다.

## 9. 구현 기준 최종 수식

현재 기본 parameter를 기준으로 feasible 후보의 총 비용을 펼쳐 쓰면 다음과 같다.

```math
J(a)
= D(R_a)
+ C_{risk}(a)
+ 5.0 \cdot \max(0,\; 35.0 - B_{after}(a))
+ 40.0 \cdot \max(0,\; 1 - q_{comm}(a))
+ P_{state}(s_a)
```

여기서,

```math
B_{after}(a)
= B_0(a)
- D(R_a) \cdot \rho_v \cdot m(s_a) \cdot \gamma_b
```

따라서 완전히 대입하면 다음과 같다.

```math
J(a)
= D(R_a)
+ C_{risk}(a)
+ 5.0 \cdot
\max\left(
0,\;
35.0 -
\left[
B_0(a)
- D(R_a)\rho_v m(s_a)\gamma_b
\right]
\right)
+ 40.0 \cdot \max(0,\; 1 - q_{comm}(a))
+ P_{state}(s_a)
```

기본 설정에서 위험구역 통과가 금지되어 있고 feasible 후보만 비교한다면 보통 다음처럼 해석할 수 있다.

```math
C_{risk}(a)=0
\quad \text{for feasible routes under default risk policy}
```

즉, 기본 정책에서는 위험구역을 통과하는 후보는 `C_risk`가 커지는 것이 아니라 feasible 후보에서 제외된다.

## 10. 계산 예시

다음 후보를 가정한다.

```text
vehicle_type = UGV
D(R_a) = 10.0 km
B_0(a) = 40.0 %
s_a = caution
q_comm(a) = 0.75
C_risk(a) = 0.0
```

UGV의 배터리 소모율과 caution multiplier는 다음과 같다.

```math
\rho_{UGV}=0.08,\quad m(caution)=1.35,\quad \gamma_b=1.0
```

배터리 사용량:

```math
B_{used}
= 10.0 \cdot 0.08 \cdot 1.35 \cdot 1.0
= 1.08
```

도착 배터리:

```math
B_{after}
= 40.0 - 1.08
= 38.92
```

배터리 비용:

```math
C_{battery}
= 5.0 \cdot \max(0,\; 35.0 - 38.92)
= 0.0
```

통신 비용:

```math
C_{comm}
= 40.0 \cdot \max(0,\; 1 - 0.75)
= 10.0
```

상태 비용:

```math
C_{condition}
= P_{state}(caution)
= 35.0
```

총 비용:

```math
J(a)
= 10.0 + 0.0 + 0.0 + 10.0 + 35.0
= 55.0
```
