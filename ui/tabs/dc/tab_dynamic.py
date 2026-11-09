"""탭 3. 동특성 (시간 응답)"""
from dataclasses import replace
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.simulate import simulate, Event
from motors import registry
from ui.compare import VARIANTS, COLORS, build, label_of
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


def _preset(name, params, R0):
    """R0: 기동 저항을 뺀 전기자 회로 저항 (직권·복권은 직권 계자 저항 포함)."""
    ss = st.session_state
    _init_state(params, force=True)
    if name == "rst":
        # 돌입 전류를 정격의 2배로 제한하는 기동 저항
        ss.dy_rst = round(max(params["V"] / (2 * params["I_rated"]) - R0, 0.0), 2)
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
    R0 = float(model.R_arm(replace(model.default_inputs(), Rst=0.0)))
    has_field_ctrl = model.field_control_input in ("Vf", "Rfx")
    st.markdown("**프리셋**")
    p = st.columns(4)
    p[0].button("직입 기동", on_click=_preset, args=("direct", params, R0),
                use_container_width=True)
    p[1].button("기동 저항 사용", on_click=_preset, args=("rst", params, R0),
                use_container_width=True)
    p[2].button("전압 제어", on_click=_preset, args=("volt", params, R0),
                use_container_width=True)
    p[3].button("계자 약화", on_click=_preset, args=("field", params, R0),
                use_container_width=True, disabled=not has_field_ctrl)
    if not has_field_ctrl and ss.dy_change == "계자 변경":
        ss.dy_change = "없음"

    c = st.columns(4)
    with c[0]:
        st.number_input("시뮬레이션 시간 [s]", 0.2, 30.0, step=0.5, key="dy_tend")
        st.checkbox("계자 사전 여자 (기동 전 If 확립)", key="dy_preex",
                    disabled=model.excitation == "series",
                    help="끄면 전기자와 계자를 동시에 투입합니다. 계자 시정수 Lf/Rf 동안 "
                         "Kφ 가 작아 큰 전류가 오래 흐릅니다.")
    with c[1]:
        st.number_input("부하 인가 시각 [s]", 0.0, 30.0, step=0.1, key="dy_tload")
        st.caption(f"부하 크기는 파라미터 설정의 TL = {params['TL']:.1f} N·m")
    with c[2]:
        st.number_input("기동 저항 Rst [Ω]", 0.0, 100.0, step=0.5, key="dy_rst",
                        help="0 이면 직입 기동")
        st.number_input("기동 저항 제거 시각 [s]", 0.0, 30.0, step=0.1, key="dy_trst",
                        disabled=ss.dy_rst <= 0)
    with c[3]:
        st.selectbox("운전 중 변경", CHANGE_OPTS if has_field_ctrl else CHANGE_OPTS[:2],
                     key="dy_change")
        st.number_input("변경 시각 [s]", 0.0, 30.0, step=0.1, key="dy_tchg",
                        disabled=ss.dy_change == "없음")
        if ss.dy_change == "전기자 전압 변경":
            st.number_input("새 전압 [V]", 0.0, 2000.0, step=10.0, key="dy_newV")
        elif ss.dy_change == "계자 변경":
            st.slider("새 계자 세기 [% 기준]", 20, 150, key="dy_fpct",
                      help="타여자: Vf 를 조정 / 분권·복권: Rfx 를 조정 (Rfx ≥ 0 이라 "
                           "기준보다 세게는 못 함)")
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
    if np.min(rpm) < -10:
        st.error(f"⚠️ 기동 중 **역회전**했습니다 (최저 {np.min(rpm):.0f} rpm). 차동 복권은 기동 "
                 "전류가 클 때 직권 자속이 분권 자속을 넘어서 Kφ 가 음수가 되기 때문입니다. "
                 "그래서 차동 복권은 직권 계자를 단락하고 기동합니다.")
    if np.max(np.abs(rpm)) > 5000:
        st.error(f"⚠️ 속도가 {np.max(np.abs(rpm)):,.0f} rpm 까지 올라갔습니다 (폭주).")
    if abs(ia[k]) > 2.5 * I_r:
        st.warning(f"돌입 전류가 정격의 {abs(ia[k]) / I_r:.0f} 배입니다. 실제 전동기에서는 "
                   "정류 불꽃, 브러시 손상, 보호계전기 동작이 생깁니다. 기동 저항이나 "
                   "전압 제어 기동을 써 보세요.")


def _plot(res, params, model):
    t = res.t
    if_title = "계자 전류 If [A]" + (" (= Ia, 직권)" if model.excitation == "series" else "")
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        subplot_titles=("속도 [rpm]", "전기자 전류 Ia [A]", if_title,
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


def _compare(model, params, s, res_me):
    st.markdown("#### 다른 여자 방식과 비교")
    me = label_of(model)
    others = [v[0] for v in VARIANTS if v[0] != me]
    picked = st.multiselect("같은 시나리오로 겹쳐 볼 방식", others, key="dy_cmp",
                            placeholder="비교할 방식을 고르세요")
    if not picked:
        st.caption("방식을 고르면 같은 기동·부하·변경 시나리오의 속도와 전류를 겹쳐 그립니다.")
        return
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("속도 [rpm]", "전기자 전류 Ia [A]"))
    rows = []
    I_r = params["I_rated"]
    for label in [me] + picked:
        if label == me:
            r = res_me
        else:
            m = build(label, model, params)
            r = _run(m.key, tuple(sorted(m.p.items())), s)
        col = COLORS[label]
        w = 3.5 if label == me else 2
        fig.add_trace(go.Scatter(x=r.t, y=r["rpm"], name=label, legendgroup=label,
                                 line=dict(color=col, width=w)), 1, 1)
        fig.add_trace(go.Scatter(x=r.t, y=r["ia"], name=label, legendgroup=label,
                                 showlegend=False, line=dict(color=col, width=w)), 2, 1)
        k = int(np.argmax(np.abs(r["ia"])))
        before = np.interp(s["tload"] - 1e-6, r.t, r["rpm"])
        m_ = (r.t >= s["tload"])
        rows.append({"방식": label,
                     "최대 돌입 전류 [A]": round(float(r["ia"][k]), 1),
                     "정격 대비 [배]": round(abs(float(r["ia"][k])) / I_r, 1),
                     "최종 속도 [rpm]": round(float(r["rpm"][-1]), 1),
                     "부하 인가 직전 속도 [rpm]": round(float(before), 1),
                     "부하 후 최저 속도 [rpm]": round(float(r["rpm"][m_].min()), 1)
                     if m_.any() else None})
    style(fig, 560, side_legend=True)
    mark_events(fig, res_me.events, rows=(1, 2))
    fig.update_xaxes(title_text="시간 [s]", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("직권은 기동 전류가 작아도 토크가 커서(T ∝ Ia²) 빨리 가속하고, "
               "무부하 구간의 속도가 높습니다. 같은 기동 저항 설정은 모든 방식에 똑같이 적용됩니다.")


def render(model, params):
    _init_state(params)
    st.caption("정지 상태에서 **무부하로 기동** → 지정 시각에 부하 인가 → 지정 시각에 전압 또는 "
               "계자 변경. 이벤트 사이 구간을 따로 적분합니다 (solve_ivp, LSODA).")
    s = _settings(model, params)
    res = _run(model.key, tuple(sorted(params.items())), s)
    _summary(res, s, params)
    st.plotly_chart(_plot(res, params, model), use_container_width=True)
    st.divider()
    _compare(model, params, s, res)
