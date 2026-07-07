# 프로젝트명
KannibalDX: 전장 상황 인식 및 다중 무인제어 자동화 C2 시스템

# 목적
현대 전장에서 무인 체계(UxV)의 비중이 급증함에 따라, 기존의 1:1(운용자:무인기) 조종 방식은 한계에 다다랐습니다. 본 프로젝트는 한 명의 운용자가 다종·다수의 무인기(UAV, UGV, USV)를 동시에 통제하는 1:N 운영체계를 구축하여 작전 효율을 극대화하는 것을 목적으로 합니다[cite: 3, 5, 6].

# 기술 스택
* **OS / Middleware:** Ubuntu 22.04 LTS, ROS2 (Humble)[cite: 1, 8, 9]
* **Frontend:** Vanilla JavaScript, HTML5, CSS3, SVG 기반 커스텀 렌더링[cite: 5, 6, 7]
* **AI & Vision:** YOLO (Ultralytics), OpenCV, ZMQ (비디오 스트리밍 브릿지)[cite: 8, 9]
* **Backend & Logic:** Python3, A* 기반 경로 탐색 및 자동화 상태 머신[cite: 1, 4]

# 해결하고자 하는 문제
1:N 다중 무인기 운영 체계로 전환 시, 현장에서는 다음과 같은 치명적인 문제가 발생합니다.
1. **운용자 인지 과부하(Cognitive Overload):** 장비 대수에 비례하여 통신 상태, 배터리, 에러 알림이 선형적으로 폭증하여 운용자의 피로도가 급증하고 핵심 정보(적군 탐지 등)를 놓칠 위험이 커집니다[cite: 5, 6].
2. **수동 개입으로 인한 작전 공백:** 기존 시스템은 기체가 지정된 위치로 이동하는 데 그칩니다. 기체의 배터리가 부족해지거나 통신이 두절될 경우 운용자가 수동으로 개입하여 복귀시키고 새 기체를 투입해야 하며, 이 과정에서 심각한 작전 공백이 발생합니다[cite: 3].

# 해결 방안 및 구현 상세
저희는 리눅스 우분투 환경의 ROS2 통신 체계와 자체 개발한 웹 관제 UI(KannibalDX)를 결합하여 전 과정의 자동화를 구현했습니다.

**1. 전장 상황 통합 시각화 및 경보 자동 분류**
각 무인기의 상태 데이터(배터리, 통신 품질 등)를 ROS2 브릿지를 통해 웹 UI로 실시간 전송합니다[cite: 2]. 웹 UI는 대한민국 GeoJSON 맵 데이터를 기반으로 육상/해상 노드와 위험 구역(Risk Zones)을 시각화합니다[cite: 5]. 
특히, 알림의 홍수를 막기 위해 통신 품질과 배터리 잔량에 따라 시스템이 자동으로 상태를 3단계(GREEN, AMBER, RED)로 분류하며, 운용자는 고위험(RED) 알림에만 집중할 수 있도록 필터링을 제공하여 인지 부하를 획기적으로 줄였습니다[cite: 2, 5, 7].

**2. AI 비전 기반 위협 자동 탐지 및 시각화**
단순한 상태 모니터링을 넘어, UAV에서 촬영되는 비디오 스트림을 ZMQ를 통해 수신하고 YOLO 객체 인식 모델을 적용했습니다[cite: 8, 9]. 적군이나 의심 객체가 탐지될 경우 시스템이 즉각적으로 6초의 쿨다운을 가진 'RED' 경보를 발생시키며, 웹 UI 상의 카메라 화면에 실시간 Bounding Box를 오버레이하여 운용자에게 위협을 직관적으로 시각화합니다[cite: 5, 9].

**3. 작전 공백 제로(0): 예측 기반 자동 복귀 및 임무 교대 (Handoff)**
운용자의 개입 없이 작전이 지속되도록 고도화된 스케줄링을 구현했습니다. 시스템은 현재 기체의 임무 반경과 남은 거리를 계산하여 '안전한 HQ 복귀에 필요한 예상 배터리량(Safety Reserve 포함)'을 실시간으로 추적합니다[cite: 3, 4]. 
배터리가 임계치에 도달하면 해당 기체에 자동 복귀(RETURN_HOME) 명령을 내림과 동시에, 대기 중인 완충 상태의 새 기체를 동일한 임무 노드로 자동 출고시켜 순찰(Patrol) 임무를 끊김 없이 인수인계(Handoff)합니다[cite: 3].

**4. 동적 위험 구역을 회피하는 A* 경로 탐색**
자동 복귀 및 이동 시 단순히 직선으로 비행하는 것이 아니라, 전장 내에 설정된 위험 구역(Risk Zones)과 안전 마진(Clearance margin)을 고려하여 A* 알고리즘 기반으로 가장 안전하고 비용이 적은 경로를 실시간으로 탐색(Route Planning)하고 주행합니다.


# Route Planner Cost Function Math

## Candidate Selection

```math
\mathcal{A}_v = \{a \mid type(a)=v\}
```

```math
F(a) =
\begin{cases}
1, & \text{feasible} \\
0, & \text{rejected}
\end{cases}
```

```math
a^* = \arg\min_{a \in \mathcal{A}_v,\; F(a)=1} J(a)
```

## Total Cost

```math
J(a)
= C_{route}(a)
+ C_{risk}(a)
+ C_{battery}(a)
+ C_{comm}(a)
+ C_{condition}(a)
```

```math
C_{route}(a) = D(R_a)
```

```math
C_{risk}(a) = P_{risk}(R_a)
```

```math
C_{battery}(a)
= w_b \max(0,\; B_{safe} - B_{after}(a))
```

```math
C_{comm}(a)
= w_c \max(0,\; 1 - q_{comm}(a))
```

```math
C_{condition}(a)
= P_{state}(s_a)
```

```math
w_b = 5.0,\quad w_c = 40.0,\quad B_{safe}=35.0
```

## Route Distance

```math
R = (p_0, p_1, \dots, p_n)
```

```math
D(R) = \sum_{i=0}^{n-1} d_H(p_i, p_{i+1})
```

```math
d_H(p_i, p_j)
= 2R_E
\arcsin
\left(
\sqrt{
\sin^2\left(\frac{\Delta\phi}{2}\right)
+ \cos\phi_i\cos\phi_j\sin^2\left(\frac{\Delta\lambda}{2}\right)
}
\right)
```

```math
R_E = 6371.0088\;km
```

## Graph Route Distance

```math
s = snap(p_0)
```

```math
E_R = (e_1, e_2, \dots, e_m)
```

```math
D(R) = d_H(p_0, s) + \sum_{k=1}^{m} d(e_k)
```

```math
d(e) =
\begin{cases}
\frac{distance\_m(e)}{1000}, & distance\_m(e) > 0 \\
d_H(from(e), to(e)), & distance\_m(e) \le 0
\end{cases}
```

```math
UGV: domain(e)=land
```

```math
USV: domain(e)=water
```

## Risk Cost

```math
\mathcal{Z} = \{z_1, z_2, \dots, z_l\}
```

```math
\bar{r}_z = r_z + r_{margin}
```

```math
r_{margin}=3.0
```

```math
I_{node}(p) =
\begin{cases}
1, & \exists z \in \mathcal{Z}: d_H(p,c_z) \le \bar{r}_z \\
0, & \text{otherwise}
\end{cases}
```

```math
I_{seg}(p_i,p_j) =
\begin{cases}
1, & \exists z \in \mathcal{Z}: d_{\perp}(c_z,\overline{p_i p_j}) \le \bar{r}_z \\
0, & \text{otherwise}
\end{cases}
```

```math
X(p_i,p_j)
= I_{node}(p_i) \lor I_{node}(p_j) \lor I_{seg}(p_i,p_j)
```

```math
\exists i \in \{0,\dots,n-1\}: X(p_i,p_{i+1})=1
\quad \Rightarrow \quad F(a)=0
\quad
(allow\_risk\_crossing\_edges=False)
```

```math
C_{risk}(a)
= \lambda_r \sum_{i=0}^{n-1} X(p_i,p_{i+1})
\quad
(allow\_risk\_crossing\_edges=True)
```

```math
\lambda_r = risk\_crossing\_edge\_cost\_km
```

## Graph Search Risk Cost

```math
X_e = I_{node}(u) \lor I_{node}(w) \lor I_{seg}(u,w)
\quad
(e=(u,w))
```

```math
c_{search}(e) = d(e) + \lambda_r X_e
```

```math
S(R) = \sum_{e \in E_R} c_{search}(e)
```

```math
T(R) = \sum_{e \in E_R} d(e)
```

```math
C_{risk}^{graph}(R) = S(R) - T(R)
```

```math
C_{risk}^{graph}(R)
= \lambda_r \sum_{e \in E_R} X_e
```

## Battery Cost

```math
B_0(a) = battery(a)
```

```math
\rho_v =
\begin{cases}
0.18, & v=UAV \\
0.08, & v=UGV \\
0.06, & v=USV
\end{cases}
```

```math
m(s_a) =
\begin{cases}
1.00, & s_a=good \\
1.35, & s_a=caution \\
2.00, & s_a=critical \\
1.50, & s_a=unknown
\end{cases}
```

```math
\gamma_b = 1.0
```

```math
B_{used}(a)
= D(R_a)\rho_v m(s_a)\gamma_b
```

```math
B_{after}(a)
= B_0(a) - B_{used}(a)
```

```math
C_{battery}(a)
= w_b \max(0,\; B_{safe} - B_{after}(a))
```

```math
C_{battery}(a)
= 5.0 \max(0,\; 35.0 - B_{after}(a))
```

## Communication Cost

```math
q_{comm}(a) = comm\_quality(a)
```

```math
C_{comm}(a)
= w_c \max(0,\; 1 - q_{comm}(a))
```

```math
C_{comm}(a)
= 40.0 \max(0,\; 1 - q_{comm}(a))
```

## Condition Cost

```math
s_a = device\_state(a)
```

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

```math
s_a=disabled \Rightarrow F(a)=0
```

## Feasibility Constraints

```math
B_0(a) > B_{start,min}
```

```math
B_{start,min}=5.0
```

```math
B_{after}(a) \ge B_{arrival,min}
```

```math
B_{arrival,min}=3.0
```

```math
I_{node}(p_n)=0
```

```math
\sum_{i=0}^{n-1} X(p_i,p_{i+1}) = 0
\quad
(allow\_risk\_crossing\_edges=False)
```

## Expanded Default Cost

```math
J(a)
= D(R_a)
+ C_{risk}(a)
+ 5.0 \max(0,\; 35.0 - B_{after}(a))
+ 40.0 \max(0,\; 1 - q_{comm}(a))
+ P_{state}(s_a)
```

```math
B_{after}(a)
= B_0(a) - D(R_a)\rho_v m(s_a)\gamma_b
```

```math
J(a)
= D(R_a)
+ C_{risk}(a)
+ 5.0
\max\left(
0,\;
35.0 -
\left[
B_0(a) - D(R_a)\rho_v m(s_a)\gamma_b
\right]
\right)
+ 40.0 \max(0,\; 1 - q_{comm}(a))
+ P_{state}(s_a)
```
