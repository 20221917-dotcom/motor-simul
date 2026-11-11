"""강의 실습 1장: 전동기의 기본 원리."""
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lectures import ch1
from ui.lecture_draw import blocks
from ui.pages.lecture_common import check, link, lstyle, ref
from ui.plots import info_metric

RPM = 60 / (2 * math.pi)


@st.cache_data(max_entries=64, show_spinner=False)
def _force_curves(N, i):
    xg = np.linspace(0.2, 5.0, 60)
    F = [ch1.gap_force(i, x * 1e-3, N=N) for x in xg]
    return xg, F, ch1.gap_force_linear(i, xg * 1e-3, N=N), ch1.lambda_i(i, N=N, g=xg * 1e-3) / i


@st.cache_data(max_entries=64, show_spinner=False)
def _paths(i0, x1, x2):
    return ch1.linear_machine_paths(i0, x1 * 1e-3, min(x2, x1 - 0.1) * 1e-3)


@st.cache_data(max_entries=64, show_spinner=False)
def _rel_sweep(delta):
    ws = 2 * math.pi * 10
    return [ch1.reluctance_avg(10.0, ws, r * ws, math.radians(delta), 0.01, cycles=60) for r in np.linspace(0, 2, 81)]


@st.cache_data(max_entries=64, show_spinner=False)
def _dbl_sweep(ws, wr, th0):
    return [ch1.double_excited_avg(1, 1, 1, ws, wr, w, math.radians(th0), T=30, n=60000) for w in np.linspace(0, 40, 161)]


@st.cache_data(max_entries=64, show_spinner=False)
def _startup(kind, V, T0, J):
    return ch1.startup(kind, V, 0.4058, 0.5, T0, 1000 / RPM, J)


@st.fragment
def _principle():
    ref("1.1 전동기의 동작 원리 — 로렌츠의 힘 F = I·l·B, 두 자석의 상호 작용 (자석–자석, 자석–자성체), 직류·교류(동기·유도) 전동기의 자석")
    st.markdown("##### ① 로렌츠의 힘: 자계 안의 전류가 흐르는 도체")
    c = st.columns(4)
    B = c[0].slider("자속 밀도 B [T]", 0.1, 2.0, 0.8, 0.05, key="l11_B")
    I = c[1].slider("전류 I [A]", 0.0, 50.0, 10.0, 1.0, key="l11_I")
    L = c[2].slider("도체 길이 l [m]", 0.05, 0.5, 0.2, 0.01, key="l11_l")
    r = c[3].slider("회전 반지름 r [m]", 0.01, 0.2, 0.05, 0.01, key="l11_r")
    c = st.columns(3)
    info_metric(c[0], "힘 F = I·l·B", f"{I * L * B:.2f} N")
    info_metric(c[1], "토크 T = r × F (도체 1개)", f"{I * L * B * r:.3f} N·m")
    info_metric(c[2], "힘의 방향", "플레밍 왼손 법칙", "자계 ⊥ 전류 ⊥ 힘")
    st.markdown("##### ② 두 자석 사이의 회전력: 회전자 축이 고정자 자계에서 θ 만큼 벗어나 있을 때")
    c = st.columns([1, 2, 2])
    th = c[0].slider("회전자 각 θ [°]", -180, 180, 60, 5, key="l11_th")
    kind = c[0].radio("회전자", ["자석–자석", "자석–자성체 (릴럭턴스)"], key="l11_k")
    x = np.linspace(-180, 180, 361)
    T = ch1.magnet_torque(np.radians(x), "자석–자석" if kind == "자석–자석" else "r")
    Tnow = float(ch1.magnet_torque(math.radians(th), "자석–자석" if kind == "자석–자석" else "r"))
    fig = go.Figure(go.Scatter(x=x, y=T, name="복원 토크"))
    fig.add_trace(go.Scatter(x=[th], y=[Tnow], mode="markers", marker=dict(size=12, color="#d62828"), name="현재"))
    fig.update_xaxes(title_text="θ [°]", dtick=45); fig.update_yaxes(title_text="토크 (단위값, + = θ 를 줄이는 쪽)")
    c[1].plotly_chart(lstyle(fig, height=300), width="stretch", key="l11_T")
    pol = go.Figure()
    pol.add_trace(go.Scatterpolar(r=[0, 1], theta=[0, 0], mode="lines+markers", line=dict(color="#1d4ed8", width=5), name="고정자 자계 (N→)"))
    if kind == "자석–자석":
        pol.add_trace(go.Scatterpolar(r=[0, 0.8], theta=[0, th], mode="lines+markers", line=dict(color="#d62828", width=5), name="회전자 자석 N"))
    else:
        pol.add_trace(go.Scatterpolar(r=[0.8, 0, 0.8], theta=[th, 0, th + 180], mode="lines", line=dict(color="#555", width=10), name="자성체 회전자 (돌극)"))
    pol.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20), polar=dict(radialaxis=dict(visible=False)), legend=dict(orientation="h", y=-0.1))
    c[2].plotly_chart(pol, width="stretch", key="l11_pol")
    check("자석–자석: θ = 90° 에서 토크 최대, 0° 에서 0 → 직류 전동기는 정류자로 두 자석을 항상 90° 로 유지",
          "자석–자성체: 토크가 sin2θ 로 작고 180° 마다 반복 (릴럭턴스 토크) → 회전자가 원통형이면 생기지 않음",
          "교류 전동기는 고정자 자석(회전자계)이 돌고 회전자 자석이 같은 속도로 따라 돎: 동기 = 회전자 자석이 직류, 유도 = 회전자 자석이 유도 전류")


@st.fragment
def _magnetic():
    ref("1.2.1 자기 에너지 — 기자력과 자속, λ-i 특성(선형·포화 영역), 인덕턴스, 자기 에너지와 코에너지")
    c = st.columns(4)
    N = c[0].slider("코일 권수 N", 50, 500, 200, 10, key="l1_N")
    g = c[1].slider("공극 길이 x [mm]", 0.1, 3.0, 1.0, 0.1, key="l1_g")
    imax = c[2].slider("코일 전류 i [A]", 0.5, 30.0, 8.0, 0.5, key="l1_i")
    Bs = c[3].slider("철심 포화 자속 밀도 Bs [T]", 0.8, 2.0, 1.6, 0.1, key="l1_Bs")
    kw = dict(N=N, Bs=Bs)
    i = np.linspace(0, 30, 400)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("λ-i 특성 (공극 길이별)", "인덕턴스 L = λ/i  와  증분 dλ/di"))
    for gg, col in ((g * 0.5, "#94a3b8"), (g, "#d62828"), (g * 2, "#1d4ed8")):
        lam = ch1.lambda_i(i, g=gg * 1e-3, **kw)
        fig.add_trace(go.Scatter(x=i, y=lam, name=f"x = {gg:.2g} mm", line=dict(color=col, width=3 if gg == g else 1.6)), 1, 1)
        if gg == g:
            L = np.where(i > 0, lam / np.maximum(i, 1e-9), np.nan)
            fig.add_trace(go.Scatter(x=i, y=L * 1e3, name="L = λ/i [mH]", line=dict(color=col)), 1, 2)
            fig.add_trace(go.Scatter(x=i, y=np.gradient(lam, i) * 1e3, name="dλ/di [mH]", line=dict(color=col, dash="dot")), 1, 2)
    W, Wc, ii, ll = ch1.energy_coenergy(imax, g=g * 1e-3, **kw)
    fig.add_trace(go.Scatter(x=np.r_[ii, 0], y=np.r_[ll, ll[-1]], fill="toself", fillcolor="rgba(214,40,40,0.15)",
                             line=dict(width=0), name="자기 에너지 W (곡선 위쪽)"), 1, 1)
    fig.add_trace(go.Scatter(x=np.r_[ii, ii[-1]], y=np.r_[ll, 0], fill="toself", fillcolor="rgba(29,78,216,0.12)",
                             line=dict(width=0), name="코에너지 W′ (곡선 아래쪽)"), 1, 1)
    fig.update_xaxes(title_text="전류 i [A]")
    fig.update_yaxes(title_text="쇄교 자속 λ [Wb·turn]", row=1, col=1)
    fig.update_yaxes(title_text="[mH]", row=1, col=2)
    st.plotly_chart(lstyle(fig, height=380), width="stretch", key="l1_mag")
    c = st.columns(4)
    info_metric(c[0], "쇄교 자속 λ", f"{ll[-1]:.4f} Wb·t")
    info_metric(c[1], "자기 에너지 W = ∫i dλ", f"{W:.3f} J")
    info_metric(c[2], "코에너지 W′ = ∫λ di", f"{Wc:.3f} J", "선형이면 W = W′ = ½Li²")
    B = ll[-1] / (N * 4e-4)
    info_metric(c[3], "자속 밀도 B", f"{B:.2f} T", "포화 영역" if B > 0.85 * Bs else "선형 영역")
    check("전류를 키우면 처음엔 λ 가 비례하다가(선형 영역) Bs 근처에서 거의 늘지 않음(포화 영역)",
          "공극 x 가 길어지면 자기 저항이 커져 기울기(인덕턴스)가 작아지고 포화가 늦게 옴",
          "포화되면 L 이 작아지고, 에너지 W 와 코에너지 W′ 가 달라짐 (선형이면 같음)")
    st.markdown("##### 코일의 유도 기전력 (패러데이 법칙 e = −dλ/dt, 렌츠의 법칙)")
    c = st.columns(3)
    fm = c[0].slider("자석이 오가는 주파수 [Hz]", 0.5, 10.0, 2.0, 0.5, key="l1e_f")
    lm = c[1].slider("최대 쇄교 자속 λmax [Wb·turn]", 0.01, 0.5, 0.1, 0.01, key="l1e_l")
    tt = np.linspace(0, 2 / fm, 600)
    lam = lm * 0.5 * (1 - np.cos(2 * math.pi * fm * tt))
    e = -np.gradient(lam, tt)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("쇄교 자속 λ (자석이 다가오면 증가)", "유도 기전력 e = −dλ/dt"))
    fig.add_trace(go.Scatter(x=tt, y=lam, name="λ"), 1, 1); fig.add_trace(go.Scatter(x=tt, y=e, name="e"), 2, 1)
    fig.update_xaxes(title_text="시간 [s]", row=2, col=1)
    st.plotly_chart(lstyle(fig, height=360), width="stretch", key="l1_far")
    st.caption(f"최대 기전력 = π·f·λmax = {math.pi * fm * lm:.3f} V. 자석이 다가올 때(λ 증가) e 는 음, 멀어질 때 양 — "
               "유도 전류는 언제나 자속 변화를 방해하는 방향 (렌츠의 법칙).")


@st.fragment
def _force_reluctance():
    ref("1.2.2 직선 운동 기계 · 1.2.3 회전 기계 — 힘은 인덕턴스가 커지는(자기 저항이 작아지는) 방향, 릴럭턴스 토크와 평균 토크 조건")
    st.markdown("##### ① 직선 운동 기계 (단일 여자): 운동자에 걸리는 힘 F = ∂W′/∂x")
    c = st.columns(3)
    N = c[0].slider("권수 N", 50, 500, 200, 10, key="l1f_N")
    i = c[1].slider("전류 i [A]", 0.5, 20.0, 3.0, 0.5, key="l1f_i")
    xg, F, Fl, L = _force_curves(N, i)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("공극에 따른 인덕턴스 L(x)", "운동자에 걸리는 힘 (− = 공극을 줄이는 쪽)"))
    fig.add_trace(go.Scatter(x=xg, y=L * 1e3, name="L [mH]"), 1, 1)
    fig.add_trace(go.Scatter(x=xg, y=F, name="힘 (포화 포함)"), 1, 2)
    fig.add_trace(go.Scatter(x=xg, y=Fl, name="힘 (선형 해석해 ½i²dL/dx)", line=dict(dash="dot")), 1, 2)
    fig.update_xaxes(title_text="공극 x [mm]")
    fig.update_yaxes(title_text="[mH]", row=1, col=1); fig.update_yaxes(title_text="F [N]", row=1, col=2)
    st.plotly_chart(lstyle(fig, height=330), width="stretch", key="l1_force")
    st.caption("공극이 좁을수록 인덕턴스가 커지므로, 힘은 언제나 공극을 줄이는(인덕턴스가 커지는) 쪽으로 작용합니다. "
               "포화되면 해석해(점선)보다 힘이 작아집니다.")

    st.markdown("##### 운동자가 x1 → x2 로 움직일 때 λ-i 평면의 동작점 이동 (빠른 이동 vs 느린 이동)")
    c = st.columns(3)
    i0 = c[0].slider("코일 전류 i [A]", 0.5, 10.0, 3.0, 0.5, key="l1p_i")
    x1 = c[1].slider("이동 전 공극 x1 [mm]", 0.5, 4.0, 2.0, 0.1, key="l1p_x1")
    x2 = c[2].slider("이동 후 공극 x2 [mm]", 0.2, 3.5, 1.0, 0.1, key="l1p_x2")
    pth = _paths(i0, x1, x2)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("매우 빨리 이동 (λ 일정: A → C → B)", "매우 느리게 이동 (i 일정: A → B)"))
    for col, key in ((1, "fast"), (2, "slow")):
        fig.add_trace(go.Scatter(x=pth["i"], y=pth["lam1"], name="x = x1", line=dict(color="#1d4ed8"), showlegend=col == 1), 1, col)
        fig.add_trace(go.Scatter(x=pth["i"], y=pth["lam2"], name="x = x2 (공극 감소)", line=dict(color="#d62828"), showlegend=col == 1), 1, col)
        A, B, C = pth["A"], pth["B"], pth["C"]
        if key == "fast":
            fig.add_trace(go.Scatter(x=[0, A[0], C[0], 0], y=[0, A[1], C[1], 0], fill="toself", fillcolor="rgba(42,157,143,0.3)",
                                     line=dict(color="#2a9d8f"), name="기계적 에너지 = 면적 OAC"), 1, col)
            fig.add_trace(go.Scatter(x=[A[0], C[0], B[0]], y=[A[1], C[1], B[1]], mode="markers+text", text=["A", "C", "B"],
                                     textposition="top left", marker=dict(size=9, color="#111"), showlegend=False), 1, col)
        else:
            fig.add_trace(go.Scatter(x=[0, A[0], B[0], 0], y=[0, A[1], B[1], 0], fill="toself", fillcolor="rgba(233,196,106,0.4)",
                                     line=dict(color="#e9c46a"), name="기계적 에너지 = 면적 OAB"), 1, col)
            fig.add_trace(go.Scatter(x=[A[0], B[0]], y=[A[1], B[1]], mode="markers+text", text=["A", "B"], textposition="top left",
                                     marker=dict(size=9, color="#111"), showlegend=False), 1, col)
    fig.update_xaxes(title_text="i [A]"); fig.update_yaxes(title_text="λ [Wb·turn]", row=1, col=1)
    st.plotly_chart(lstyle(fig, height=340), width="stretch", key="l1_paths")
    c = st.columns(3)
    info_metric(c[0], "빠른 이동의 기계적 에너지", f"{pth['W_fast'] * 1000:.1f} mJ", "자기 에너지에서 나옴 (전원 공급 없음)")
    info_metric(c[1], "느린 이동의 기계적 에너지", f"{pth['W_slow'] * 1000:.1f} mJ", "코에너지 증가분 (전원이 공급)")
    st.markdown("##### 교재 예제 1: L(x) = 5×10⁻³·x [H], 전류 2 A, 스프링 k = 5 N/m 일 때 힘과 이동 거리")
    c = st.columns(3)
    ie = c[0].slider("전류 [A]", 0.5, 5.0, 2.0, 0.5, key="l1x_i")
    dL = c[1].number_input("dL/dx [H/m]", 1e-3, 5e-2, 5e-3, 1e-3, format="%.4f", key="l1x_dL")
    k = c[2].slider("스프링 상수 k [N/m]", 1.0, 20.0, 5.0, 0.5, key="l1x_k")
    Fm = 0.5 * ie * ie * dL
    c = st.columns(3)
    info_metric(c[0], "힘 Fm = ½ i² dL/dx", f"{Fm:.3f} N"); info_metric(c[1], "이동 거리 Δx = Fm / k", f"{Fm / k * 100:.2f} cm")

    st.markdown("##### ② 회전 기계의 릴럭턴스 토크: L(θ) = L0 + L2·cos2θ,  T = ½i²·dL/dθ")
    th_ = np.linspace(0, 360, 361)
    figL = go.Figure(go.Scatter(x=th_, y=1.0 + 0.5 * np.cos(np.radians(2 * th_)), name="Lss(θ)"))
    figL.add_hline(y=1.5, line=dict(dash="dot"), annotation_text="Lmax (θ = 0°, 180°: 돌극이 자계 방향)")
    figL.add_hline(y=0.5, line=dict(dash="dot"), annotation_text="Lmin (θ = 90°, 270°)")
    figL.add_hline(y=1.0, line=dict(dash="dash", color="#999"), annotation_text="L0 = (Lmax + Lmin)/2")
    figL.update_xaxes(title_text="회전자 위치 θ [°]", dtick=90); figL.update_yaxes(title_text="고정자 자기 인덕턴스 (상대값)")
    st.plotly_chart(lstyle(figL, height=260), width="stretch", key="l1_Lth")
    c = st.columns(4)
    ratio = c[0].slider("회전자 속도 ωm / 전류 각주파수 ωs", 0.0, 2.0, 1.0, 0.05, key="l1r_ratio")
    delta = c[1].slider("초기 위치(부하각) δ [°]", -90, 90, 30, 5, key="l1r_d")
    Im, L2 = 10.0, 0.01
    ws = 2 * math.pi * 10
    t = np.linspace(0, 4 / 10, 2000)
    T = ch1.reluctance_torque(t, Im, ws, ratio * ws, math.radians(delta), L2)
    Tavg = ch1.reluctance_avg(Im, ws, ratio * ws, math.radians(delta), L2, cycles=60)
    rr = np.linspace(0, 2, 81)
    avg = _rel_sweep(delta)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("순시 토크 (전류 4주기)", "평균 토크 vs ωm/ωs"))
    fig.add_trace(go.Scatter(x=t * 1000, y=T, name="순시 토크"), 1, 1)
    fig.add_hline(y=Tavg, line=dict(color="#d62828", dash="dash"), row=1, col=1)
    fig.add_trace(go.Scatter(x=rr, y=avg, name="평균 토크", mode="lines+markers", marker=dict(size=4)), 1, 2)
    fig.add_trace(go.Scatter(x=[ratio], y=[Tavg], mode="markers", marker=dict(size=12, color="#d62828"), name="현재"), 1, 2)
    fig.update_xaxes(title_text="시간 [ms]", row=1, col=1); fig.update_xaxes(title_text="ωm / ωs", row=1, col=2)
    fig.update_yaxes(title_text="T [N·m]")
    st.plotly_chart(lstyle(fig, height=330), width="stretch", key="l1_rel")
    c = st.columns(3)
    info_metric(c[0], "평균 토크 (계산)", f"{Tavg:.4f} N·m")
    info_metric(c[1], "동기일 때 해석해 (Im²L2/4)·sin2δ", f"{ch1.reluctance_avg_sync(Im, L2, math.radians(delta)):.4f} N·m")
    check("ωm/ωs 를 1 에서 조금만 벗어나도 평균 토크가 0 → 동기 속도로 돌 때만 회전력이 생김 (동기 릴럭턴스 전동기)",
          "δ 를 바꾸면 평균 토크가 sin2δ 로 변하고, 회전자가 원통형(L2 = 0)이면 토크가 없음")


@st.fragment
def _double():
    ref("1.2.3 이중 여자 기기·원통형 기기 — T = −is·ir·M·sinθ, 평균 토크 조건 ωm = ωs ± ωr (직류·동기·유도 전동기)")
    c = st.columns([2, 3])
    kind = c[0].radio("전동기 종류로 맞추기", list(ch1.MACHINES), key="l1d_kind")
    c[1].info(ch1.MACHINES[kind])
    c = st.columns(4)
    if kind == "직류 전동기":
        ws0, wr0 = 0.0, 20.0
    elif kind == "동기 전동기":
        ws0, wr0 = 20.0, 0.0
    else:
        ws0, wr0 = 20.0, 1.0
    ws = c[0].slider("고정자 전류 각주파수 ωs [rad/s]", 0.0, 40.0, ws0, 0.5, key=f"l1d_ws_{kind}")
    wr = c[1].slider("회전자 전류 각주파수 ωr [rad/s]", 0.0, 40.0, wr0, 0.5, key=f"l1d_wr_{kind}")
    wm_def = {"직류 전동기": wr0, "동기 전동기": ws0, "유도 전동기": ws0 - wr0}[kind]
    wm = c[2].slider("회전자 속도 ωm [rad/s]", 0.0, 40.0, float(wm_def), 0.5, key=f"l1d_wm_{kind}")
    th0 = c[3].slider("회전자 초기 각 θ0 [°]", -180, 180, -90, 15, key="l1d_th")
    t = np.linspace(0, 3.0, 3000)
    T = ch1.double_excited_torque(t, 1, 1, 1, ws, wr, wm, math.radians(th0))
    avg = ch1.double_excited_avg(1, 1, 1, ws, wr, wm, math.radians(th0))
    sweep = np.linspace(0, 40, 161)
    av = _dbl_sweep(ws, wr, th0)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("순시 토크 (단위값)", "평균 토크 vs 회전자 속도 ωm"))
    fig.add_trace(go.Scatter(x=t, y=T, name="순시 토크"), 1, 1)
    fig.add_hline(y=avg, line=dict(color="#d62828", dash="dash"), row=1, col=1)
    fig.add_trace(go.Scatter(x=sweep, y=av, name="평균 토크"), 1, 2)
    for wv, lab in ((ws + wr, "ωs+ωr"), (abs(ws - wr), "|ωs−ωr|")):
        fig.add_vline(x=wv, line=dict(color="#aaa", dash="dot"), row=1, col=2)
        fig.add_annotation(x=wv, y=1, xref="x2", yref="y2 domain", text=lab, showarrow=False, font=dict(size=11))
    fig.add_trace(go.Scatter(x=[wm], y=[avg], mode="markers", marker=dict(size=12, color="#d62828"), name="현재"), 1, 2)
    fig.update_xaxes(title_text="시간 [s]", row=1, col=1); fig.update_xaxes(title_text="ωm [rad/s]", row=1, col=2)
    st.plotly_chart(lstyle(fig, height=340), width="stretch", key="l1_double")
    info_metric(st.columns(3)[0], "평균 토크", f"{avg:.3f} (단위값)")
    check("평균 토크는 ωm = ωs + ωr 또는 ωm = |ωs − ωr| 일 때만 0 이 아님",
          "직류 전동기: ωs = 0 이면 ωr = ωm (정류자가 맞춰 줌) · 동기: ωr = 0 이면 ωm = ωs · 유도: ωr = ωs − ωm (슬립)",
          "θ0 를 바꾸면 평균 토크 크기가 변함 (브러시 위치·부하각)")


@st.fragment
def _load():
    ref("1.3 부하 시스템 — 운동 방정식 J·dω/dt = Te − TL − Bω, 부하 토크 종류, 기어·직선 운동의 등가 관성")
    c = st.columns(4)
    kind = c[0].selectbox("부하 종류", ch1.LOADS, key="l1l_kind")
    T0 = c[1].slider("기준 부하 토크 (1000 rpm 에서) [N·m]", 0.5, 20.0, 6.0, 0.5, key="l1l_T0")
    V = c[2].slider("전동기 전압 V [V]", 20, 140, 140, 5, key="l1l_V")
    J = c[3].slider("관성 J [kg·m²] (전동기+부하)", 0.001, 0.05, 0.01, 0.001, format="%.3f", key="l1l_J")
    K, Ra = 0.4058, 0.5
    w_ref = 1000 / RPM
    w = np.linspace(0, V / K * 1.05, 300)
    t, ww, Tm, TL, w_op = _startup(kind, V, T0, J)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("토크–속도: 전동기 곡선과 부하 곡선", "기동 과정 (속도)"))
    fig.add_trace(go.Scatter(x=w * RPM, y=ch1.dc_motor_torque(w, V, K, Ra), name="전동기 토크 Te"), 1, 1)
    fig.add_trace(go.Scatter(x=w * RPM, y=ch1.load_torque(kind, w, T0, w_ref), name="부하 토크 TL"), 1, 1)
    for k2 in ch1.LOADS:
        if k2 != kind:
            fig.add_trace(go.Scatter(x=w * RPM, y=ch1.load_torque(k2, w, T0, w_ref), name=k2.split(" (")[0], line=dict(dash="dot", width=1)), 1, 1)
    fig.add_trace(go.Scatter(x=[w_op * RPM], y=[ch1.load_torque(kind, w_op, T0, w_ref)], mode="markers",
                             marker=dict(size=12, color="#d62828"), name="운전점"), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=ww * RPM, name="속도 [rpm]"), 1, 2)
    fig.update_yaxes(range=[0, max(3 * T0, 10)], row=1, col=1)
    fig.update_xaxes(title_text="속도 [rpm]", row=1, col=1); fig.update_xaxes(title_text="시간 [s]", row=1, col=2)
    fig.update_yaxes(title_text="토크 [N·m]", row=1, col=1); fig.update_yaxes(title_text="rpm", row=1, col=2)
    st.plotly_chart(lstyle(fig, height=360), width="stretch", key="l1_load")
    c = st.columns(3)
    info_metric(c[0], "운전점 속도", f"{w_op * RPM:.0f} rpm")
    TLop = float(ch1.load_torque(kind, w_op, T0, w_ref))
    info_metric(c[1], "운전점 토크", f"{TLop:.2f} N·m")
    info_metric(c[2], "필요 출력 P = T·ω", f"{TLop * w_op:.0f} W")
    st.caption("전동기는 교재 2장의 직류 전동기 (Kφ = 0.406 V·s/rad, Ra = 0.5 Ω) 입니다. 운전점은 두 곡선의 교점이고, "
               "관성 J 가 클수록 그 점까지 가는 데 오래 걸립니다.")
    figP = go.Figure()
    for k2 in ch1.LOADS:
        figP.add_trace(go.Scatter(x=w * RPM, y=ch1.load_torque(k2, w, T0, w_ref) * w / 1000, name=k2.split(" (")[0],
                                  line=dict(width=3 if k2 == kind else 1.5)))
    figP.update_xaxes(title_text="속도 [rpm]"); figP.update_yaxes(title_text="부하 요구 전력 P = TL·ω [kW]", range=[0, None])
    st.markdown("##### 부하 종류별 요구 전력 (교재 그림: 일정 토크 → P ∝ ω, 일정 출력 → P 일정, 속도 제곱 → P ∝ ω³)")
    st.plotly_chart(lstyle(figP, height=300), width="stretch", key="l1_loadP")
    st.markdown("##### 회전체의 관성 모멘트 J = ½ m r² (같은 질량이라도 반지름이 크면 J 가 큼)")
    c = st.columns(4)
    mJ = c[0].slider("질량 m [kg]", 0.5, 50.0, 10.0, 0.5, key="l1j_m")
    rJ = c[1].slider("반지름 r [m]", 0.02, 0.5, 0.1, 0.01, key="l1j_r")
    info_metric(c[2], "원통·원판 J = ½ m r²", f"{ch1.cylinder_inertia(mJ, rJ):.4f} kg·m²")
    info_metric(c[3], "얇은 링 J = m r²", f"{mJ * rJ * rJ:.4f} kg·m²")
    st.markdown("##### 기어·벨트와 직선 운동 부하를 전동기 축에서 보면")
    c = st.columns(5)
    n = c[0].slider("감속비 n = ωm/ωL", 1.0, 20.0, 5.0, 0.5, key="l1g_n")
    JL = c[1].number_input("부하 관성 JL [kg·m²]", 0.0, 10.0, 0.5, 0.05, key="l1g_JL")
    TLL = c[2].number_input("부하 축 토크 TL [N·m]", 0.0, 500.0, 50.0, 5.0, key="l1g_TL")
    m = c[3].number_input("직선 운동 질량 m [kg]", 0.0, 5000.0, 200.0, 10.0, key="l1g_m")
    r = c[4].number_input("드럼·바퀴 반지름 r [m]", 0.01, 1.0, 0.15, 0.01, key="l1g_r")
    Jeq, _, TLeq = ch1.reflect_gear(0.01, JL + ch1.reflect_linear(m, r), 0, 0, TLL, n)
    c = st.columns(3)
    info_metric(c[0], "직선 부하의 등가 관성 m·r²", f"{ch1.reflect_linear(m, r):.3f} kg·m²")
    info_metric(c[1], "전동기 축 등가 관성 Jm + (JL + m r²)/n²", f"{Jeq:.4f} kg·m²", "Jm = 0.01 으로 가정")
    info_metric(c[2], "전동기 축 부하 토크 TL/n", f"{TLeq:.2f} N·m")
    check("일정 토크 부하는 속도에 관계없이 같은 토크, 일정 출력 부하는 저속일수록 큰 토크, 팬·펌프는 속도 제곱",
          "감속비 n 을 키우면 부하 관성이 n² 로 작아져 보이고 토크도 1/n 로 작아짐 (대신 속도는 n 배 필요)")


@st.fragment
def _quadrant():
    ref("1.3.3 전동기의 동작 모드 — 전동기 모드/발전기(제동) 모드, 4상한 운전 (엘리베이터 예)")
    c = st.columns(5)
    m_car = c[0].slider("빈 카 질량 [kg]", 300, 1500, 800, 50, key="l1q_car")
    m_load = c[1].slider("승객 질량 [kg]", 0, 1200, 600, 50, key="l1q_load")
    m_cw = c[2].slider("균형추 질량 [kg]", 300, 2500, 1100, 50, key="l1q_cw")
    v = c[3].slider("카 속도 [m/s] (+ 상승, − 하강)", -2.0, 2.0, 1.0, 0.1, key="l1q_v")
    r = c[4].slider("드럼 반지름 [m]", 0.1, 0.5, 0.25, 0.05, key="l1q_r")
    T, w, P, q = ch1.elevator(m_car, m_load, m_cw, v, r)
    names = {1: "1상한: 정방향 전동기 모드", 2: "2상한: 정방향 제동(발전기) 모드", 3: "3상한: 역방향 전동기 모드", 4: "4상한: 역방향 제동(발전기) 모드"}
    fig = go.Figure()
    lim_w, lim_T = 10, 4000
    cols = {1: "rgba(42,157,143,0.15)", 2: "rgba(231,111,81,0.15)", 3: "rgba(42,157,143,0.15)", 4: "rgba(231,111,81,0.15)"}
    for k, (x0, x1, y0, y1) in {1: (0, lim_w, 0, lim_T), 2: (0, lim_w, -lim_T, 0), 3: (-lim_w, 0, -lim_T, 0), 4: (-lim_w, 0, 0, lim_T)}.items():
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=cols[k] if k != q else cols[k].replace("0.15", "0.45"), line=dict(width=0), layer="below")
        fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2 * 1.6, text=names[k].replace(": ", "<br>"), showarrow=False, font=dict(size=12))
    fig.add_trace(go.Scatter(x=[w], y=[T], mode="markers", marker=dict(size=16, color="#d62828"), name="현재 운전점"))
    fig.update_xaxes(range=[-lim_w, lim_w], title_text="전동기 속도 ω [rad/s]  (+ = 카 상승)")
    fig.update_yaxes(range=[-lim_T, lim_T], title_text="전동기 토크 T [N·m]  (+ = 카를 끌어올리는 방향)")
    c = st.columns([3, 2])
    c[0].plotly_chart(lstyle(fig, height=420), width="stretch", key="l1_quad")
    with c[1]:
        st.markdown(f"### {names[q]}")
        info_metric(st, "전동기 토크", f"{T:.0f} N·m")
        info_metric(st, "전동기 속도", f"{w:.2f} rad/s ({w * RPM:.0f} rpm)")
        info_metric(st, "전력 P = T·ω", f"{P / 1000:.2f} kW", "+: 전원 → 부하 (전동기)  −: 부하 → 전원 (발전기)")
        st.markdown("전동기 모드" if P >= 0 else
                    "**제동 중**: 부하의 위치 에너지가 전기로 바뀝니다. 전원으로 되돌리면 **회생 제동**, 저항에서 열로 쓰면 **발전 제동**.")
    check("사람이 탄 카 상승 → 1상한, 빈 카 상승 → 2상한, 빈 카 하강 → 3상한, 사람이 탄 카 하강 → 4상한",
          "균형추가 카보다 무거우면 토크 부호가 바뀜")


@st.fragment
def _system():
    ref("1.4 전동기 구동 시스템의 구성 — 전원, 전력 변환 장치, 전동기, 제어기, 센서")
    st.plotly_chart(blocks([("전원<br>(단상·3상 교류)", "#fff3d6"), ("전력 변환 장치<br>정류기·초퍼·인버터", "#fdf0e6"),
                            ("전동기", "#eef4fb"), ("기계 부하", "#e6f5ec")], feedback=(3, 1, "센서 (전류·속도·위치) → 제어기 → 스위칭 지령")),
                    width="stretch", key="l1_sys")
    st.markdown("""
| 전동기 | 전력 변환 장치 | 이 앱에서 확인 |
|---|---|---|
| 직류 전동기 | 정류기 / 초퍼 (1상한, H-브리지 4상한) | 2장 초퍼 탭, 회로 시뮬레이터 '강압 초퍼'·'H-브리지' 예제 |
| BLDC 전동기 | 3상 인버터 (6스텝, 120° 통전) | 3장, BLDC 전동기 시뮬레이터 |
| 유도·동기 전동기 | (정류기 +) 3상 PWM 인버터 | 4장, 회로 시뮬레이터 '3상 인버터' 예제, 유도전동기·PMSM 시뮬레이터 |
""")
    c = st.columns(3)
    with c[0]: link("회로 시뮬레이터", "circuit")
    with c[1]: link("제어 블록 편집기", "blocks")
    with c[2]: link("DC 전동기 시뮬레이터", "")


def render():
    st.title("📘 1장 전동기의 기본 원리")
    st.caption("강의 자료 1장의 내용을 직접 값을 바꿔 가며 확인합니다. 탭은 교재 절 순서입니다.")
    tabs = st.tabs(["1.1 동작 원리", "1.2 자기회로·λ-i 특성", "1.2 힘·릴럭턴스 토크", "1.2 이중 여자·평균 토크 조건",
                    "1.3 부하 시스템", "1.3.3 4상한 운전", "1.4 구동 시스템 구성"])
    for tab, fn in zip(tabs, (_principle, _magnetic, _force_reluctance, _double, _load, _quadrant, _system)):
        with tab:
            fn()
