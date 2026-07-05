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
