"""관련 개념 페이지들: 전자기 기초, 정류, 아라고의 원판, 자기회로, 제어 기초, 기호·단위."""
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from scipy.integrate import solve_ivp
from scipy import signal

from core.units import to_rpm
from ui import realtime
from ui.plots import info_metric, style
from ui.tabs.dc.tab_principle import torque_ripple_section

MU0 = 4e-7 * np.pi


# --------------------------------------------------------------------------
# 1. 전자기 기초
# --------------------------------------------------------------------------
def _force_figure(b_dir, i_dir):
    """자계 속 도체 단면: B 방향(→/←), 전류 방향(⊙/⊗), 힘 방향."""
    fig = go.Figure()
    for y in (-0.6, -0.2, 0.2, 0.6):
        x0, x1 = (-1.2, 1.2) if b_dir > 0 else (1.2, -1.2)
        fig.add_annotation(x=x1, y=y, ax=x0, ay=y, xref="x", yref="y", axref="x", ayref="y",
                           arrowhead=2, arrowwidth=1.5, arrowcolor="#7b52c7", showarrow=True)
    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers",
                             marker=dict(size=46, color="#c77d3a", line=dict(color="#7a4a1f", width=2),
                                         symbol="circle-dot" if i_dir > 0 else "circle-x")))
    f = b_dir * i_dir          # I(±z) × B(±x) = ±y
    fig.add_annotation(x=0, y=0.95 * f, ax=0, ay=0.25 * f, xref="x", yref="y", axref="x",
                       ayref="y", arrowhead=2, arrowwidth=4, arrowcolor="#2a9d3a", showarrow=True)
    fig.add_annotation(x=0.32, y=0.85 * f, text="<b>F</b>", showarrow=False,
                       font=dict(color="#2a9d3a", size=16))
    fig.add_annotation(x=-1.05, y=0.82, text="<b>B</b>", showarrow=False,
                       font=dict(color="#7b52c7", size=15))
    fig.add_annotation(x=0.45, y=-0.15, text="I " + ("⊙ (나옴)" if i_dir > 0 else "⊗ (들어감)"),
                       showarrow=False, font=dict(size=13))
    fig.update_xaxes(range=[-1.3, 1.3], visible=False)
    fig.update_yaxes(range=[-1.1, 1.1], visible=False, scaleanchor="x")
    fig.update_layout(height=300, showlegend=False, plot_bgcolor="white",
                      margin=dict(l=5, r=5, t=5, b=5))
    return fig


def em_basics():
    st.title("🧭 전자기 기초: 힘과 기전력")
    st.markdown("""
전동기는 두 가지 현상이 **동시에** 일어나는 기계입니다.

| 현상 | 식 | 법칙 | 전동기에서의 의미 |
|---|---|---|---|
| 자계 속 **전류**가 흐르는 도체는 **힘**을 받는다 | F = B·I·L | 플레밍 **왼손** (전동기) | 토크 Te = Kφ·Ia |
| 자계 속에서 **움직이는** 도체에는 **기전력**이 생긴다 | e = B·L·v | 플레밍 **오른손** (발전기) | 역기전력 E = Kφ·ω |
""")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("**방향 확인** (F = I L × B)")
        b_dir = 1 if st.radio("자계 B 방향", ["→ 오른쪽", "← 왼쪽"], horizontal=True,
                              key="em_b").startswith("→") else -1
        i_dir = 1 if st.radio("전류 I 방향", ["⊙ 지면에서 나옴", "⊗ 지면으로 들어감"],
                              horizontal=True, key="em_i").startswith("⊙") else -1
        st.plotly_chart(_force_figure(b_dir, i_dir), width="stretch",
                        config={"staticPlot": True})
        st.caption("자계나 전류 중 하나만 뒤집으면 힘이 반대가 되고, 둘 다 뒤집으면 그대로입니다. "
                   "DC 전동기의 역회전은 그래서 **전기자 전압이나 계자 중 하나만** 뒤집습니다.")
    with c2:
        st.markdown("**도체 하나 계산기**")
        B = st.slider("자속 밀도 B [T]", 0.1, 1.5, 0.8, 0.05, key="em_B")
        I = st.slider("전류 I [A]", 0.0, 50.0, 20.0, 1.0, key="em_I")
        L = st.slider("도체 유효 길이 L [m]", 0.05, 0.5, 0.2, 0.01, key="em_L")
        v = st.slider("도체 속도 v [m/s]", 0.0, 30.0, 10.0, 0.5, key="em_v")
        F, e = B * I * L, B * L * v
        k = st.columns(2)
        info_metric(k[0], "힘 F = BIL", f"{F:.2f} N")
        info_metric(k[1], "기전력 e = BLv", f"{e:.2f} V")
        info_metric(k[0], "기계 출력 F·v", f"{F * v:.1f} W")
        info_metric(k[1], "전기 입력 e·I", f"{e * I:.1f} W", "F·v 와 같다 (에너지 보존)")

    st.divider()
    st.markdown("#### 도체가 여러 개면 → Kφ")
    st.markdown("반지름 r 인 회전자에 유효 도체가 Z 개 있고 전기자 전류가 a 개의 병렬 경로로 나뉘면 "
                "(정류자가 모든 도체의 토크 방향을 같게 정리):")
    st.latex(r"T = Z\,(B\,I_c\,L)\,r = \underbrace{\frac{Z}{a} B L r}_{K\phi}\, I_a,\qquad"
             r"E = \frac{Z}{a}\,(B\,L\,r\omega) = K\phi\,\omega\qquad (I_c = I_a / a)")
    c = st.columns(4)
    Z = c[0].number_input("유효 도체 수 Z", 10, 2000, 240, 10, key="em_Z")
    r = c[1].number_input("회전자 반지름 r [m]", 0.01, 1.0, 0.08, 0.01, key="em_r")
    a = c[2].number_input("병렬 회로 수 a", 2, 16, 2, 2, key="em_a",
                          help="전기자 전류가 a 개의 병렬 경로로 나뉨 (중권: a = 극수, 파권: a = 2)")
    w = c[3].number_input("회전 속도 [rpm]", 0.0, 6000.0, 1000.0, 50.0, key="em_w")
    # 평균 자속 밀도 B 가 극 아래 일부에만 있으므로 단순화: 모든 도체가 평균 B 를 받는다고 봄
    kphi = (Z / a) * B * L * r
    info_cols = st.columns(3)
    info_metric(info_cols[0], "Kφ = (Z/a)·B·L·r", f"{kphi:.3f} V·s/rad")
    info_metric(info_cols[1], "E = Kφ·ω", f"{kphi * w * 2 * np.pi / 60:.1f} V")
    info_metric(info_cols[2], f"Ia = a·I = {I * a:.0f} A 일 때 토크", f"{kphi * I * a:.1f} N·m",
                "도체 하나의 전류 Ic = Ia / a = 위의 I")
    st.caption("교재 식 E = (P·Z/(60·a))·φ·n 과 같은 내용입니다 (φ: 극당 자속, n: rpm). "
               "여기서는 모든 도체가 평균 자속 밀도 B 아래 있다고 단순화했습니다.")


# --------------------------------------------------------------------------
# 2. 정류 원리
# --------------------------------------------------------------------------
def _commutation(lam, eps, n=400):
    """정류 중 코일 전류 (정규화: 전류/I, 시간/Tc).
    L·di/dt = Rb/x·(I − i) − Rb/(1−x)·(I + i) − e_c   (x = t/Tc, 브러시 접촉 저항 ∝ 1/접촉면적)
    lam = L/(Rb·Tc) (리액턴스 전압의 크기), eps = e_c/(Rb·I) (보극이 만드는 정류 기전력)."""
    def f(x, y):
        i = y[0]
        return [((1 - i) / x - (1 + i) / (1 - x) - eps) / max(lam, 1e-9)]
    x0, x1 = 1e-4, 1 - 1e-4
    if lam < 1e-6:
        x = np.linspace(x0, x1, n)
        # L = 0: 대수식 (1−i)/x − (1+i)/(1−x) − eps = 0 → 저항 정류 (eps = 0 이면 직선)
        i = 1 - 2 * x - eps * x * (1 - x)
        return x, i
    sol = solve_ivp(f, (x0, x1), [1.0], method="Radau", t_eval=np.linspace(x0, x1, n),
                    rtol=1e-7, atol=1e-9)
    return sol.t, sol.y[0]


def commutation():
    st.title("🔁 정류 원리")
    st.markdown("""
전기자 코일이 **중성축**을 지날 때, 브러시가 이웃한 두 정류자편에 걸치면서 그 코일의 전류가
**+I → −I 로 뒤집힙니다.** 이 짧은 시간 Tc 동안의 과정을 **정류(commutation)** 라고 합니다.

- 코일에 인덕턴스가 없으면 전류는 브러시 접촉 면적 비율에 따라 **직선으로** 바뀝니다 (저항 정류).
- 실제 코일은 인덕턴스 L 이 있어 전류 변화를 막는 **리액턴스 전압 L·di/dt** 가 생깁니다.
  그래서 전류가 늦게 바뀌고(**부족 정류**), 브러시가 떨어지는 순간 남은 전류가 **불꽃(아크)** 으로 끊깁니다.
- **보극**은 중성축에 작은 자계를 만들어 정류 중인 코일에 리액턴스 전압과 반대인
  **정류 기전력**을 넣어 줍니다. 그래서 전류가 제때 뒤집힙니다.
""")
    c = st.columns(2)
    lam = c[0].slider("리액턴스 크기 λ = L/(Rb·Tc)", 0.0, 2.0, 0.6, 0.05, key="cm_lam",
                      help="코일 인덕턴스가 크거나 속도가 빨라 Tc 가 짧을수록 커집니다.")
    eps = c[1].slider("보극 정류 기전력 ε = e_c/(Rb·I)", 0.0, 4.0, 0.0, 0.1, key="cm_eps",
                      help="0 이면 보극 없음. 너무 크면 과정류.")
    x, i = _commutation(lam, eps)
    x_ref, i_ref = _commutation(0.0, 0.0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_ref, y=i_ref, name="이상적 (L = 0, 직선 정류)",
                             line=dict(color="#adb5bd", dash="dash")))
    fig.add_trace(go.Scatter(x=x, y=i, name="코일 전류", line=dict(color="#e76f51", width=3)))
    fig.add_hline(y=-1, line=dict(color="#bbb", dash="dot"))
    style(fig, 360, xaxis_title="정류 진행 t / Tc", yaxis_title="코일 전류 i / I [p.u.]")
    st.plotly_chart(fig, width="stretch")
    # 브러시 접촉면의 전류 밀도 (직선 정류일 때 = 1). 끝쪽이 크면 부족 정류, 앞쪽이 크면 과정류.
    trail = float(np.mean(((1 + i) / (1 - x) / 2)[(x > 0.85) & (x < 0.97)]))
    lead = float(np.mean(((1 - i) / x / 2)[(x > 0.03) & (x < 0.15)]))
    k = st.columns(3)
    info_metric(k[0], "브러시 뒤쪽 끝 전류 밀도", f"{trail:.2f} 배", "직선 정류 = 1.00")
    info_metric(k[1], "브러시 앞쪽 끝 전류 밀도", f"{lead:.2f} 배", "직선 정류 = 1.00")
    state, why = (("부족 정류", "브러시 뒤쪽 끝에서 불꽃") if trail > 1.4 else
                  ("과정류", "브러시 앞쪽 끝에서 불꽃") if lead > 1.4 else ("양호", "불꽃 거의 없음"))
    info_metric(k[2], "판정", state, why)
    st.caption("정류가 늦으면 브러시가 정류자편에서 떨어지기 직전, 좁아진 접촉면에 전류가 몰립니다. "
               "그곳의 전류 밀도와 전압이 커지면서 아크(불꽃)가 생깁니다. 보극 ε 를 올려 두 값을 1 에 가깝게 만들어 보세요.")
    st.caption("모델: 브러시 접촉 저항이 접촉 면적에 반비례한다고 보고 정류 코일 회로를 푼 결과입니다 "
               "(L·di/dt = Rb/x·(I − i) − Rb/(1−x)·(I + i) − e_c). 이 시뮬레이터의 전동기 모델은 "
               "'정류가 이상적'이라고 가정합니다.")
    st.divider()
    torque_ripple_section()


# --------------------------------------------------------------------------
# 3. 자기회로와 Kφ
# --------------------------------------------------------------------------
def magnetic():
    st.title("🧲 자기회로와 Kφ")
    st.markdown("""
계자 권선의 기자력 **N·If** 가 자속 φ 를 만들고, 자속은 계철 → 주극 → **공극** → 전기자 → 공극 → 주극으로 돕니다.
철심의 투자율은 공기보다 수천 배 크므로, **기자력 대부분이 공극에 걸립니다**. 공극은 선형이므로
철심이 포화되기 전까지는 Kφ ∝ If 로 보아도 됩니다 (이 시뮬레이터의 **선형 자기회로 가정**).
""")
    st.latex(r"N I_f = \phi\,\mathcal{R} \approx \phi\,\frac{2g}{\mu_0 A}"
             r"\;\Rightarrow\; B_g = \frac{\mu_0 N I_f}{2g},\qquad K\phi = L_{af} I_f")
    c = st.columns(4)
    N = c[0].number_input("계자 권수 N (극당)", 10, 20000, 1200, 50, key="mg_N")
    If = c[1].number_input("계자 전류 If [A]", 0.0, 20.0, 1.0, 0.1, key="mg_If")
    g = c[2].number_input("공극 길이 g [mm]", 0.2, 10.0, 1.5, 0.1, key="mg_g") * 1e-3
    A = c[3].number_input("극 면적 A [cm²]", 10.0, 2000.0, 150.0, 10.0, key="mg_A") * 1e-4
    Bg = MU0 * N * If / (2 * g)
    k = st.columns(3)
    info_metric(k[0], "공극 자속 밀도 Bg", f"{Bg:.3f} T")
    info_metric(k[1], "극당 자속 φ = Bg·A", f"{Bg * A * 1e3:.2f} mWb")
    info_metric(k[2], "필요 기자력 N·If", f"{N * If:.0f} A·turn")
    if Bg > 1.5:
        st.warning("공극 자속 밀도가 1.5 T 를 넘습니다. 실제 철심(특히 극편과 전기자 치)은 "
                   "포화되어 선형 계산보다 자속이 훨씬 적게 나옵니다.")

    st.divider()
    st.markdown("#### 선형 모델 vs 실제 자화 곡선 (포화)")
    st.caption("실제 자화 곡선을 프뢰리히(Froelich) 식 Kφ = Kφ_max·If / (If_k + If) 로 근사합니다. "
               "원점 기울기는 선형 모델과 같게 Laf 로 맞췄습니다.")
    c = st.columns(3)
    Laf = c[0].number_input("Laf [H]", 0.1, 10.0, 1.8, 0.1, key="mg_Laf")
    If_r = c[1].number_input("정격 계자 전류 [A]", 0.1, 20.0, 1.0, 0.1, key="mg_Ifr")
    sat = c[2].slider("포화 정도 (정격점에서 선형 대비 감소율)", 0.0, 0.4, 0.15, 0.01, key="mg_sat")
    # 정격점에서 Kφ_sat / Kφ_lin = 1 − sat 이 되도록 If_k 결정:  If_k/(If_k + If_r) = 1 − sat
    If_k = (1 - sat) * If_r / max(sat, 1e-6)
    Kmax = Laf * If_k
    x = np.linspace(0, 2.5 * If_r, 300)
    lin = Laf * x
    satc = Kmax * x / (If_k + x) if sat > 0 else lin
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=lin, name="선형 모델 Kφ = Laf·If",
                             line=dict(color="#adb5bd", dash="dash")))
    fig.add_trace(go.Scatter(x=x, y=satc, name="포화 고려 (근사)", line=dict(color="#264653", width=3)))
    fig.add_vline(x=If_r, line=dict(color="#e76f51", dash="dot"), annotation_text="정격 If")
    style(fig, 360, xaxis_title="계자 전류 If [A]", yaxis_title="Kφ [V·s/rad]")
    st.plotly_chart(fig, width="stretch")
    st.markdown(f"""
- 정격점에서 선형 모델은 Kφ 를 **{sat * 100:.0f} %** 크게 봅니다. 그만큼 무부하 속도 V/Kφ 를 작게 예측합니다.
- 정격보다 약한 계자(**계자 약화**)에서는 곡선이 거의 직선이라 선형 모델이 잘 맞습니다.
- **직권 전동기**는 Kφ = Ms·Ia 라서 큰 전류에서 포화가 특히 중요합니다. 실제 기동 토크는 Ia² 보다 덜 커집니다.
- **전기자 반작용**: 전기자 전류가 만드는 자계가 주자속을 비틀고 (극편 한쪽은 강해지고 반대쪽은 포화) 중성축을 옮깁니다.
  보극과 보상 권선이 이를 줄입니다. 이 시뮬레이터에서는 무시합니다.
""")


# --------------------------------------------------------------------------
# 4. 제어 기초
# --------------------------------------------------------------------------
def control_basics():
    st.title("🎛️ 제어 기초: PI 제어와 대역폭")
    st.markdown("""
전기자 회로는 **1차 지연** 플랜트 1/(La·s + Ra) 입니다 (역기전력은 피드포워드로 상쇄했다고 봄).
PI 제어기 Kp + Ki/s 의 영점 Ki/Kp 를 플랜트 극 Ra/La 에 맞추면 둘이 상쇄되어,
폐루프가 **대역폭 ωc 인 깔끔한 1차 응답**이 됩니다.
""")
    st.latex(r"C(s)G(s) = \frac{K_p s + K_i}{s}\cdot\frac{1}{L s + R}"
             r"\;\xrightarrow{K_p = \omega_c \hat L,\; K_i = \omega_c \hat R}\;"
             r"\frac{\omega_c}{s}\quad(\hat L = L,\ \hat R = R \text{ 일 때})"
             r"\;\Rightarrow\; \frac{I}{I^*} = \frac{\omega_c}{s + \omega_c}")
    c = st.columns(4)
    R = c[0].number_input("실제 R [Ω]", 0.01, 100.0, 0.5, 0.05, key="cb_R")
    L = c[1].number_input("실제 L [mH]", 0.1, 1000.0, 10.0, 1.0, key="cb_L") * 1e-3
    wc = c[2].number_input("목표 대역폭 ωc [rad/s]", 10.0, 1e5, 1000.0, 100.0, key="cb_wc")
    err = c[3].slider("추정한 L̂ / 실제 L", 0.3, 3.0, 1.0, 0.05, key="cb_err",
                      help="파라미터를 틀리게 알고 게인을 정하면 어떻게 되는지")
    Kp, Ki = wc * L * err, wc * R * err
    t = np.linspace(0, 8 / wc, 600)
    sys = signal.TransferFunction([Kp, Ki], [L, R + Kp, Ki])
    _, y = signal.step(sys, T=t)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t * 1e3, y=1 - np.exp(-wc * t), name="목표: 1 − e^(−ωc t)",
                             line=dict(color="#adb5bd", dash="dash")))
    fig.add_trace(go.Scatter(x=t * 1e3, y=y, name="실제 폐루프 응답", line=dict(color="#e76f51", width=3)))
    style(fig, 360, xaxis_title="시간 [ms]", yaxis_title="I / I* [p.u.]")
    st.plotly_chart(fig, width="stretch")
    k = st.columns(4)
    info_metric(k[0], "Kp", f"{Kp:.4g} V/A")
    info_metric(k[1], "Ki", f"{Ki:.4g} V/(A·s)")
    j63 = np.argmax(y >= 0.632) if np.any(y >= 0.632) else None
    info_metric(k[2], "63 % 도달 시간", f"{t[j63] * 1e3:.2f} ms" if j63 else "—",
                f"목표 {1e3 / wc:.2f} ms (= 1/ωc)")
    info_metric(k[3], "최대 오버슈트", f"{max(0.0, (np.max(y) - 1) * 100):.1f} %")
    st.markdown("""
- **L̂ = L** 이면 목표 곡선과 정확히 겹칩니다 (극–영점 상쇄).
- L̂ 를 크게 잡으면 Kp 가 커져 응답이 빨라지고, 작게 잡으면 느려집니다. 영점과 극이 어긋나서 느린 꼬리가 남기도 합니다.
- **속도 루프**는 전류 루프를 '빠른 1' 로 보고 설계하므로 대역폭을 전류 루프의 **1/5 ~ 1/10 이하**로 둡니다.
- 실제 출력에는 한계(전압·전류 제한)가 있습니다. 포화 중에 적분기가 계속 쌓이는 것을 막는 것이 **안티와인드업**입니다.
  직류 전동기 페이지 ④ 제어 탭의 실시간 실험에서 직접 켜고 꺼 보세요.
""")


# --------------------------------------------------------------------------
# 5. 아라고의 원판
# --------------------------------------------------------------------------
# 재질: (도전율 σ [S/m], 표시 색) — ui/realtime/arago_engine.js 와 같은 값
ARAGO_MATERIALS = {
    "구리": (5.8e7, "#c77d3a"), "알루미늄": (3.5e7, "#7b8794"), "황동": (1.5e7, "#d4a93c"),
    "스테인리스강": (1.4e6, "#264653"), "홈 판 구리 (방사형 홈)": (5.8e7 * 0.12, "#e76f51"),
}


def arago_torque(dw, sigma, B=0.25 * math.exp(-4 / 6), t=0.002, a=0.02, rm=0.07):
    """와전류 토크 [N·m]: 자석 2개, 얇은 도체판 모델 T = 2·rm·σ·t·a²·B²·Δv / (1 + (Δv/vc)²)."""
    if sigma <= 0:
        return np.zeros_like(np.asarray(dw, dtype=float))
    dv = rm * np.asarray(dw, dtype=float)
    vc = 2 / (MU0 * sigma * t)
    return 2 * rm * sigma * t * a * a * B * B * dv / (1 + (dv / vc) ** 2)


def arago():
    st.title("🧲 아라고의 원판 (Arago's disk)")
    st.markdown("""
1824년 아라고(F. Arago)는 **자석에 붙지 않는 구리 원판**이 그 아래(또는 위)에서 돌리는 자석을 **따라 돈다**는 것을 발견했습니다.
나중에 패러데이가 전자기 유도로 설명했고, 이 원리가 **유도전동기**의 출발점이 되었습니다.
아래 시뮬레이션은 계산이 브라우저에서 실시간으로 돌아가므로 값을 바꾸면 바로 반응합니다.
""")
    realtime.render(realtime.arago_html(), height=820)
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("#### 왜 따라 도는가")
        st.markdown("""
1. 자석이 움직이면 그 아래 원판 부분을 지나는 **자속이 변합니다** (자석 앞쪽은 늘고, 뒤쪽은 줄어듦).
2. 자속이 변하는 도체에는 **기전력**이 생기고, 원판 안에 소용돌이 모양의 **와전류(맴돌이 전류)** 가 흐릅니다 (패러데이 법칙).
3. 와전류는 자속 변화를 **방해하는 방향**으로 흐릅니다 (렌츠 법칙). 그 결과 원판은 자석과의 **상대 운동을 줄이는 쪽**,
   즉 자석이 움직이는 방향으로 힘을 받습니다 (F = I·L × B).
4. 원판이 자석과 **같은 속도가 되면** 상대 운동이 없어 자속 변화·와전류·토크가 모두 0 이 됩니다.
   그래서 마찰이나 부하가 있으면 원판은 **항상 자석보다 조금 느리게** 돕니다 → **슬립**.
""")
    with c2:
        st.markdown("#### 계산 모델")
        st.latex(r"\Delta v = r_m(\omega_m - \omega_d),\quad J \approx \sigma\,\Delta v\,B")
        st.latex(r"T = 2 r_m\,\frac{\sigma t a^2 B^2\,\Delta v}{1 + (\Delta v / v_c)^2},\quad v_c = \frac{2}{\mu_0 \sigma t}")
        st.latex(r"J_d \frac{d\omega_d}{dt} = T - T_{제동} - b\,\omega_d")
        st.caption("σ: 도전율, t: 원판 두께, a: 자석 한 변, B: 자속 밀도(공극이 커지면 감소), r_m: 자석 위치 반지름. "
                   "속도 차가 작으면 토크가 속도 차에 비례하고, v_c 근처에서 최대가 됩니다 (와전류가 만드는 자계가 원래 자계를 밀어냄).")

    st.markdown("#### 재질에 따른 토크–슬립 곡선 (자석 60 rpm, 공극 4 mm)")
    wm = 2 * np.pi
    wd = np.linspace(-0.3 * wm, wm, 300)
    fig = go.Figure()
    for name, (sig, col) in ARAGO_MATERIALS.items():
        fig.add_trace(go.Scatter(x=wd * 60 / (2 * np.pi), y=arago_torque(wm - wd, sig) * 1000, name=name,
                                 line=dict(color=col, width=2.5)))
    fig.add_vline(x=60, line=dict(color="#999", dash="dash"), annotation_text="자석 속도 (슬립 0)")
    style(fig, 340, xaxis_title="원판 속도 [rpm]", yaxis_title="와전류 토크 [mN·m]", hovermode="closest")
    st.plotly_chart(fig, width="stretch")
    st.markdown("#### 상대 속도를 크게 했을 때: 최대 토크가 있다 (유도전동기 토크–슬립 곡선과 같은 꼴)")
    dn = np.linspace(0, 6000, 400)
    fig2 = go.Figure()
    for name, (sig, col) in ARAGO_MATERIALS.items():
        if "스테인리스" in name:
            continue
        T = arago_torque(dn * 2 * np.pi / 60, sig) * 1000
        fig2.add_trace(go.Scatter(x=dn, y=T, name=name, line=dict(color=col, width=2.5)))
        j = int(np.argmax(T))
        if 0 < j < len(dn) - 1:
            fig2.add_trace(go.Scatter(x=[dn[j]], y=[T[j]], mode="markers+text", text=[f" 최대 {dn[j]:.0f} rpm"],
                                      textposition="top right", marker=dict(color=col, size=9), showlegend=False))
    style(fig2, 320, xaxis_title="자석과 원판의 속도 차 Δn [rpm]", yaxis_title="와전류 토크 [mN·m]", hovermode="closest")
    st.plotly_chart(fig2, width="stretch")
    st.caption("속도 차가 아주 커지면 와전류가 만드는 자계가 자석 자계를 밀어내 토크가 오히려 줄어듭니다. "
               "최대 토크가 나는 속도 차는 v_c = 2/(μ0·σ·t) 에서 정해지며 도전율·두께가 클수록 작아집니다 "
               "(유도전동기에서 회전자 저항이 작을수록 최대 토크 슬립이 작아지는 것과 같음). 시뮬레이션에서 자석을 2000~3000 rpm 으로 돌려 보세요.")
    st.caption("도전율이 큰 재질일수록 같은 슬립에서 토크가 커서 자석을 더 바짝 따라갑니다. "
               "방사형 홈을 내면 와전류가 흐를 길이 끊겨 토크가 크게 줄어듭니다 (전동기 철심을 얇게 쌓는 이유와 같음). "
               "플라스틱 같은 부도체는 전류가 흐르지 않아 전혀 돌지 않습니다.")

    st.markdown("#### 유도전동기와 비교")
    st.markdown("""
| 아라고의 원판 | 유도전동기 |
|---|---|
| 손으로 돌리는 **자석** | 3상 고정자 권선이 만드는 **회전자계** (전기로 자석을 돌리는 셈) |
| 구리·알루미늄 **원판** | 농형 **회전자** (알루미늄·구리 도체 막대 + 단락 링) |
| 원판의 **와전류** | 회전자 도체에 **유도되는 전류** |
| 원판이 자석보다 느림 | 회전자가 동기속도보다 느림 → **슬립** s = (ns − n)/ns |
| 토크–슬립 곡선: 비례 → 최대 → 감소 | 토크–슬립 곡선: 비례 → **최대 토크** → 감소 |
| 홈 판은 와전류가 줄어 약함 | 회전자 저항이 크면 최대 토크 슬립이 커짐 |
""")
    st.markdown("#### 생활 속 응용")
    st.markdown("""
- **와전류 제동기 (리타더)**: 버스·트럭·열차, 롤러코스터. 자석(또는 전자석) 사이로 금속판이 지나가면 마찰 없이 감속합니다.
  시뮬레이션에서 자석 속도를 0 으로 두고 **'원판 손으로 돌리기'** 를 눌러 보세요.
- **유도형 전력량계** (옛날 회전 원판 계량기): 알루미늄 원판이 소비 전력에 비례해 돕니다.
- **와전류식 속도계**, **인덕션 레인지**(와전류로 냄비를 데움), **금속 탐지기**.
""")
    with st.expander("해 볼 실험", expanded=True):
        st.markdown("""
1. **따라 돌기**: 처음부터 → 원판이 서서히 자석을 따라 돌다가 자석보다 조금 느린 속도에서 멈춥니다 (슬립 몇 %).
2. **재질 바꾸기**: 구리 → 알루미늄 → 황동 → 스테인리스강 → 플라스틱. 슬립이 어떻게 변하나요?
   알루미늄은 도전율이 구리보다 작지만 훨씬 가벼워서 더 빨리 따라붙습니다.
3. **홈 판 구리**: 와전류 길이 끊기면 토크가 약해집니다.
4. **공극 넓히기**: 자석을 멀리 하면 B 가 작아져 토크가 B² 에 비례해 크게 줄어듭니다.
5. **제동 토크(부하) 걸기**: 부하가 클수록 슬립이 커지고, 토크–속도 곡선의 최대값을 넘으면 원판이 멈춥니다 (유도전동기의 스톨).
6. **역회전**: 자석 속도를 음수로 → 원판도 반대로 돕니다.
7. **최대 토크 넘기기**: 자석을 2000 rpm 이상으로 돌리고 제동 토크를 크게 걸면, 토크–속도 곡선의 최대점을 넘어 원판이 멈춰 버립니다.
8. **와전류 제동**: 자석 속도 0 → '원판 손으로 돌리기'. '자석 있음'을 끄고 같은 실험을 하면 마찰로만 천천히 멈춥니다.
""")


# --------------------------------------------------------------------------
# 6. 기호와 단위
# --------------------------------------------------------------------------
def symbols():
    st.title("📘 기호와 단위")
    rows = [
        ("V", "전기자(단자) 전압", "V"), ("Vf", "계자 전원 전압 (타여자)", "V"),
        ("Ia", "전기자 전류", "A"), ("If", "계자 전류", "A"), ("IL", "선전류 (전원 전류)", "A"),
        ("Ra, La", "전기자 저항, 인덕턴스", "Ω, H"), ("Rf, Lf", "분권/타여자 계자 저항, 인덕턴스", "Ω, H"),
        ("Rfx", "계자 조정 저항", "Ω"), ("Rs, Ls", "직권 계자 저항, 인덕턴스", "Ω, H"),
        ("Laf", "계자–전기자 결합계수 (Kφ = Laf·If)", "H = V·s/A"),
        ("Ms", "직권 결합계수 (Kφ = Ms·Ia)", "H"),
        ("Kφ", "토크 상수 = 역기전력 상수", "V·s/rad = N·m/A"),
        ("E", "역기전력 = Kφ·ω", "V"), ("Te", "전자기 토크 = Kφ·Ia", "N·m"),
        ("TL", "부하 토크", "N·m"), ("ω", "각속도", "rad/s (화면은 rpm)"),
        ("J", "관성 모멘트", "kg·m²"), ("B", "점성 마찰 계수", "N·m·s/rad"),
        ("ωci, ωcs", "전류·속도 루프 대역폭", "rad/s"), ("Kp, Ki", "PI 비례·적분 게인", "단위는 루프마다 다름"),
        ("Ts", "제어 주기", "s"), ("I_lim", "전류 제한값", "A"),
    ]
    st.dataframe([{"기호": a, "의미": b, "단위": c} for a, b, c in rows], hide_index=True,
                 width="stretch")
    st.markdown("#### 자주 쓰는 변환")
    st.latex(r"n\,[\text{rpm}] = \omega\,[\text{rad/s}]\times\frac{60}{2\pi}\approx 9.549\,\omega,"
             r"\qquad P = T\omega,\qquad 1\ \text{HP} = 746\ \text{W}")
    st.caption(f"예: 1000 rpm = {1000 / 9.5493:.2f} rad/s, 100 rad/s = {to_rpm(100.0):.1f} rpm")
