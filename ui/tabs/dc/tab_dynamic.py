"""탭 3. 동특성 (시간 응답)"""
from dataclasses import replace
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.simulate import simulate, Event
from motors import registry
from ui.plots import info_metric, style, mark_events, PALETTE

CHANGE_OPTS = ["없음", "전기자 전압 변경", "계자 변경"]


def _init_state(params, force=False):
    ss = st.session_state
    defaults = {
        "dy_tend": 3.0, "dy_tload": 1.0, "dy_rst": 0.0, "dy_trst": 0.5,
        "dy_change": "없음", "dy_tchg": 2.0, "dy_newV": round(0.6 * params["V"]),
        "dy_fpct": 70, "dy_preex": True,
    }
    for k, v in defaults.items():
        if force or k not in ss:
            ss[k] = v


def _preset(name, params):
    ss = st.session_state
    _init_state(params, force=True)
    if name == "rst":
        # 돌입 전류를 정격의 2배로 제한하는 기동 저항
        ss.dy_rst = round(max(params["V"] / (2 * params["I_rated"]) - params["Ra"], 0.0), 2)
        ss.dy_trst = 0.5
    elif name == "volt":
        ss.dy_change = "전기자 전압 변경"
    elif name == "field":
        ss.dy_change = "계자 변경"


@st.cache_data(max_entries=30, show_spinner=False)
def _run(model_key, params_items, s):
    model = registry.get(model_key)(dict(params_items))
    u_nom = model.default_inputs()
    u0 = replace(u_nom, TL=0.0, Rst=s["rst"])
    evs = [Event(s["tload"], {"TL": u_nom.TL}, "부하 인가")]
    if s["rst"] > 0:
        evs.append(Event(s["trst"], {"Rst": 0.0}, "기동저항 제거"))
    if s["change"] == "전기자 전압 변경":
        evs.append(Event(s["tchg"], {"V": s["newV"]}, f"V→{s['newV']:.0f} V"))
    elif s["change"] == "계자 변경":
        uf = model.with_field_ratio(u_nom, s["fpct"] / 100)
        evs.append(Event(s["tchg"], {"Vf": uf.Vf, "Rfx": uf.Rfx}, f"계자 {s['fpct']}%"))
    x0 = model.initial_state(u0, field_preexcited=s["preex"])
    return simulate(model, u0, s["tend"], x0=x0, events=evs, n_points=3000,
                    max_step=min(s["tend"] / 1000, 2e-3))


def _settings(model, params):
    ss = st.session_state
    st.markdown("**프리셋**")
    p = st.columns(4)
    p[0].button("직입 기동", on_click=_preset, args=("direct", params), use_container_width=True)
    p[1].button("기동 저항 사용", on_click=_preset, args=("rst", params),
                use_container_width=True)
    p[2].button("전압 제어", on_click=_preset, args=("volt", params), use_container_width=True)
    p[3].button("계자 약화", on_click=_preset, args=("field", params), use_container_width=True,
                disabled=model.field_control_input not in ("Vf", "Rfx"))

    c = st.columns(4)
    with c[0]:
        st.number_input("시뮬레이션 시간 [s]", 0.2, 30.0, step=0.5, key="dy_tend")
        st.checkbox("계자 사전 여자 (기동 전 If 확립)", key="dy_preex",
                    help="끄면 전기자와 계자를 동시에 투입합니다. 계자 시정수 Lf/Rf 동안 "
                         "Kφ 가 작아 큰 전류가 오래 흐릅니다.")
    with c[1]:
        st.number_input("부하 인가 시각 [s]", 0.0, 30.0, step=0.1, key="dy_tload")
        st.caption(f"부하 크기는 사이드바 TL = {params['TL']:.1f} N·m")
    with c[2]:
        st.number_input("기동 저항 Rst [Ω]", 0.0, 100.0, step=0.5, key="dy_rst",
                        help="0 이면 직입 기동")
        st.number_input("기동 저항 제거 시각 [s]", 0.0, 30.0, step=0.1, key="dy_trst",
                        disabled=ss.dy_rst <= 0)
    with c[3]:
        st.selectbox("운전 중 변경", CHANGE_OPTS, key="dy_change")
        st.number_input("변경 시각 [s]", 0.0, 30.0, step=0.1, key="dy_tchg",
                        disabled=ss.dy_change == "없음")
        if ss.dy_change == "전기자 전압 변경":
            st.number_input("새 전압 [V]", 0.0, 2000.0, step=10.0, key="dy_newV")
        elif ss.dy_change == "계자 변경":
            st.slider("새 계자 세기 [% 기준]", 20, 150, key="dy_fpct")
    return {"tend": ss.dy_tend, "tload": ss.dy_tload, "rst": ss.dy_rst, "trst": ss.dy_trst,
            "change": ss.dy_change, "tchg": ss.dy_tchg, "newV": float(ss.dy_newV),
            "fpct": ss.dy_fpct, "preex": ss.dy_preex}


def _summary(res, s, params):
    t, ia, rpm = res.t, res["ia"], res["rpm"]
    I_r = params["I_rated"]
    k = int(np.argmax(np.abs(ia)))
    c = st.columns(4)
    info_metric(c[0], "최대 돌입 전류", f"{ia[k]:.1f} A", f"정격의 {abs(ia[k]) / I_r:.1f} 배 "
                f"(t = {t[k] * 1000:.0f} ms)")
    info_metric(c[1], "최종 속도", f"{rpm[-1]:.1f} rpm", f"Ia = {ia[-1]:.1f} A")
    if 0 < s["tload"] < s["tend"]:
        later = [e.t for e in res.events if e.t > s["tload"]] + [s["tend"]]
        t_stop = min(later)
        before = np.interp(s["tload"] - 1e-6, t, rpm)
        m = (t >= s["tload"]) & (t <= t_stop)
        dip = before - rpm[m].min()
        settled = before - rpm[m][-1]
        info_metric(c[2], "부하 인가 시 속도 강하 (과도 최대)", f"{dip:.1f} rpm",
                    f"{dip / before * 100:.1f} %" if before > 0 else None)
        info_metric(c[3], "부하 인가 후 정상 강하", f"{settled:.1f} rpm",
                    f"{settled / before * 100:.1f} %" if before > 0 else None)
    if abs(ia[k]) > 2.5 * I_r:
        st.warning(f"돌입 전류가 정격의 {abs(ia[k]) / I_r:.0f} 배입니다. 실제 전동기에서는 "
                   "정류 불꽃, 브러시 손상, 보호계전기 동작이 생깁니다. 기동 저항이나 "
                   "전압 제어 기동을 써 보세요.")


def _plot(res, params):
    t = res.t
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        subplot_titles=("속도 [rpm]", "전기자 전류 Ia [A]", "계자 전류 If [A]",
                                        "토크 [N·m]", "전압 [V]"))
    fig.add_trace(go.Scatter(x=t, y=res["rpm"], name="속도",
                             line=dict(color=PALETTE["speed"])), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=res["ia"], name="Ia", line=dict(color=PALETTE["ia"])), 2, 1)
    fig.add_hline(y=params["I_rated"], line=dict(color="#bbb", dash="dot"), row=2, col=1,
                  annotation_text="정격", annotation_position="right")
    fig.add_trace(go.Scatter(x=t, y=res["if"], name="If", line=dict(color=PALETTE["if"])), 3, 1)
    fig.add_trace(go.Scatter(x=t, y=res["Te"], name="Te (전자기)",
                             line=dict(color=PALETTE["Te"])), 4, 1)
    fig.add_trace(go.Scatter(x=t, y=res["TL"], name="TL (부하)",
                             line=dict(color=PALETTE["TL"], dash="dash")), 4, 1)
    fig.add_trace(go.Scatter(x=t, y=res["V"], name="V (전원)",
                             line=dict(color=PALETTE["V"], dash="dash")), 5, 1)
    fig.add_trace(go.Scatter(x=t, y=res["E"], name="E (역기전력)",
                             line=dict(color=PALETTE["E"])), 5, 1)
    fig.add_trace(go.Scatter(x=t, y=res["v_R"], name="Ia·R (저항 강하)",
                             line=dict(color=PALETTE["ia"], width=1)), 5, 1)
    style(fig, 1050, side_legend=True)
    mark_events(fig, res.events, rows=range(1, 6))
    fig.update_xaxes(title_text="시간 [s]", row=5, col=1)
    return fig


def render(model, params):
    _init_state(params)
    st.caption("정지 상태에서 **무부하로 기동** → 지정 시각에 부하 인가 → 지정 시각에 전압 또는 "
               "계자 변경. 이벤트 사이 구간을 따로 적분합니다 (solve_ivp, LSODA).")
    s = _settings(model, params)
    res = _run(model.key, tuple(sorted(params.items())), s)
    _summary(res, s, params)
    st.plotly_chart(_plot(res, params), use_container_width=True)
