"""유도전동기 페이지: 원리(실시간) · 정상상태(등가회로) · 동특성 · 제어(실시간)."""
from dataclasses import replace
import math
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.simulate import simulate, Event
from core.units import to_rpm
from motors import registry
import motors.ac.induction  # noqa: F401  (모델 등록 보장)
from ui import realtime
from ui.params_panel import render_params
from ui.plots import info_metric, style, mark_events, PALETTE

PCOL = ["#d62828", "#2a9d3a", "#1d4ed8"]
ASSUMPTIONS = ("**모델 가정** · 3상 평형, 농형(회전자 단락), 선형 자기회로, 철손·표피효과·공간 고조파 무시, "
               "회전자 값은 고정자 쪽 환산. 동특성은 αβ 좌표 자속 모델(진폭 불변 변환), 정상상태는 상당 등가회로. "
               "인버터 제어는 평균값 모델입니다.")


# ---------------------------------------------------------------- ① 원리
def tab_principle(m, params):
    left, right = st.columns([3, 1])
    with left:
        st.markdown("#### 실시간 회전자계와 슬립")
        st.caption("3상 전류가 만드는 자계가 **동기속도 ns = 120f/P** 로 돕니다. 회전자가 그보다 느리게 돌면 회전자 도체가 자계를 "
                   "끊어 전류가 유도되고, 그 전류가 자계와 만나 토크가 생깁니다. 주파수·전압·부하를 바꾸면 바로 반응합니다.")
    with right:
        st.markdown("**핵심 수식**")
        st.latex(r"n_s = \frac{120 f}{P},\quad s = \frac{n_s - n}{n_s}")
        st.latex(r"f_r = s\,f")
        st.latex(r"T = \frac{3}{\omega_s}\,|I_2'|^2\frac{R_r'}{s}")
    realtime.render(realtime.im_principle_html(m), height=760)
    with st.expander("그림 읽는 법", expanded=False):
        st.markdown("""
- **보라 화살표** (고정자 전류 벡터 = 기자력 방향)가 동기속도로 돕니다. 이빨 색은 그 순간 각 상 전류가 만드는 극성입니다.
- **노란 점**은 회전자에 찍은 표시입니다. 보라 화살표보다 느리게 돕니다 → **슬립**.
- 회전자 도체의 **⊙/⊗** 는 유도된 전류입니다. 회전자가 자계를 따라잡으면(s → 0) 유도 전류와 토크가 0 이 되므로,
  유도전동기는 **동기속도보다 항상 조금 느리게** 돕니다.
- 기동 직후(s = 1) 회전자 전류 주파수가 전원과 같고 전류가 정격의 5~7 배로 큽니다.
- 주파수를 바꾸면 동기속도가 바뀝니다. **V/f 일정**을 켜 두면 자속이 유지되어 낮은 주파수에서도 토크가 나옵니다.
""")
    st.divider()
    st.markdown("#### 유도전동기 구조와 특징 · DC 전동기와 비교")
    st.markdown("""
| 항목 | DC 전동기 | 유도전동기 (농형) |
|---|---|---|
| 자계 | 고정자 계자 (정지 자계) | 고정자 3상 권선이 만드는 **회전자계** |
| 회전자 | 전기자 권선 + 정류자 | **농형 도체 (단락 링)** — 전원 연결 없음 |
| 회전자 전류 | 브러시로 공급 | 슬립에 의해 **유도** |
| 속도 | V/Kφ 근처 | 동기속도 120f/P 보다 조금 느림 |
| 속도 제어 | 전압·계자 | **주파수** (V/f, 벡터 제어) |
| 장점 | 제어가 쉬움 | 구조가 튼튼하고 값싸며 유지보수가 거의 없음 |
""")


# ---------------------------------------------------------------- ② 정상상태
def _tn_curve(m, u, s_lo=-0.6, s_hi=1.6, n=900):
    s = np.linspace(s_lo, s_hi, n)
    s = s[np.abs(s) > 1e-4]
    T = m.torque(s, u)
    _, _, I1, _ = m._circuit(s, u)
    return s, (1 - s) * to_rpm(m.ws(u)), T, np.abs(I1)


def tab_steady(m, params):
    u = m.default_inputs()
    op = m.steady_state(u)
    Tmax, smax = m.max_torque(u)
    Tst = float(m.torque(1.0, u))
    Ist = float(abs(m._circuit(1.0, u)[2]))
    ns = 120 * u.f / params["poles"]
    st.caption(f"상당 등가회로 기준 · V = {u.V:.0f} V, f = {u.f:.0f} Hz, 동기속도 {ns:.0f} rpm")
    if op is None:
        st.error(f"⚠️ 운전점이 없습니다: 부하 토크 {u.TL:.1f} N·m 가 최대 토크 {Tmax:.1f} N·m 보다 커서 전동기가 멈춥니다(스톨).")
    elif op.I1 > 1.2 * params["I_rated"]:
        st.warning(f"상전류 {op.I1:.1f} A 가 정격 {params['I_rated']:.0f} A 를 넘습니다.")
    c1, c2 = st.columns([3, 2])
    with c1:
        s, n, T, I1 = _tn_curve(m, u)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for (lo, hi, name, col) in ((ns, 1.6 * ns, "발전기 (s < 0)", "rgba(42,157,143,0.07)"),
                                    (0, ns, "전동기 (0 < s < 1)", "rgba(38,70,83,0.05)"),
                                    (-0.6 * ns, 0, "역상 제동 (s > 1)", "rgba(231,111,81,0.07)")):
            fig.add_vrect(x0=lo, x1=hi, fillcolor=col, line_width=0, annotation_text=name,
                          annotation_position="top left", annotation_font_size=11)
        fig.add_trace(go.Scatter(x=n, y=T, name="토크 T", line=dict(color=PALETTE["speed"], width=3)), secondary_y=False)
        fig.add_trace(go.Scatter(x=n, y=I1, name="상전류 I₁ (실효)", line=dict(color=PALETTE["ia"], dash="dot")), secondary_y=True)
        nl = np.linspace(0, ns, 30)
        fig.add_trace(go.Scatter(x=nl, y=u.TL + params["B"] * nl / 9.5493, name="부하선", line=dict(color=PALETTE["TL"], dash="dash")), secondary_y=False)
        if op:
            fig.add_trace(go.Scatter(x=[op.rpm], y=[op.T], mode="markers", name="운전점", marker=dict(size=13, color="#e76f51", symbol="diamond")), secondary_y=False)
        fig.add_trace(go.Scatter(x=[(1 - smax) * ns], y=[Tmax], mode="markers+text", text=["  최대 토크"], textposition="middle right",
                                 marker=dict(size=9, color="#7c3aed"), showlegend=False), secondary_y=False)
        style(fig, 430, xaxis_title="속도 [rpm]", hovermode="closest", title=dict(text="토크–속도 특성 (슬립 −0.6 ~ 1.6)", x=0))
        fig.update_yaxes(title_text="토크 [N·m]", secondary_y=False)
        fig.update_yaxes(title_text="전류 [A]", showgrid=False, secondary_y=True)
        st.plotly_chart(fig, width="stretch")
    with c2:
        k = st.columns(2)
        if op:
            info_metric(k[0], "속도", f"{op.rpm:.1f} rpm", f"슬립 {op.s * 100:.2f} %")
            info_metric(k[1], "상전류 I₁", f"{op.I1:.2f} A", f"역률 {op.pf:.3f}")
            info_metric(k[0], "효율", f"{op.eta * 100:.1f} %")
            info_metric(k[1], "출력", f"{op.P_out / 1e3:.2f} kW")
        info_metric(k[0], "최대 토크", f"{Tmax:.1f} N·m", f"슬립 {smax * 100:.1f} % 에서")
        info_metric(k[1], "기동 토크", f"{Tst:.1f} N·m")
        info_metric(k[0], "기동 전류", f"{Ist:.1f} A", f"정격의 {Ist / params['I_rated']:.1f} 배")
        info_metric(k[1], "회전자 전류 주파수", f"{(op.s * u.f if op else 0):.2f} Hz", "= s·f")
        with st.expander("계산식"):
            st.latex(r"Z = R_s + jX_{ls} + \frac{jX_m\,(R_r'/s + jX_{lr}')}{R_r'/s + j(X_m + X_{lr}')}")
            st.latex(r"T_{max} = \frac{3 V_{th}^2}{2\omega_s\left(R_{th} + \sqrt{R_{th}^2 + (X_{th} + X_{lr}')^2}\right)},\quad"
                     r"s_{max} = \frac{R_r'}{\sqrt{R_{th}^2 + (X_{th}+X_{lr}')^2}}")
    if op:
        st.markdown("#### 전력 흐름")
        Pag = op.T * m.ws(u)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=["입력"], x=[op.P_in], orientation="h", name="입력", marker_color="#1d3557", text=[f"{op.P_in:.0f} W"], textposition="inside"))
        items = [("출력 (축)", op.P_out, "#2a9d8f"), ("기계손", op.losses["기계손 (Bω²)"], "#adb5bd"),
                 ("회전자 동손 s·Pag", op.losses["회전자 동손 (s·Pag)"], "#f4a261"), ("고정자 동손", op.losses["고정자 동손"], "#e76f51")]
        for name, v, col in items:
            fig.add_trace(go.Bar(y=["출력 + 손실"], x=[v], orientation="h", name=name, marker_color=col, text=[f"{v:.0f} W"], textposition="inside"))
        style(fig, 220, barmode="stack", xaxis_title="전력 [W]", hovermode="closest")
        st.plotly_chart(fig, width="stretch")
        st.caption(f"공극 전력 Pag = {Pag:.0f} W 중 s·Pag 는 회전자 동손, (1 − s)·Pag 는 기계 출력이 됩니다 (철손 무시).")

    st.markdown("#### V/f 제어: 주파수에 따른 토크–속도 곡선")
    c = st.columns([3, 1])
    with c[1]:
        boost = st.slider("저주파 전압 보상 [V]", 0, 60, 0, key="im_boost",
                          help="낮은 주파수에서 고정자 저항 강하를 보상하려고 전압을 조금 더 줍니다.")
        st.caption("정격 주파수까지는 V ∝ f (자속 일정), 그 위는 전압이 정격으로 고정되어 **약계자** 영역이 됩니다.")
    with c[0]:
        fig = go.Figure()
        cols = ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51", "#8e44ad", "#7b8794"]
        for i, fr in enumerate([0.25, 0.5, 0.75, 1.0, 1.25, 1.5]):
            f = u.f * fr
            V = min(u.V, u.V * fr + boost * max(0, 1 - fr))
            uu = replace(u, f=f, V=V)
            s, n, T, _ = _tn_curve(m, uu, -0.05, 1.0, 400)
            fig.add_trace(go.Scatter(x=n, y=T, name=f"{f:.0f} Hz, {V:.0f} V", line=dict(color=cols[i], width=2.5)))
        fig.add_hline(y=u.TL, line=dict(color=PALETTE["TL"], dash="dash"), annotation_text="부하 토크")
        style(fig, 380, xaxis_title="속도 [rpm]", yaxis_title="토크 [N·m]", hovermode="closest")
        st.plotly_chart(fig, width="stretch")

    st.markdown("#### 회전자 저항의 영향 (권선형 유도전동기의 2차 저항 제어)")
    fig = go.Figure()
    for k_, col in zip([1, 2, 4, 8], ["#264653", "#2a9d8f", "#f4a261", "#e76f51"]):
        mm = registry.get("induction")(dict(params, Rr=params["Rr"] * k_))
        s, n, T, _ = _tn_curve(mm, u, 0.001, 1.0, 300)
        fig.add_trace(go.Scatter(x=n, y=T, name=f"Rr′ × {k_}", line=dict(color=col, width=2.5)))
    style(fig, 330, xaxis_title="속도 [rpm]", yaxis_title="토크 [N·m]", hovermode="closest")
    st.plotly_chart(fig, width="stretch")
    st.caption("회전자 저항을 키우면 최대 토크는 그대로이고 최대 토크가 나는 슬립이 커집니다 → 기동 토크가 커지고 기동 전류는 줄어듭니다.")


# ---------------------------------------------------------------- ③ 동특성
@st.cache_data(max_entries=20, show_spinner="동특성 계산 중…")
def _run(params_items, V0, f0, t_end, events):
    from motors.ac.induction import IMInputs
    m = registry.get("induction")(dict(params_items))
    u0 = IMInputs(V=V0, f=f0, TL=0.0)
    evs = [Event(t, dict(ch), lab) for t, ch, lab in events]
    return simulate(m, u0, t_end, events=evs, n_points=6000, max_step=2e-4)


def _preset(name):
    ss = st.session_state
    ss.ims_start = {"direct": "직입 기동", "yd": "Y-Δ 기동", "freq": "직입 기동"}[name]
    ss.ims_chg = name == "freq"


def tab_dynamic(m, params):
    ss = st.session_state
    st.caption("정지 상태에서 기동 → 부하 인가 → (선택) 주파수 변경. 자속 모델을 solve_ivp 로 풉니다.")
    for k, v in {"ims_start": "직입 기동", "ims_chg": False}.items():
        ss.setdefault(k, v)
    p = st.columns(3)
    p[0].button("직입 기동", on_click=_preset, args=("direct",), width="stretch")
    p[1].button("Y-Δ 기동 (감전압)", on_click=_preset, args=("yd",), width="stretch")
    p[2].button("운전 중 주파수 변경 (V/f)", on_click=_preset, args=("freq",), width="stretch")
    c = st.columns(4)
    t_end = c[0].number_input("시뮬레이션 시간 [s]", 0.2, 10.0, 2.0, 0.1, key="ims_tend")
    start = c[0].radio("기동 방식", ["직입 기동", "Y-Δ 기동"], key="ims_start",
                       help="Y-Δ: 기동 때 상전압이 1/√3 → 기동 전류·토크가 1/3")
    t_yd = c[1].number_input("Y → Δ 전환 시각 [s]", 0.0, 10.0, 0.8, 0.1, key="ims_tyd", disabled=start != "Y-Δ 기동")
    t_load = c[1].number_input("부하 인가 시각 [s]", 0.0, 10.0, 1.0, 0.1, key="ims_tl")
    TL = c[2].number_input("부하 토크 [N·m]", 0.0, 1000.0, float(params["TL"]), 1.0, key="ims_TL")
    chg = c[3].checkbox("주파수 변경", key="ims_chg")
    t_f = c[3].number_input("변경 시각 [s]", 0.0, 10.0, 1.5, 0.1, key="ims_tf", disabled=not chg)
    f1 = c[3].number_input("새 주파수 [Hz] (V/f 일정)", 1.0, 200.0, 0.75 * params["f"], 1.0, key="ims_f1", disabled=not chg)
    V0 = params["V"] / math.sqrt(3) if start == "Y-Δ 기동" else params["V"]
    events = [(t_load, (("TL", TL),), "부하 인가")]
    if start == "Y-Δ 기동":
        events.append((t_yd, (("V", params["V"]),), "Y→Δ"))
    if chg:
        events.append((t_f, (("f", f1), ("V", min(params["V"], params["V"] * f1 / params["f"]))), f"f → {f1:.0f} Hz"))
    r = _run(tuple(sorted(params.items())), V0, params["f"], t_end, tuple(events))
    I_r = params["I_rated"]
    ipk = float(np.max(np.abs(r["ia"])))
    k = st.columns(4)
    info_metric(k[0], "최대 상전류 (순시)", f"{ipk:.1f} A", f"정격 실효값의 {ipk / I_r:.1f} 배")
    tl_mask = r.t < t_load
    if tl_mask.any():
        w95 = 0.95 * r["rpm"][tl_mask][-1]
        j = np.argmax(r["rpm"] >= w95) if np.any(r["rpm"] >= w95) else None
        info_metric(k[1], "기동 시간 (무부하 95 %)", f"{r.t[j]:.2f} s" if j else "—")
    info_metric(k[2], "최종 속도", f"{r['rpm'][-1]:.1f} rpm", f"슬립 {r['slip'][-1] * 100:.2f} %")
    info_metric(k[3], "최종 상전류", f"{r['Is'][-1]:.1f} A (실효)")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=("속도 [rpm]", "상전류 [A]", "토크 [N·m]", "상전류 실효값 [A]"))
    t = r.t
    fig.add_trace(go.Scatter(x=t, y=120 * r["f"] / params["poles"], name="동기속도", line=dict(color="#9aa0a6", dash="dash")), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=r["rpm"], name="속도", line=dict(color=PALETTE["speed"])), 1, 1)
    for i, ph in enumerate("abc"):
        fig.add_trace(go.Scatter(x=t, y=r["i" + ph], name=f"i{ph}", line=dict(color=PCOL[i], width=1)), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=r["Te"], name="Te", line=dict(color=PALETTE["Te"], width=1.2)), 3, 1)
    fig.add_trace(go.Scatter(x=t, y=r["TL"], name="TL", line=dict(color=PALETTE["TL"], dash="dash")), 3, 1)
    fig.add_trace(go.Scatter(x=t, y=r["Is"], name="Is", line=dict(color=PALETTE["ia"])), 4, 1)
    fig.add_hline(y=I_r, line=dict(color="#bbb", dash="dot"), row=4, col=1, annotation_text="정격")
    style(fig, 950, side_legend=True)
    mark_events(fig, r.events, rows=range(1, 5))
    fig.update_xaxes(title_text="시간 [s]", row=4, col=1)
    st.plotly_chart(fig, width="stretch")
    st.caption("직입 기동 초기에는 전류에 직류 성분이 섞여 비대칭이고, 토크도 크게 진동합니다 (전기적 과도 현상).")


# ---------------------------------------------------------------- ④ 제어
def tab_control(m, params):
    st.markdown("#### 제어 구조")
    st.markdown("""
- **V/f 제어 (개루프)**: 속도 지령 → 주파수 f* = (P/2)·n*/60 → 전압 V = V정격·f/f정격 (+저주파 보상) → 인버터.
  부하가 걸리면 슬립만큼 속도가 처집니다. **슬립 보상**은 토크로 슬립 주파수를 추정해 더해 줍니다.
- **벡터 제어 (간접 FOC)**: 회전자 자속 방향을 d축으로 잡아 **id 로 자속, iq 로 토크**를 따로 제어합니다 (DC 전동기의 계자·전기자 전류처럼).
  자속 각은 θe = ∫(ωr + ωsl) dt, 미끄럼 주파수 ωsl = iq* / (τr·id*), τr = Lr/Rr.
  속도 PI → iq* (전류 제한) → dq 전류 PI (+비간섭) → 전압 → 인버터.
""")
    st.latex(r"T_e = \frac{3}{2}\frac{P}{2}\frac{L_m^2}{L_r}\, i_d\, i_q,\qquad \omega_{sl} = \frac{R_r}{L_r}\frac{i_q}{i_d}")
    realtime.render(realtime.im_control_html(m), height=860)
    with st.expander("해 볼 실험", expanded=False):
        st.markdown("""
1. **V/f vs 벡터 제어**: 같은 속도 지령에서 부하를 올려 보세요. V/f 는 속도가 처지고, 벡터 제어는 지령으로 돌아옵니다.
2. **슬립 보상**: 'V/f + 슬립 보상'을 고르면 부하가 걸려도 주파수가 조금 올라가 속도가 유지됩니다 (주파수 그래프).
3. **기동 전류**: 벡터 제어는 전류 제한 덕분에 직입 기동(6~7 배)보다 기동 전류가 훨씬 작습니다.
4. **약계자**: 정격(동기)속도보다 높은 지령을 주면 id 가 줄어들며 속도가 올라갑니다.
5. **역회전**: 음의 속도 지령 → 회전자계 방향이 바뀌어 역회전합니다.
""")


def render():
    st.title("🌀 유도전동기 시뮬레이터")
    st.caption("3상 농형 유도전동기. 회전자계와 슬립, 등가회로 특성, 직입 기동, V/f·벡터 제어를 다룹니다.")
    cls = registry.get("induction")
    params, errors = render_params(cls)
    if errors:
        st.error("파라미터에 맞지 않는 값이 있습니다.\n\n" + "\n".join(f"- {e}" for e in errors))
        st.stop()
    m = cls(params)
    tabs = st.tabs(["① 원리 이해", "② 정상상태 특성", "③ 동특성 (시간 응답)", "④ 제어"])
    with tabs[0]:
        tab_principle(m, params)
    with tabs[1]:
        tab_steady(m, params)
    with tabs[2]:
        tab_dynamic(m, params)
    with tabs[3]:
        tab_control(m, params)
    st.divider()
    st.caption(ASSUMPTIONS)
