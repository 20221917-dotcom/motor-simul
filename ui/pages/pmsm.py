"""PMSM 페이지: 원리(실시간 FOC) · 정상상태(dq 평면, 운전 영역) · 계통 직결(동기 운전·탈조) · 제어(실시간)."""
import math
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.simulate import simulate, Event
from core.units import to_rpm, to_rad_s
from motors import registry
import motors.ac.pmsm  # noqa: F401  (모델 등록 보장)
from ui import realtime
from ui.params_panel import render_params
from ui.plots import info_metric, style, mark_events, PALETTE

ASSUMPTIONS = ("**모델 가정** · 정현파 역기전력, 3상 평형, 선형 자기회로(Ld·Lq 일정), 철손·코깅 토크·인버터 데드타임 무시, "
               "진폭 불변 dq 변환. 인버터는 평균값 모델이며 전압 한계는 Vdc/√3 (SVPWM 선형 영역), 위치 센서는 이상적입니다.")


# ---------------------------------------------------------------- ① 원리
def tab_principle(m, params):
    left, right = st.columns([3, 1])
    with left:
        st.markdown("#### 실시간 벡터 제어 (dq 축)")
        st.caption("회전자 자석 방향을 d축, 그와 90° 방향을 q축으로 두면 정현파 3상 전류가 dq 좌표에서는 **직류**가 됩니다. "
                   "q축 전류 iq 가 토크를, d축 전류 id 가 자속(약계자·릴럭턴스 토크)을 담당합니다. 지령을 바꾸면 바로 반응합니다.")
    with right:
        st.markdown("**핵심 수식**")
        st.latex(r"v_d = R_s i_d + L_d \dot i_d - \omega_e L_q i_q")
        st.latex(r"v_q = R_s i_q + L_q \dot i_q + \omega_e (L_d i_d + \lambda_f)")
        st.latex(r"T_e = \tfrac{3}{2}\tfrac{P}{2}\left[\lambda_f i_q + (L_d - L_q) i_d i_q\right]")
    realtime.render(realtime.pmsm_principle_html(m), height=800)
    st.divider()
    st.markdown("#### 구조와 특징 · DC / BLDC 와 비교")
    st.markdown("""
| 항목 | DC 전동기 | BLDC | PMSM |
|---|---|---|---|
| 회전자 | 전기자 권선 | 영구자석 | 영구자석 (표면 부착 SPM / **매입 IPM**) |
| 역기전력 | 직류 | 사다리꼴 | **정현파** |
| 전류 | 직류 | 120° 사각파 (6스텝) | **정현파** (벡터 제어) |
| 토크 리플 | 정류자편 | 정류 리플 큼 | 매우 작음 |
| 토크 제어 변수 | 전기자 전류 Ia | 상전류 I | q축 전류 iq (+ id 로 릴럭턴스 토크) |
| 고속 운전 | 계자 약화 | 진각 | **약계자 제어** (id < 0) |
""")


# ---------------------------------------------------------------- ② 정상상태
def _min_current_point(m, T, w_m, n=400):
    """토크 T 를 내는 점 가운데 전압 한계 안에서 전류가 가장 작은 (id, iq)."""
    p = m.p
    best = None
    for id_ in np.linspace(-1.5 * p["Imax"], 0, n):
        den = 1.5 * m.pp * (p["lam"] + (p["Ld"] - p["Lq"]) * id_)
        if den <= 1e-9:
            continue
        iq = T / den
        if m.voltage_mag(id_, iq, w_m) > m.Vmax:
            continue
        I = math.hypot(id_, iq)
        if best is None or I < best[2]:
            best = (id_, iq, I)
    return best


def tab_steady(m, params):
    p = m.p
    wb = m.base_speed()
    nb = to_rpm(wb)
    T0, id0, iq0 = m.max_torque_at_speed(1e-3)
    ich = p["lam"] / p["Ld"]
    c = st.columns(4)
    info_metric(c[0], "기저 속도", f"{nb:.0f} rpm", "MTPA·최대 전류에서 전압 한계")
    info_metric(c[1], "최대 토크 (저속)", f"{T0:.2f} N·m", f"id = {id0:.1f}, iq = {iq0:.1f} A")
    info_metric(c[2], "특성 전류 λf/Ld", f"{ich:.1f} A", "≤ I_max 이면 이론상 무한 속도까지 약계자 가능")
    info_metric(c[3], "전압 한계 Vdc/√3", f"{m.Vmax:.0f} V")
    st.markdown("#### id–iq 평면: 전류 한계 원, 전압 한계 타원, 등토크 곡선, MTPA")
    cc = st.columns([1, 1, 2])
    n_sel = cc[0].slider("속도 [rpm]", 0, int(3 * nb), int(round(0.8 * nb, -1)), 10, key="pm_n")
    T_sel = cc[1].slider("토크 [N·m]", 0.0, float(round(T0, 1)), float(min(params["TL"], T0)), 0.1, key="pm_T")
    w_sel = to_rad_s(n_sel)
    pt = _min_current_point(m, T_sel, w_sel) if T_sel > 0 else (0.0, 0.0, 0.0)
    with cc[2]:
        if pt is None:
            st.error(f"{n_sel} rpm 에서 {T_sel:.2f} N·m 를 낼 수 없습니다 (전압 한계).")
        else:
            ok = pt[2] <= p["Imax"]
            st.markdown(f"**운전점**: id = {pt[0]:.2f} A, iq = {pt[1]:.2f} A, |i| = {pt[2]:.2f} A "
                        + ("✅ 전류 한계 안" if ok else "⚠️ 전류 한계 초과"))
            mt = m.mtpa(pt[2])
            st.caption(f"같은 전류의 MTPA 점은 id = {float(mt[0]):.2f} A. 운전점 id 가 그보다 더 음수면 전압 한계 때문에 **약계자** 중입니다.")
    Imax = p["Imax"]
    g = np.linspace(-1.6 * Imax, 0.4 * Imax, 220)
    h = np.linspace(0, 1.3 * Imax, 200)
    ID, IQ = np.meshgrid(g, h)
    fig = go.Figure()
    Tg = m.torque(ID, IQ)
    lv = np.linspace(0.2, 1.0, 5) * T0
    fig.add_trace(go.Contour(x=g, y=h, z=Tg, contours=dict(coloring="none", showlabels=True, start=lv[0], end=lv[-1],
                                                           size=lv[1] - lv[0], labelfont=dict(size=10, color="#2a9d8f")),
                             line=dict(color="#2a9d8f", width=1, dash="dot"), name="등토크 곡선 [N·m]", showscale=False, showlegend=True))
    for nn, col, wdt in ((n_sel, "#d62828", 3), (nb, "#f4a261", 1.5), (2 * nb, "#e9c46a", 1.5)):
        if nn <= 0:
            continue
        V = m.voltage_mag(ID, IQ, to_rad_s(nn))
        fig.add_trace(go.Contour(x=g, y=h, z=V, contours=dict(coloring="none", start=m.Vmax, end=m.Vmax, size=1),
                                 line=dict(color=col, width=wdt), name=f"전압 한계 ({nn:.0f} rpm)", showscale=False, showlegend=True))
    a = np.linspace(0, math.pi, 200)
    fig.add_trace(go.Scatter(x=Imax * np.cos(a), y=Imax * np.sin(a), name=f"전류 한계 |i| = {Imax:.0f} A", line=dict(color="#264653", width=2.5)))
    Is = np.linspace(0, Imax * 1.2, 60)
    mid, miq = m.mtpa(Is)
    fig.add_trace(go.Scatter(x=mid, y=miq, name="MTPA 궤적", line=dict(color="#7c3aed", width=2.5)))
    if pt:
        fig.add_trace(go.Scatter(x=[pt[0]], y=[pt[1]], mode="markers", name="운전점 (최소 전류)", marker=dict(size=14, color="#e76f51", symbol="diamond")))
    fig.add_vline(x=-ich, line=dict(color="#999", dash="dash"), annotation_text="−λf/Ld (타원 중심)")
    style(fig, 520, xaxis_title="d축 전류 id [A]", yaxis_title="q축 전류 iq [A]", hovermode="closest")
    fig.update_xaxes(range=[g[0], g[-1]]); fig.update_yaxes(range=[0, h[-1]], scaleanchor="x")
    st.plotly_chart(fig, width="stretch")
    st.caption("속도가 오르면 전압 한계 타원이 −λf/Ld 쪽으로 줄어듭니다. 운전점이 타원 밖이면 그 속도에서 낼 수 없으므로 "
               "id 를 음으로 보내(약계자) 타원 안으로 들어갑니다. 매입형(Lq > Ld)은 id < 0 에서 릴럭턴스 토크가 더해져 MTPA 가 d축 음의 방향으로 휩니다.")

    st.markdown("#### 토크–속도 한계 곡선 (운전 영역)")
    ns = np.linspace(1, 3 * nb, 60)
    res = [m.max_torque_at_speed(to_rad_s(n_)) for n_ in ns]
    Tm = np.array([r_[0] for r_ in res])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=ns, y=Tm, name="최대 토크", line=dict(color=PALETTE["speed"], width=3)), secondary_y=False)
    fig.add_trace(go.Scatter(x=ns, y=Tm * to_rad_s(ns) / 1e3, name="최대 출력 [kW]", line=dict(color=PALETTE["ia"], dash="dot")), secondary_y=True)
    fig.add_vline(x=nb, line=dict(color="#999", dash="dash"), annotation_text="기저 속도")
    fig.add_trace(go.Scatter(x=[n_sel], y=[T_sel], mode="markers", name="선택 운전점", marker=dict(size=12, color="#e76f51", symbol="diamond")), secondary_y=False)
    style(fig, 360, xaxis_title="속도 [rpm]", hovermode="closest")
    fig.update_yaxes(title_text="토크 [N·m]", secondary_y=False)
    fig.update_yaxes(title_text="출력 [kW]", showgrid=False, secondary_y=True)
    st.plotly_chart(fig, width="stretch")
    nz = ns[np.argmax(Tm <= 1e-9)] if np.any(Tm <= 1e-9) else None
    st.caption("기저 속도까지는 최대 전류로 낼 수 있는 토크가 일정합니다 (정토크 영역). 그 위는 약계자 영역입니다. "
               + (f"이 전동기는 특성 전류 λf/Ld = {ich:.1f} A 가 I_max = {Imax:.0f} A 보다 커서 자석 자속을 다 상쇄하지 못하므로 "
                  f"출력이 줄다가 약 {nz:.0f} rpm 에서 0 이 됩니다. Ld 를 키우거나 λf 를 줄여 λf/Ld ≤ I_max 로 만들면 정출력 영역이 넓어집니다."
                  if ich > Imax and nz else "λf/Ld ≤ I_max 라서 출력을 거의 일정하게 유지하며 고속까지 운전할 수 있습니다 (정출력 영역)."))


# ---------------------------------------------------------------- ③ 계통 직결
def _grid_sim(m, V, f, Kd, x0, t_end, events):
    from motors.ac.pmsm import GridInputs
    return simulate(m, GridInputs(V=V, f=f, TL=0.0, Kd=Kd), t_end, x0=x0,
                    events=[Event(t, dict(ch), lab) for t, ch, lab in events], n_points=6000, max_step=2e-4)


@st.cache_data(max_entries=20, show_spinner="계산 중…")
def _grid_cached(params_items, V, f, Kd, x0, t_end, events):
    m = registry.get("pmsm")(dict(params_items))
    return _grid_sim(m, V, f, Kd, x0, t_end, events)


def tab_grid(m, params):
    from motors.ac.pmsm import GridInputs
    st.caption("인버터 없이 상용 전원에 바로 연결했을 때의 동작입니다. 동기전동기는 **동기속도로만** 평균 토크를 낼 수 있습니다.")
    u0 = m.default_inputs()
    c = st.columns(4)
    V = c[0].number_input("전원 선간 전압 [V]", 1.0, 1000.0, float(u0.V), 1.0, key="pg_V")
    f = c[0].number_input("주파수 [Hz]", 1.0, 400.0, 60.0, 1.0, key="pg_f")
    Kd = c[0].number_input("제동 권선 계수 Kd [N·m·s/rad]", 0.0, 10.0, 0.2, 0.05, key="pg_Kd",
                           help="회전자 농형 제동 권선(댐퍼)이 만드는 비동기 토크 Kd·(ωs − ω). 0 이면 제동 권선 없음.")
    Tpo, dpo = m.pullout_torque(GridInputs(V=V, f=f, TL=0))
    mode = c[1].radio("상황", ["동기속도에서 부하 증가 (부하각·탈조)", "정지 상태에서 직결 (기동)"], key="pg_mode")
    how = c[1].radio("부하를 거는 방식", ["계단 (갑자기)", "램프 (1 초 동안 천천히)"], key="pg_how")
    TL = c[2].number_input("부하 토크 [N·m]", 0.0, 500.0, round(0.5 * Tpo, 1), 0.5, key="pg_TL")
    t_load = c[2].number_input("부하 인가 시각 [s]", 0.0, 5.0, 0.2, 0.05, key="pg_tl")
    t_end = c[3].number_input("시뮬레이션 시간 [s]", 0.1, 6.0, 2.0, 0.1, key="pg_tend")
    st.markdown(f"**정상상태 탈조 토크** ≈ **{Tpo:.1f} N·m** (부하각 {dpo:.0f}°, 고정자 저항 포함) · 지금 부하는 그 **{TL / Tpo * 100:.0f} %**")
    ns = 120 * f / params["poles"]
    if how.startswith("계단"):
        events = ((t_load, (("TL", TL),), "부하 인가"),)
    else:
        events = tuple((t_load + 0.05 * k, (("TL", TL * (k + 1) / 20),), "부하 증가 시작" if k == 0 else "") for k in range(20))
    if mode.startswith("동기"):
        we = 2 * math.pi * f
        id0 = (math.sqrt(2 / 3) * V / we - params["lam"]) / params["Ld"]
        x0 = (id0, 0.0, we / m.pp, -math.pi / 2 / m.pp, 0.0)   # 무부하 동기 운전 (전압이 q축)
    else:
        x0 = (0.0, 0.0, 0.0, 0.0, 0.0)
    r = _grid_cached(tuple(sorted(params.items())), V, f, Kd, x0, t_end, events)
    tail = r.t > 0.8 * t_end
    synced = abs(np.mean(r["rpm"][tail]) - ns) < 0.01 * ns and np.ptp(r["rpm"][tail]) < 0.02 * ns
    k = st.columns(3)
    info_metric(k[0], "동기속도", f"{ns:.0f} rpm")
    info_metric(k[1], "끝 구간 평균 속도", f"{np.mean(r['rpm'][tail]):.0f} rpm")
    if mode.startswith("동기"):
        info_metric(k[2], "판정", "동기 유지" if synced else "⚠️ 탈조 (동기 이탈)",
                    f"끝 부하각 {np.mean(r['delta_deg'][tail]):.0f}°" if synced else "")
    else:
        info_metric(k[2], "판정", "기동 성공 → 동기 진입" if synced else "기동 실패", "제동 권선 덕분" if synced and Kd > 0 else "")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=("속도 [rpm]", "부하각 δ [°]", "토크 [N·m]", "dq 전류 [A]"))
    fig.add_trace(go.Scatter(x=r.t, y=np.full(len(r.t), ns), name="동기속도", line=dict(color="#9aa0a6", dash="dash")), 1, 1)
    fig.add_trace(go.Scatter(x=r.t, y=r["rpm"], name="속도", line=dict(color=PALETTE["speed"])), 1, 1)
    fig.add_trace(go.Scatter(x=r.t, y=r["delta_deg"], name="부하각 δ", line=dict(color="#7c3aed")), 2, 1)
    fig.add_trace(go.Scatter(x=r.t, y=r["Te"], name="Te (자석+릴럭턴스)", line=dict(color=PALETTE["Te"], width=1.2)), 3, 1)
    fig.add_trace(go.Scatter(x=r.t, y=r["TL"], name="TL", line=dict(color=PALETTE["TL"], dash="dash")), 3, 1)
    fig.add_trace(go.Scatter(x=r.t, y=r["id"], name="id", line=dict(color="#d62828", width=1)), 4, 1)
    fig.add_trace(go.Scatter(x=r.t, y=r["iq"], name="iq", line=dict(color="#2a9d3a", width=1)), 4, 1)
    style(fig, 900, side_legend=True)
    mark_events(fig, [e for e in r.events if e.label], rows=range(1, 5))
    fig.update_xaxes(title_text="시간 [s]", row=4, col=1)
    st.plotly_chart(fig, width="stretch")
    st.markdown("""
- **제동 권선이 없으면(Kd = 0)** 동기 운전 중 작은 흔들림이 점점 커지는 **난조**가 생기고, 정지 상태에서 직결하면 토크가 반 주기마다
  방향을 바꿔 평균 0 이라 **기동하지 못합니다**. 그래서 보통 PMSM 은 **인버터로 주파수를 0 부터 올리며** 기동합니다.
- **제동 권선이 있으면** 유도전동기처럼 비동기 토크로 가속한 뒤 동기속도에 끌려 들어갑니다 (라인 기동형 PMSM).
- **부하각 δ**: 부하가 늘면 회전자가 전원 전압보다 뒤처지는 각이 커지며 토크가 늘어납니다. 탈조 토크를 넘으면 동기를 잃습니다.
- 부하를 **갑자기** 걸면 부하각이 정상값을 지나쳐 크게 흔들리므로, 탈조 토크보다 작은 부하에서도 탈조할 수 있습니다
  (등면적법). **램프**로 천천히 걸면 탈조 토크 가까이까지 버팁니다.
""")


# ---------------------------------------------------------------- ④ 제어
def tab_control(m, params):
    st.markdown("#### 제어 구조 (벡터 제어 FOC)")
    st.markdown("**n\\*** → (Σ) → **속도 PI** → 전류 크기 지령 → **id\\*, iq\\*** 결정 (id = 0 / MTPA / MTPA + 약계자) → "
                "(Σ) → **d·q 전류 PI** (+비간섭 −ωLq·iq, ω(Ld·id + λf)) → **전압 한계 원** Vdc/√3 → 역 Park 변환 → 인버터 → **PMSM**")
    st.caption("약계자는 전압 크기 |v| 가 한계의 95 % 를 넘으면 id 를 음으로 더 보내는 전압 피드백 방식입니다.")
    realtime.render(realtime.pmsm_control_html(m), height=880)
    with st.expander("해 볼 실험", expanded=False):
        st.markdown(f"""
1. **id = 0 vs MTPA**: 같은 부하에서 MTPA 가 전류를 더 적게 씁니다 (매입형이라 릴럭턴스 토크 이용).
2. **기저 속도({to_rpm(m.base_speed()):.0f} rpm) 넘기기**: id = 0 이나 MTPA 로는 전압 한계에 걸려 속도가 지령에 못 미칩니다.
   'MTPA + 약계자'로 바꾸면 id 가 음으로 커지며 지령 속도에 도달합니다 (전압 그래프가 한계선 아래로 내려옴).
3. **비간섭 보상 끄기**: 속도가 높을 때 d·q 전류가 서로 영향을 주어 응답이 나빠집니다.
4. **역회전**: 음의 속도 지령 → iq 가 음이 되어 제동 후 역회전합니다.
""")


def render():
    st.title("🧲 PMSM 시뮬레이터 (영구자석 동기전동기)")
    st.caption("매입형 PMSM (Ld < Lq). dq 좌표 모델, 벡터 제어(id=0·MTPA·약계자), 운전 영역, 계통 직결 동기 운전과 탈조를 다룹니다.")
    cls = registry.get("pmsm")
    params, errors = render_params(cls)
    if errors:
        st.error("파라미터에 맞지 않는 값이 있습니다.\n\n" + "\n".join(f"- {e}" for e in errors))
        st.stop()
    m = cls(params)
    tabs = st.tabs(["① 원리 이해", "② 정상상태 · 운전 영역", "③ 계통 직결 (동기 운전·탈조)", "④ 제어"])
    with tabs[0]:
        tab_principle(m, params)
    with tabs[1]:
        tab_steady(m, params)
    with tabs[2]:
        tab_grid(m, params)
    with tabs[3]:
        tab_control(m, params)
    st.divider()
    st.caption(ASSUMPTIONS)
