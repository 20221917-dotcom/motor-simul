"""BLDC 전동기 페이지: 원리(실시간) · 정상상태 · 동특성 · 제어(실시간)."""
from dataclasses import replace
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.units import to_rpm
from motors import registry
import motors.bldc.model  # noqa: F401  (모델 등록 보장)
from ui import realtime
from ui.params_panel import render_params
from ui import structure_tab
from ui.plots import info_metric, style, PALETTE

PCOL = ["#d62828", "#2a9d3a", "#1d4ed8"]
ASSUMPTIONS = ("**모델 가정** · 3상 Y결선, 상 저항·인덕턴스 동일 (L 은 자기 인덕턴스 − 상호 인덕턴스), "
               "사다리꼴 역기전력(평탄부 120°), 홀 센서 6스텝 120° 통전, 인버터는 평균값 PWM "
               "(스위칭 리플 무시) + 이상적 스위치·환류 다이오드, 자기포화·철손·코깅 토크 무시. "
               "속도는 rpm 으로 표시하고 계산은 SI 단위입니다.")


@st.cache_data(max_entries=20, show_spinner="3상 파형 계산 중…")
def _sim(params_items, u_items, t_end, events, record_dt):
    m = registry.get("bldc")(dict(params_items))
    from motors.bldc.model import BLDCInputs
    return m.simulate_fixed(BLDCInputs(**dict(u_items)), t_end, h=1e-5,
                            events=[(t, dict(c)) for t, c in events], record_dt=record_dt)


def _items(d):
    return tuple(sorted(d.items()))


# ---------------------------------------------------------------- ① 원리
def tab_principle(m, params):
    left, right = st.columns([3, 1])
    with left:
        st.markdown("#### 실시간 동작 (6스텝 정류)")
        st.caption("홀 센서가 회전자 위치를 읽고, 그 코드에 따라 인버터 스위치 2개를 켜서 두 상에 전류를 흘립니다. "
                   "60°(전기각)마다 통전 상이 바뀌며 고정자 자계가 한 칸씩 앞으로 뛰어 회전자를 끌고 갑니다. "
                   "슬라이더를 바꾸면 현재 상태에서 바로 반응합니다.")
    with right:
        st.markdown("**핵심 수식**")
        st.latex(r"L\frac{di_x}{dt} = v_x - v_n - R\,i_x - e_x")
        st.latex(r"e_x = k_e\,\omega_m\, f(\theta_e - \varphi_x)")
        st.latex(r"T_e = \frac{e_a i_a + e_b i_b + e_c i_c}{\omega_m}")
        st.latex(r"\theta_e = \tfrac{P}{2}\,\theta_m")
    realtime.render(realtime.bldc_principle_html(params), height=1180)
    with st.expander("그림 읽는 법 · DC 전동기와 비교", expanded=False):
        st.markdown("""
- **기계식 정류자 → 전자식 정류**: DC 전동기는 정류자·브러시가 코일 전류를 뒤집었지만, BLDC 는
  **홀 센서 + 인버터 스위치**가 그 일을 합니다. 그래서 브러시가 없고 (Brushless) 수명이 깁니다.
- 각 순간 **두 상만 통전**합니다 (+ 쪽 상 → − 쪽 상). 역기전력이 평탄한 구간에 전류를 흘려 토크가 거의 일정합니다:
  Te = 2·ke·I (DC 전동기의 Kφ 자리에 2ke).
- **정류 리플**: 통전 상이 바뀌는 순간, 꺼진 상의 전류는 인덕턴스 때문에 바로 0 이 되지 못하고 **환류 다이오드**(주황)로 흐르며 줄어듭니다.
  그 사이 토크가 출렁입니다. L 이 크거나 속도가 빠를수록 커집니다.
- **홀 센서 위치 오차**: 슬라이더로 센서를 옮기면 정류가 이르거나 늦어져 토크 리플이 커지고 같은 전압에서 속도·효율이 변합니다.
- **보라 화살표**(고정자 자계)가 회전자 N 방향보다 **60°~120° 앞서** 있어야 회전 방향으로 끌어당기는 토크가 납니다 (90° 에서 최대).
""")
    st.divider()
    _structure_section(m, params)


def _structure_section(m, params):
    st.markdown("#### BLDC 구조와 특징 · DC 전동기와 비교")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(f"""
| 항목 | DC 전동기 (타여자·분권) | BLDC 전동기 |
|---|---|---|
| 자계를 만드는 쪽 | 고정자 계자 권선 (또는 영구자석) | **회전자 영구자석** ({params['poles']:.0f}극) |
| 전류가 흐르는 쪽 | 회전자 (전기자) | **고정자 3상 권선** |
| 전류 방향 바꾸기 | 정류자 + 브러시 (기계식) | **홀 센서 + 인버터 스위치 6개** (전자식) |
| 토크 식 | Te = Kφ·Ia | Te = 2ke·I (두 상 도통) |
| 역기전력 | E = Kφ·ω | 선간 2ke·ω (평탄 구간) |
| 속도 제어 | 전기자 전압 | PWM 듀티 (d·Vdc) |
| 토크 리플 원인 | 정류자편 수 | 6스텝 **정류 리플** (60° 마다) |
| 유지보수 | 브러시 마모·불꽃 | 브러시 없음, 수명 김 |
""")
    with c2:
        st.markdown(f"""
**이 전동기 값으로 보면**
- 등가 토크 상수 K = 2ke = **{m.K:.3f} N·m/A**
- 무부하 속도 ≈ Vdc / 2ke = **{params['Vdc'] / m.K * 60 / (2 * np.pi):.0f} rpm**
- 기동 전류 = Vdc / 2R = **{params['Vdc'] / (2 * params['R']):.1f} A**
- 선간 전기 시정수 L/R = **{params['L'] / params['R'] * 1000:.2f} ms**
- 기계 시정수 J·2R/K² = **{params['J'] * 2 * params['R'] / m.K ** 2 * 1000:.1f} ms**

평균적으로는 **DC 전동기와 같은 식**으로 움직입니다 (② 정상상태 탭).
차이는 60° 마다 일어나는 정류 과정과 그때 생기는 토크 리플입니다.
""")


# ---------------------------------------------------------------- ② 정상상태
def tab_steady(m, params):
    u = m.default_inputs()
    op, nl = m.steady_state(u), m.no_load(u)
    st.caption(f"평균 모델 (듀티 100 %, Vdc = {params['Vdc']:.0f} V, TL = {params['TL']:.3g} N·m). "
               "평탄 구간에서 두 상이 직렬로 도통한다고 보면 DC 전동기와 같은 식이 됩니다.")
    st.latex(r"V = d\,V_{dc} = 2R\,I + 2k_e\,\omega,\qquad T_e = 2k_e\,I"
             r"\;\Rightarrow\; \omega = \frac{V}{2k_e} - \frac{2R}{(2k_e)^2}\,T_e")
    if op is None:
        st.error("운전점이 없습니다: 기동 토크(2ke·Vdc/2R)보다 부하 토크가 큽니다.")
        return
    if op.I > 1.5 * params["I_rated"]:
        st.warning(f"상전류 {op.I:.1f} A 가 정격 {params['I_rated']:.0f} A 를 크게 넘습니다.")
    c1, c2 = st.columns([3, 2])
    with c1:
        te, w, _ = m.speed_torque_curve(u, I_max=3 * params["I_rated"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=te, y=to_rpm(w), name="평균 모델 속도–토크", line=dict(color=PALETTE["speed"], width=3)))
        wl = np.linspace(0, max(w), 40)
        fig.add_trace(go.Scatter(x=params["TL"] + params["B"] * wl, y=to_rpm(wl), name="부하선 TL + Bω",
                                 line=dict(color=PALETTE["TL"], dash="dash")))
        fig.add_trace(go.Scatter(x=[op.Te], y=[op.rpm], mode="markers", name="운전점 (평균 모델)",
                                 marker=dict(size=13, color=PALETTE["ia"], symbol="diamond")))
        sim = _steady_sim(m, params)
        fig.add_trace(go.Scatter(x=[sim["Te_mean"]], y=[sim["rpm"]], mode="markers", name="운전점 (3상 시뮬레이션)",
                                 marker=dict(size=12, color="#7c3aed", symbol="x")))
        style(fig, 400, xaxis_title="토크 [N·m]", yaxis_title="속도 [rpm]", hovermode="closest",
              title=dict(text="속도–토크 특성", x=0))
        fig.update_yaxes(range=[0, to_rpm(max(w)) * 1.1])
        st.plotly_chart(fig, width="stretch")
    with c2:
        k = st.columns(2)
        info_metric(k[0], "속도 (평균 모델)", f"{op.rpm:.0f} rpm")
        info_metric(k[1], "속도 (3상 시뮬레이션)", f"{sim['rpm']:.0f} rpm", f"차이 {(sim['rpm'] - op.rpm) / op.rpm * 100:+.1f} %")
        info_metric(k[0], "상전류 (통전 중)", f"{op.I:.2f} A")
        info_metric(k[1], "토크 리플 (p-p / 평균)", f"{sim['ripple']:.0f} %")
        info_metric(k[0], "무부하 속도", f"{nl.rpm:.0f} rpm" if nl else "—")
        info_metric(k[1], "효율 (평균 모델)", f"{op.eta * 100:.1f} %")
        info_metric(k[0], "전기 주파수", f"{op.omega * m.pp / (2 * np.pi):.0f} Hz", f"극수 {params['poles']:.0f}")
        info_metric(k[1], "기동 전류 Vdc/2R", f"{params['Vdc'] / (2 * params['R']):.1f} A")
        st.caption("평균 모델은 정류 순간을 무시합니다. 3상 시뮬레이션은 정류 때 전류가 늦게 바뀌는 효과까지 넣어서 "
                   "속도가 조금 낮게 나옵니다. 상 인덕턴스 L 을 키워 보면 차이가 커집니다.")
    st.markdown("#### 정상상태 3상 파형 (전기각 2주기)")
    r = sim["wave"]
    th = np.unwrap(r["theta_e"]); x = np.rad2deg(th - th[0])
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("상 역기전력 [V]", "상전류 [A]", "토크 [N·m]"))
    for k, ph in enumerate("abc"):
        fig.add_trace(go.Scatter(x=x, y=r["e" + ph], name=f"e{ph}", line=dict(color=PCOL[k])), 1, 1)
        fig.add_trace(go.Scatter(x=x, y=r["i" + ph], name=f"i{ph}", line=dict(color=PCOL[k])), 2, 1)
    fig.add_trace(go.Scatter(x=x, y=r["Te"], name="Te", line=dict(color=PALETTE["Te"])), 3, 1)
    fig.add_trace(go.Scatter(x=x, y=r["TL"], name="TL", line=dict(color=PALETTE["TL"], dash="dash")), 3, 1)
    style(fig, 620, side_legend=True)
    fig.update_xaxes(title_text="전기각 [°]", dtick=60, row=3, col=1)
    st.plotly_chart(fig, width="stretch")
    st.caption("60° 마다 통전 상이 바뀌고, 그때마다 꺼지는 상의 전류가 환류하며 줄어드는 동안 토크가 출렁입니다 (정류 리플).")

    # 부하 토크에 따른 전류·효율 (평균 모델)
    TLs = np.linspace(0, 2 * m.rated_torque(), 40)
    ops = [m.steady_state(replace(u, TL=float(T))) for T in TLs]
    pts = [(T, o.I, o.eta * 100, o.rpm) for T, o in zip(TLs, ops) if o]
    if pts:
        T_, I_, e_, n_ = map(np.array, zip(*pts))
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=T_, y=I_, name="상전류 [A]", line=dict(color=PALETTE["ia"], width=3)), secondary_y=False)
        fig.add_trace(go.Scatter(x=T_, y=e_, name="효율 [%]", line=dict(color=PALETTE["Te"], width=3)), secondary_y=True)
        style(fig, 320, xaxis_title="부하 토크 [N·m]", title=dict(text="부하 토크에 따른 전류와 효율 (평균 모델)", x=0))
        fig.update_yaxes(title_text="전류 [A]", secondary_y=False)
        fig.update_yaxes(title_text="효율 [%]", range=[0, 100], tickmode="linear", dtick=20, showgrid=False, secondary_y=True)
        st.plotly_chart(fig, width="stretch")


def _steady_sim(m, params):
    u = m.default_inputs()
    op = m.steady_state(u)
    # 정상상태에 이를 만큼 돌린 뒤 마지막 전기각 2주기를 잘라 본다
    t_set = max(0.15, 8 * params["J"] * 2 * params["R"] / (2 * params["ke"]) ** 2)
    r = _sim(_items(m.p), _items({"duty": 1.0, "TL": params["TL"], "hall_offset": 0.0, "friction": False}),
             t_set, (), 2e-5)
    w_end = max(r["omega"][-1], 1.0)
    T2 = 2 * 2 * np.pi / (w_end * m.pp)
    k = r["t"] >= r["t"][-1] - T2
    wave = {key: v[k] for key, v in r.items()}
    Te = wave["Te"]
    return {"wave": wave, "rpm": float(np.mean(wave["rpm"])), "Te_mean": float(np.mean(Te)),
            "ripple": float((Te.max() - Te.min()) / max(abs(Te.mean()), 1e-9) * 100), "op": op}


# ---------------------------------------------------------------- ③ 동특성
def tab_dynamic(m, params):
    st.caption("정지 상태에서 기동 → 부하 인가 → 듀티 변경. 3상 회로를 10 µs 간격으로 계산합니다 (계산에 몇 초 걸릴 수 있음).")
    c = st.columns(4)
    t_end = c[0].number_input("시뮬레이션 시간 [s]", 0.02, 1.0, 0.2, 0.02, key="bd_tend")
    d0 = c[0].slider("기동 듀티 [%]", 5, 100, 100, key="bd_d0")
    t_load = c[1].number_input("부하 인가 시각 [s]", 0.0, 1.0, 0.1, 0.01, key="bd_tl")
    TL = c[1].number_input("부하 토크 [N·m]", 0.0, 100.0, float(params["TL"]), 0.05, key="bd_TL")
    t_d = c[2].number_input("듀티 변경 시각 [s]", 0.0, 1.0, 0.15, 0.01, key="bd_td")
    d1 = c[2].slider("변경 후 듀티 [%]", -100, 100, 60, key="bd_d1")
    ho = c[3].slider("홀 센서 오차 [° 전기각]", -40, 40, 0, key="bd_ho")
    fric = c[3].checkbox("마찰형 부하", value=True, key="bd_fric")
    events = [(t_load, (("TL", TL),)), (t_d, (("duty", d1 / 100),))]
    r = _sim(_items(m.p), _items({"duty": d0 / 100, "TL": 0.0, "hall_offset": float(np.deg2rad(ho)),
                                   "friction": fric}), t_end, tuple(events), 5e-5)
    I_r = params["I_rated"]
    ipk = float(np.max(np.abs([r["ia"], r["ib"], r["ic"]])))
    k = st.columns(4)
    info_metric(k[0], "최대 상전류", f"{ipk:.1f} A", f"정격의 {ipk / I_r:.1f} 배")
    info_metric(k[1], "최종 속도", f"{r['rpm'][-1]:.0f} rpm")
    seg = (r["t"] > t_load + 0.3 * (t_d - t_load)) & (r["t"] < t_d) if t_d > t_load else r["t"] > t_load
    if seg.any():
        Te = r["Te"][seg]
        info_metric(k[2], "부하 중 토크 리플", f"{(Te.max() - Te.min()) / max(abs(Te.mean()), 1e-9) * 100:.0f} %")
        info_metric(k[3], "부하 중 평균 속도", f"{np.mean(r['rpm'][seg]):.0f} rpm")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=("속도 [rpm]", "상전류 [A]", "토크 [N·m]", "상 역기전력 [V]"))
    t = r["t"] * 1000
    fig.add_trace(go.Scatter(x=t, y=r["rpm"], name="속도", line=dict(color=PALETTE["speed"])), 1, 1)
    for i, ph in enumerate("abc"):
        fig.add_trace(go.Scatter(x=t, y=r["i" + ph], name=f"i{ph}", line=dict(color=PCOL[i], width=1)), 2, 1)
        fig.add_trace(go.Scatter(x=t, y=r["e" + ph], name=f"e{ph}", line=dict(color=PCOL[i], width=1), showlegend=False), 4, 1)
    fig.add_trace(go.Scatter(x=t, y=r["Te"], name="Te", line=dict(color=PALETTE["Te"], width=1)), 3, 1)
    fig.add_trace(go.Scatter(x=t, y=r["TL"], name="TL", line=dict(color=PALETTE["TL"], dash="dash")), 3, 1)
    for ev, lab in ((t_load, "부하 인가"), (t_d, f"듀티 → {d1}%")):
        if 0 < ev < t_end:
            for row in range(1, 5):
                fig.add_vline(x=ev * 1000, line=dict(color="#999", dash="dot", width=1), row=row, col=1)
            fig.add_annotation(x=ev * 1000, y=1.0, yref="paper", text=lab, showarrow=False, yanchor="bottom",
                               font=dict(size=11, color="#666"))
    style(fig, 900, side_legend=True)
    fig.update_xaxes(title_text="시간 [ms]", row=4, col=1)
    st.plotly_chart(fig, width="stretch")
    if d1 < 0:
        st.info("듀티를 음수로 바꾸면 통전 순서가 반대가 되어 제동 → 역회전합니다 (4상한 인버터).")


# ---------------------------------------------------------------- ④ 제어
def tab_control(m, params):
    st.markdown("#### 제어 구조")
    st.markdown("**ω\\*** → (Σ) → **속도 PI** → **토크 전류 제한 ±I_lim** → **I\\*** → (Σ) → **전류 PI** (+ 2ke·ω 피드포워드) "
                "→ **듀티 d = v\\*/Vdc** → **6스텝 인버터** (홀 센서로 통전 상 선택) → **BLDC**  "
                "· 피드백: 속도 ω, 토크 전류 Te/2ke")
    st.caption("DC 전동기 제어와 같은 이중 루프입니다. 전류 루프 플랜트가 두 상 직렬(2R, 2L)이라 "
               "추천 게인은 Kpi = ωci·2L, Kii = ωci·2R 입니다. 토크 전류는 상전류와 역기전력 모양으로 계산한 Te/(2ke) 를 씁니다.")
    realtime.render(realtime.bldc_control_html(params), height=860)
    st.info("🧩 제어 구조를 직접 바꿔 보려면 왼쪽 메뉴 **제어 실습 → 제어 블록 편집기**에서 "
            "'BLDC:' 템플릿을 불러와 블록을 바꿔 보세요 (P/PI/PID, 전류 루프만, 개루프 등).")
    with st.expander("해 볼 실험", expanded=False):
        st.markdown("""
1. **기동**: 처음부터 다시 → 전류가 I_lim 에 붙은 채 일정하게 가속합니다.
2. **부하 외란**: TL 을 올리면 속도가 잠깐 처졌다가 돌아오고, 토크에 정류 리플이 보입니다.
3. **역회전**: 빠른 버튼으로 음의 속도 지령 → 듀티가 음수가 되어 통전 순서가 반대로 바뀝니다.
4. **홀 센서 오차**: 20~30° 로 옮기면 같은 토크에 더 큰 전류가 필요하고 리플이 커집니다.
5. **피드포워드 끄기 / 게인 바꾸기**: 전류 응답이 느려지거나 진동하는지 보세요.
""")


def render():
    st.title("⚡ BLDC 전동기 시뮬레이터")
    st.caption("3상 BLDC 전동기 (사다리꼴 역기전력, 홀 센서 6스텝 정류). "
               "DC 전동기의 정류자·브러시를 홀 센서와 인버터 스위치로 바꾼 전동기라고 볼 수 있습니다.")
    cls = registry.get("bldc")
    params, errors = render_params(cls)
    if errors:
        st.error("파라미터에 맞지 않는 값이 있습니다.\n\n" + "\n".join(f"- {e}" for e in errors))
        st.stop()
    m = cls(params)
    tabs = st.tabs(["① 원리 이해", "② 정상상태 특성", "③ 동특성 (시간 응답)", "④ 제어", "⑤ 구조 살펴보기"])
    with tabs[0]:
        tab_principle(m, params)
    with tabs[1]:
        tab_steady(m, params)
    with tabs[2]:
        tab_dynamic(m, params)
    with tabs[3]:
        tab_control(m, params)
    with tabs[4]:
        structure_tab.render_bldc(params)
    st.divider()
    st.caption(ASSUMPTIONS)
