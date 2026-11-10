"""탭 4. 속도 제어 (타여자 기준, 이중 루프)"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from control.cascade import ControlConfig, run_cascade
from control.tuning import current_gains, speed_gains
from core.units import to_rad_s, to_rpm
from ui import realtime
from ui.diagrams import control_block_diagram
from ui.plots import info_metric, style, PALETTE


def _kphi(model, params):
    """제어 모델에 쓸 Kφ. 타여자·분권은 일정, 직권·복권은 정격 전류에서의 값으로 고정."""
    u = model.default_inputs()
    ia = 0.0 if model.excitation in ("separately", "shunt") else params["I_rated"]
    return float(model.kphi(ia, model.field_ss(ia, u)))


def _recommended(params, kphi):
    ss = st.session_state
    kpi, kii = current_gains(params["La"], params["Ra"], ss.ct_wci)
    kpw, kiw = speed_gains(params["J"], kphi, ss.ct_wcs)
    return kpw, kiw, kpi, kii


def _apply_rec(params, kphi):
    ss = st.session_state
    ss.ct_Kpw, ss.ct_Kiw, ss.ct_Kpi, ss.ct_Kii = (float(f"{v:.4g}") for v in
                                                  _recommended(params, kphi))


def _init_state(params, kphi):
    ss = st.session_state
    base = {"ct_r1": 1000.0, "ct_t2": 1.5, "ct_r2": -800.0, "ct_t3": 3.0, "ct_r3": 600.0,
            "ct_tend": 4.0, "ct_tload": 0.8, "ct_load_type": "마찰형 (회전 반대 방향)",
            "ct_quad": "4상한 (H-브리지)", "ct_Ilim": round(2 * params["I_rated"], 1),
            "ct_wci": 1000.0, "ct_wcs": 50.0, "ct_aw": True, "ct_ff": True, "ct_ol": True,
            "ct_Ts": 100}
    for k, v in base.items():
        if k not in ss:
            ss[k] = v
    if "ct_Kpw" not in ss:
        _apply_rec(params, kphi)


@st.cache_data(max_entries=30, show_spinner=False)
def _run(params_items, kphi, cfg_items, open_loop):
    cfg = ControlConfig(**dict(cfg_items))
    return run_cascade(dict(params_items), kphi, cfg, open_loop=open_loop)


def _settings(params, kphi):
    ss = st.session_state
    c = st.columns(4)
    with c[0]:
        st.markdown("**속도 지령 [rpm]**")
        st.number_input("t = 0 s 지령", -3000.0, 3000.0, step=50.0, key="ct_r1")
        a, b = st.columns(2)
        a.number_input("변경 시각 1 [s]", 0.0, 30.0, step=0.1, key="ct_t2")
        b.number_input("지령 2 [rpm]", -3000.0, 3000.0, step=50.0, key="ct_r2")
        a, b = st.columns(2)
        a.number_input("변경 시각 2 [s]", 0.0, 30.0, step=0.1, key="ct_t3")
        b.number_input("지령 3 [rpm]", -3000.0, 3000.0, step=50.0, key="ct_r3")
    with c[1]:
        st.markdown("**부하·초퍼**")
        st.number_input("시뮬레이션 시간 [s]", 0.2, 20.0, step=0.5, key="ct_tend")
        st.number_input(f"부하 인가 시각 [s] (TL = {params['TL']:.1f} N·m)", 0.0, 20.0,
                        step=0.1, key="ct_tload")
        st.radio("부하 종류", ["마찰형 (회전 반대 방향)", "위치에너지형 (방향 일정)"],
                 key="ct_load_type",
                 help="마찰형: TL·tanh(ω/1 rad/s). 위치에너지형(권상기 등): 회전 방향과 무관하게 일정")
        st.radio("초퍼", ["4상한 (H-브리지)", "1상한 (강압형)"], key="ct_quad", horizontal=True)
        st.number_input("전류 제한 I_lim [A]", 0.1, 10000.0, step=5.0, key="ct_Ilim")
    with c[2]:
        st.markdown("**게인**")
        a, b = st.columns(2)
        a.number_input("Kpω [A·s/rad]", 0.0, 1e5, step=0.1, key="ct_Kpw", format="%.4g")
        b.number_input("Kiω [A/rad]", 0.0, 1e7, step=1.0, key="ct_Kiw", format="%.4g")
        a.number_input("Kpi [V/A]", 0.0, 1e5, step=1.0, key="ct_Kpi", format="%.4g")
        b.number_input("Kii [V/(A·s)]", 0.0, 1e8, step=10.0, key="ct_Kii", format="%.4g")
        st.select_slider("제어 주기 Ts [µs]", [50, 100, 200, 500], key="ct_Ts")
    with c[3]:
        st.markdown("**대역폭 → 추천 게인**")
        st.number_input("전류 루프 ωci [rad/s]", 1.0, 1e5, step=100.0, key="ct_wci")
        st.number_input("속도 루프 ωcs [rad/s]", 0.1, 1e4, step=5.0, key="ct_wcs")
        kpw, kiw, kpi, kii = _recommended(params, kphi)
        st.caption(f"추천: Kpω={kpw:.3g}, Kiω={kiw:.3g}, Kpi={kpi:.3g}, Kii={kii:.3g}")
        st.button("추천 게인 적용", on_click=_apply_rec, args=(params, kphi),
                  width="stretch")
        st.checkbox("안티와인드업", key="ct_aw")
        st.checkbox("역기전력 피드포워드", key="ct_ff")
        st.checkbox("개루프 운전과 비교", key="ct_ol")
    if ss.ct_wcs > ss.ct_wci / 5:
        st.warning("속도 루프 대역폭이 전류 루프의 1/5 보다 큽니다. 두 루프가 간섭해 "
                   "진동하기 쉽습니다 (보통 ωcs ≤ ωci/10).")
    if ss.ct_wci * ss.ct_Ts * 1e-6 > 0.3:
        st.warning("전류 루프 대역폭이 제어 주기에 비해 너무 높습니다 (ωci·Ts > 0.3).")
    refs = sorted([(0.0, to_rad_s(ss.ct_r1)), (ss.ct_t2, to_rad_s(ss.ct_r2)),
                   (ss.ct_t3, to_rad_s(ss.ct_r3))])
    cfg = dict(t_end=ss.ct_tend, Ts=ss.ct_Ts * 1e-6, refs=tuple(refs), t_load=ss.ct_tload,
               TL=params["TL"], friction_load=ss.ct_load_type.startswith("마찰"),
               quadrants=4 if ss.ct_quad.startswith("4") else 1, I_lim=ss.ct_Ilim,
               Kp_w=ss.ct_Kpw, Ki_w=ss.ct_Kiw, Kp_i=ss.ct_Kpi, Ki_i=ss.ct_Kii,
               anti_windup=ss.ct_aw, emf_ff=ss.ct_ff)
    return cfg


def _plot(r, ro, cfg):
    t = r["t"]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.045,
                        subplot_titles=("속도 [rpm]", "전기자 전류 [A]", "전기자 전압 va [V]",
                                        "토크 [N·m]"))
    fig.add_trace(go.Scatter(x=t, y=to_rpm(r["w_ref"]), name="속도 지령 ω*",
                             line=dict(color=PALETTE["ref"], width=3, shape="hv")), 1, 1)
    if ro is not None:
        fig.add_trace(go.Scatter(x=ro["t"], y=to_rpm(ro["omega"]), name="개루프 속도",
                                 line=dict(color=PALETTE["ol"], dash="dash")), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=to_rpm(r["omega"]), name="실제 속도 (폐루프)",
                             line=dict(color=PALETTE["speed"])), 1, 1)

    if ro is not None:
        fig.add_trace(go.Scatter(x=ro["t"], y=ro["ia"], name="개루프 전류",
                                 line=dict(color=PALETTE["ol"], dash="dash")), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=r["ia_ref"], name="전류 지령 Ia*",
                             line=dict(color=PALETTE["ref"], width=2)), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=r["ia"], name="실제 전류 Ia",
                             line=dict(color=PALETTE["ia"])), 2, 1)
    lims = [cfg["I_lim"]] + ([-cfg["I_lim"]] if cfg["quadrants"] == 4 else [0.0])
    for y in lims:
        fig.add_hline(y=y, line=dict(color=PALETTE["lim"], dash="dot"), row=2, col=1)

    if ro is not None:
        fig.add_trace(go.Scatter(x=ro["t"], y=ro["va"], name="개루프 전압",
                                 line=dict(color=PALETTE["ol"], dash="dash")), 3, 1)
    fig.add_trace(go.Scatter(x=t, y=r["va"], name="va (폐루프)",
                             line=dict(color=PALETTE["V"])), 3, 1)
    fig.add_trace(go.Scatter(x=t, y=r["E"], name="E (역기전력)",
                             line=dict(color=PALETTE["E"], dash="dot")), 3, 1)

    fig.add_trace(go.Scatter(x=t, y=r["Te"], name="Te (전자기)",
                             line=dict(color=PALETTE["Te"])), 4, 1)
    fig.add_trace(go.Scatter(x=t, y=r["TL"], name="TL (부하)",
                             line=dict(color=PALETTE["TL"], dash="dash")), 4, 1)
    style(fig, 950, side_legend=True)
    fig.update_xaxes(title_text="시간 [s]", row=4, col=1)
    # 개루프 전류가 너무 커서 폐루프가 안 보이지 않도록 전류 축 범위 제한
    span = max(cfg["I_lim"] * 1.6, np.nanmax(np.abs(r["ia"])) * 1.3)
    fig.update_yaxes(range=[-span if cfg["quadrants"] == 4 else -0.1 * span, span],
                     row=2, col=1)
    return fig


def _summary(r, ro, cfg, params):
    c = st.columns(4)
    imax = np.max(np.abs(r["ia"]))
    info_metric(c[0], "폐루프 최대 전류", f"{imax:.1f} A", f"정격의 {imax / params['I_rated']:.1f} 배",)
    if ro is not None:
        iol = np.max(np.abs(ro["ia"]))
        info_metric(c[1], "개루프 최대 전류", f"{iol:.1f} A",
                    f"정격의 {iol / params['I_rated']:.1f} 배")
    err = to_rpm(r["w_ref"][-1] - r["omega"][-1])
    info_metric(c[2], "최종 속도 오차 (폐루프)", f"{err:.2f} rpm")
    if ro is not None:
        info_metric(c[3], "최종 속도 오차 (개루프)", f"{to_rpm(ro['w_ref'][-1] - ro['omega'][-1]):.1f} rpm")


def render(model, params):
    kphi = _kphi(model, params)
    if model.excitation != "separately":
        st.info(f"제어 탭은 **타여자 전동기** 기준입니다. 파라미터 설정의 전기자·기계 파라미터를 쓰고, "
                f"Kφ 는 선택한 {model.name} 전동기의 정격점 값 {kphi:.3f} V·s/rad 로 고정합니다 "
                "(계자를 따로 여자했다고 보는 등가 모델).")
    if kphi <= 0:
        st.error("Kφ 가 0 이하라 속도 제어를 할 수 없습니다. 파라미터를 확인하세요.")
        return
    _init_state(params, kphi)
    st.markdown("#### 제어 구조")
    st.plotly_chart(control_block_diagram(st.session_state.ct_ff), width="stretch",
                    config={"staticPlot": True})
    with st.expander("제어 구조와 게인 설계 설명", expanded=False):
        st.markdown("""
- **속도 PI** 가 속도 오차로 **전류 지령 Ia\\*** 를 만들고, **전류 제한**이 Ia\\* 를 ±I_lim 으로 자릅니다
  → 큰 속도 지령에도 전류가 제한값 이상 오르지 않아 기동 전류가 저절로 억제됩니다.
- **전류 PI** 가 전류 오차로 전압 지령을 만들고 **초퍼**가 평균 전압 va = d·Vdc 로 바꿉니다 (Vdc = 파라미터 설정의 V).
- **역기전력 피드포워드**: 전압 지령에 E = Kφω 를 미리 더해 주면 전류 PI 는 Ia·Ra + La·dIa/dt 만 담당하면 됩니다.
- **안티와인드업**: 출력이 포화된 동안 적분기를 멈춥니다. 끄면 포화 구간에 적분값이 쌓여 큰 오버슈트가 생깁니다.
- **1상한 초퍼**는 va ≥ 0, Ia ≥ 0 만 가능해서 역회전과 회생제동을 못 합니다.
""")
        st.latex(r"K_{pi} = \omega_{ci} L_a,\quad K_{ii} = \omega_{ci} R_a"
                 r"\quad(\text{전기자 극}\; R_a/L_a \text{ 를 PI 영점으로 상쇄})")
        st.latex(r"K_{p\omega} = \frac{\omega_{cs} J}{K\phi},\quad "
                 r"K_{i\omega} = \frac{K_{p\omega}\,\omega_{cs}}{4}")
        st.caption(f"현재 Kφ = {kphi:.3f} V·s/rad, 전기자 시정수 La/Ra = "
                   f"{params['La'] / params['Ra'] * 1000:.1f} ms")
    st.info("🧩 제어 구조를 직접 바꿔 보고 싶다면 왼쪽 메뉴의 **제어 블록 편집기**에서 "
            "블록을 끌어다 이어 구성할 수 있습니다 (전류 루프만, P 제어, PID, 위치 제어 등).")
    st.markdown("#### 실시간 제어 실험")
    st.caption("계산이 브라우저에서 실시간으로 돌아갑니다. 속도 지령·부하·게인·전류 제한·초퍼 종류를 "
               "바꾸면 **그 순간부터** 반영되어 현재 상태에서 어떻게 반응하는지 볼 수 있습니다. "
               "처음부터 보려면 **⟲ 처음부터 다시** 를 누르세요.")
    realtime.render(realtime.control_html(params, kphi), height=800)
    with st.expander("해 볼 실험", expanded=False):
        st.markdown("""
1. **전류 제한**: 지령을 0 → +1000 rpm 으로 바꾸면 전류가 I_lim 에 붙은 채로 일정 가속합니다.
   I_lim 슬라이더를 줄이면 가속이 느려집니다.
2. **부하 외란**: 정속 중 TL 을 올리면 속도가 잠깐 처졌다가 PI 의 적분 동작으로 지령에 돌아옵니다.
   회색 점선(개루프)은 처진 채로 남습니다.
3. **안티와인드업**: 끄고 큰 속도 지령을 주면 전류 제한에 걸린 동안 적분기가 쌓여 오버슈트가 커집니다.
4. **역회전 / 1상한**: +1000 → −700 rpm. 4상한은 회생 제동 후 역회전, 1상한은 음의 전류를 못 내서
   마찰로만 감속하고 0 rpm 에서 멈춥니다.
5. **게인**: Kpω 를 크게/작게 하거나 ωcs 를 ωci 에 가깝게 올려 진동이 생기는지 보세요.
""")
    st.markdown("#### 시나리오 시뮬레이션 (시각을 정해 한 번에 계산)")
    with st.expander("지령 변경 시각, 부하 인가 시각을 정해 전체 응답을 한 그래프로 보기", expanded=False):
        cfg = _settings(params, kphi)
        items = tuple(sorted(cfg.items()))
        p_items = tuple(sorted(params.items()))
        r = _run(p_items, kphi, items, False)
        ro = _run(p_items, kphi, items, True) if st.session_state.ct_ol else None
        _summary(r, ro, cfg, params)
        st.plotly_chart(_plot(r, ro, cfg), width="stretch")

