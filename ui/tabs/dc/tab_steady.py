"""탭 2. 정상상태 특성"""
from dataclasses import replace
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.units import to_rpm, fmt
from ui.compare import VARIANTS, COLORS, build, label_of
from ui.plots import info_metric, style, PALETTE


def _warnings(model, op, op_nl, params):
    I_r = params["I_rated"]
    if op is None:
        st.error("⚠️ **운전점이 없습니다.** 기동 토크(정지 시 토크)가 부하 토크보다 작아 "
                 "전동기 영역(ω ≥ 0)에서 Te = TL + Bω 를 만족하는 점이 없습니다. "
                 "전압을 올리거나 부하를 줄여 보세요.")
        return
    if not op.stable:
        msg = ("⚠️ 이 운전점은 **불안정**합니다. 운전점에서 선형화한 미분방정식의 고유값 중 "
               "실수부가 양수인 것이 있어서, 작은 흔들림에도 운전점을 벗어납니다.")
        if model.excitation == "compound" and model.sigma < 0:
            R = params["Ra"] + params["Rs"]
            msg += (f"\n\n**차동 복권의 전기적 불안정**: 속도가 오르면 직권 자속이 줄어드는 몫까지 "
                    f"더해져 전류가 오히려 늘어납니다. 대략 **Ms·ω < Ra + Rs** 여야 안정합니다. "
                    f"지금은 Ms·ω = {params['Ms'] * op.omega:.2f} Ω, Ra + Rs = {R:.2f} Ω 입니다. "
                    f"위 파라미터 설정에서 Ms 를 {0.8 * R / max(op.omega, 1):.4f} H 이하로 줄여 보세요.")
        st.error(msg)
    if abs(op.ia) > 1.5 * I_r:
        st.error(f"⚠️ 전기자 전류 {op.ia:.1f} A 가 정격 {I_r:.0f} A 의 "
                 f"{op.ia / I_r:.1f} 배입니다. 연속 운전 시 과열됩니다.")
    elif abs(op.ia) > 1.05 * I_r:
        st.warning(f"전기자 전류 {op.ia:.1f} A 가 정격 {I_r:.0f} A 를 초과합니다.")
    if op_nl is None:
        st.error("⚠️ 무부하 운전점이 없습니다 (B = 0 인 직권 전동기는 무부하 속도가 무한대). "
                 "부하가 빠지면 **폭주**합니다.")
    elif op_nl.rpm > 2 * max(op.rpm, 1):
        st.error(f"⚠️ 무부하 속도가 {op_nl.rpm:,.0f} rpm 으로 지금 운전 속도의 "
                 f"{op_nl.rpm / max(op.rpm, 1):.1f} 배입니다. 부하가 빠지면 **폭주** 위험이 있습니다 "
                 "(직권 전동기는 벨트 구동·무부하 운전 금지).")


def _metrics(op, op_nl, model):
    reg = (op_nl.omega - op.omega) / op.omega * 100 if (op_nl and op.omega > 0) else None
    rows = [
        [("속도", f"{op.rpm:.1f} rpm", f"{op.omega:.2f} rad/s"),
         ("전기자 전류 Ia", fmt(op.ia, "A"), None),
         ("선전류 IL", fmt(op.il, "A"), "전원에서 공급"),
         ("계자 전류 If", fmt(op.if_, "A"), None)],
        [("Kφ", fmt(op.kphi, "V·s/rad"), None),
         ("역기전력 E", fmt(op.E, "V"), None),
         ("전자기 토크 Te", fmt(op.Te, "N·m"), None),
         ("부하 토크 TL", fmt(op.TL, "N·m"), None)],
        [("입력 전력", fmt(op.P_in / 1e3, "kW"), None),
         ("출력 전력 (TL·ω)", fmt(op.P_out / 1e3, "kW"), None),
         ("효율", f"{op.eta * 100:.1f} %" if op.P_in > 0 else "—", None),
         ("무부하 속도", f"{op_nl.rpm:,.1f} rpm" if op_nl else "∞ (폭주)",
          f"속도 변동률 {reg:.2f} %" if reg is not None else None)],
    ]
    for row in rows:
        cols = st.columns(4)
        for c, (label, val, sub) in zip(cols, row):
            info_metric(c, label, val, sub)
    with st.expander("계산식 보기"):
        for eq in model.steady_latex:
            st.latex(eq)
        st.latex(r"\text{속도 변동률} = \frac{\omega_{\text{무부하}} - \omega}{\omega}\times 100\,\%,"
                 r"\qquad \eta = \frac{T_L\,\omega}{P_{in}}")
        st.caption("입력 전력에는 계자 회로 입력도 포함합니다. 운전점은 Ia 를 변수로 두고 "
                   "Te(Ia) − B·ω(Ia) − TL = 0 의 근을 수치적으로 찾습니다.")


def _speed_torque(model, op, op_nl, u, params):
    I_r = params["I_rated"]
    ia_max = max(2.5 * I_r, 1.3 * abs(op.ia) if op else 0)
    te, w, _ = model.speed_torque_curve(u, ia_max=ia_max)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=te, y=to_rpm(w), name=f"{model.name} 속도–토크 곡선",
                             line=dict(color=PALETTE["speed"], width=3)))
    w_top = max(np.max(w) if len(w) else 0, op_nl.omega if op_nl else 0) * 1.1
    if op:  # 직권처럼 저부하 속도가 매우 큰 경우 운전점이 잘 보이도록 범위 제한
        w_top = min(w_top, 3.0 * max(op.omega, 1.0))
    wl = np.linspace(0, w_top, 50)
    fig.add_trace(go.Scatter(x=u.TL + params["B"] * wl, y=to_rpm(wl),
                             name="부하선 TL + Bω", line=dict(color=PALETTE["TL"], dash="dash")))
    T_r = model.rated_torque()
    fig.add_vline(x=T_r, line=dict(color="#bbb", dash="dot"),
                  annotation_text=f"정격전류 토크 {T_r:.1f} N·m",
                  annotation_position="bottom right")
    if op:
        fig.add_trace(go.Scatter(x=[op.Te], y=[op.rpm], mode="markers+text",
                                 marker=dict(size=14, color=PALETTE["ia"], symbol="diamond"),
                                 text=[f"  운전점 ({op.Te:.1f} N·m, {op.rpm:.0f} rpm)"],
                                 textposition="middle right", name="운전점"))
    style(fig, 430, xaxis_title="토크 [N·m]", yaxis_title="속도 [rpm]",
          title=dict(text="속도–토크 특성과 운전점", x=0.0), hovermode="closest")
    fig.update_yaxes(range=[0, to_rpm(w_top)])
    return fig


def _compare_section(model, params):
    """여러 여자 방식의 속도–토크 곡선을 겹쳐 그리고 운전점 비교표를 만든다."""
    st.markdown("#### 여자 방식 비교")
    st.caption("체크한 방식의 곡선을 한 그래프에 겹칩니다. 공통 파라미터(V, Ra, La, J, B, TL, "
               "정격 전류)는 파라미터 설정 값을 같이 쓰고, 계자 파라미터는 각 종류에서 입력해 둔 값"
               "(없으면 기본값)을 씁니다.")
    me = label_of(model)
    cols = st.columns(len(VARIANTS))
    chosen = []
    for c, (label, _, _) in zip(cols, VARIANTS):
        if c.checkbox(label, value=True if label != "차동 복권" or me == label else False,
                      key=f"cmp_{label}", disabled=label == me,
                      help="지금 선택한 전동기는 항상 표시" if label == me else None):
            chosen.append(label)
    if me not in chosen:
        chosen.insert(0, me)

    I_r = params["I_rated"]
    fig = go.Figure()
    rows, w_ops, w_all, t_all = [], [], [], [1.0]
    for label in chosen:
        m = build(label, model, params)
        u = m.default_inputs()
        op = m.steady_state(u)
        nl = m.no_load(u)
        te, w, _ = m.speed_torque_curve(u, ia_max=2.5 * I_r)
        col = COLORS[label]
        width = 4 if label == me else 2
        fig.add_trace(go.Scatter(x=te, y=to_rpm(w), name=label, line=dict(color=col, width=width),
                                 hovertemplate=f"{label}<br>%{{x:.1f}} N·m, %{{y:.0f}} rpm"))
        if op:
            fig.add_trace(go.Scatter(x=[op.Te], y=[op.rpm], mode="markers", showlegend=False,
                                     marker=dict(size=12, color=col, symbol="diamond",
                                                 line=dict(color="white", width=1.5)),
                                     hovertemplate=f"{label} 운전점<br>%{{x:.1f}} N·m, "
                                                   f"%{{y:.0f}} rpm<extra></extra>"))
            w_ops.append(op.omega)
        if len(w):
            w_all.append(float(np.max(w)))
            t_all.append(float(np.max(te)))
        T_at_2I = float(m.kphi(2 * I_r, m.field_ss(2 * I_r, u)) * 2 * I_r)
        reg = ((nl.omega - op.omega) / op.omega * 100) if (op and nl and op.omega > 0) else None
        rows.append({
            "방식": label,
            "속도 [rpm]": round(op.rpm, 1) if op else None,
            "Ia [A]": round(op.ia, 2) if op else None,
            "IL [A]": round(op.il, 2) if op else None,
            "Kφ [V·s/rad]": round(op.kphi, 3) if op else None,
            "효율 [%]": round(op.eta * 100, 1) if op else None,
            "무부하 속도 [rpm]": round(nl.rpm, 0) if nl else float("inf"),
            "속도 변동률 [%]": round(reg, 2) if reg is not None else None,
            "2×정격전류 토크 [N·m]": round(T_at_2I, 1),
            "안정": ("예" if op.stable else "아니오") if op else "운전점 없음",
        })
    y_top = min(max(w_all + [1.0]), 3.0 * max(w_ops + [1.0])) * 1.1
    wl = np.linspace(0, y_top, 60)   # 화면에 보이는 속도 범위까지만 부하선을 그린다
    fig.add_trace(go.Scatter(x=params["TL"] + params["B"] * wl, y=to_rpm(wl), name="부하선",
                             line=dict(color=PALETTE["TL"], dash="dash")))
    style(fig, 460, xaxis_title="토크 [N·m]", yaxis_title="속도 [rpm]", hovermode="closest",
          title=dict(text="속도–토크 곡선 비교 (◆ 운전점)", x=0.0))
    fig.update_yaxes(range=[0, to_rpm(y_top)])
    fig.update_xaxes(range=[0, 1.05 * max(t_all)])
    st.plotly_chart(fig, width="stretch")
    st.dataframe(rows, width="stretch", hide_index=True)
    with st.expander("비교해서 볼 점"):
        st.markdown("""
- **타여자·분권**: 거의 수평인 직선. 부하가 변해도 속도가 일정합니다 (속도 변동률 수 %).
  기본값처럼 Vf = V 이면 두 곡선이 **완전히 겹칩니다** (계자 전류가 같으므로).
  차이는 전압을 바꿀 때 드러납니다 → 동특성 탭 '전압 제어'로 비교해 보세요.
- **직권**: 쌍곡선. 저부하에서 속도가 급격히 오르고(폭주), 같은 전류에서 토크가 가장 큽니다
  (표의 **2×정격전류 토크** 열). → 견인·크레인용.
- **가동 복권**: 둘의 중간. 분권보다 기동 토크가 크고 직권과 달리 무부하 속도가 정해져 있습니다.
- **차동 복권**: 부하가 늘수록 속도가 오르기도 하는 특성. 직권 계자가 크면 불안정합니다.
""")


def _power_flow(op):
    fig = go.Figure()
    fig.add_trace(go.Bar(y=["입력"], x=[op.P_in], orientation="h", name="입력 전력",
                         marker_color="#1d3557", text=[f"{op.P_in:.0f} W"],
                         textposition="inside"))
    fig.add_trace(go.Bar(y=["출력 + 손실"], x=[op.P_out], orientation="h", name="축 출력",
                         marker_color="#2a9d8f", text=[f"출력 {op.P_out:.0f} W"],
                         textposition="inside"))
    colors = ["#e76f51", "#f4a261", "#8e44ad", "#adb5bd", "#e9c46a"]
    for (name, val), c in zip(op.losses.items(), colors):
        if abs(val) < 1e-6:
            continue
        fig.add_trace(go.Bar(y=["출력 + 손실"], x=[val], orientation="h", name=name,
                             marker_color=c, text=[f"{val:.0f} W"], textposition="inside"))
    style(fig, 260, barmode="stack", xaxis_title="전력 [W]",
          title=dict(text="전력 흐름 (입력 = 출력 + 손실)", x=0.0), hovermode="closest")
    return fig


def _load_sweep(model, u, params):
    T_max = 2.0 * model.rated_torque()
    TLs = np.linspace(0, T_max, 41)
    ia, eta, rpm, Tx = [], [], [], []
    for T in TLs:
        o = model.steady_state(replace(u, TL=float(T)))
        if o is None:
            break
        Tx.append(T); ia.append(o.ia); eta.append(o.eta * 100); rpm.append(o.rpm)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=Tx, y=ia, name="전기자 전류 Ia [A]",
                             line=dict(color=PALETTE["ia"], width=3)), secondary_y=False)
    fig.add_trace(go.Scatter(x=Tx, y=eta, name="효율 η [%]",
                             line=dict(color=PALETTE["Te"], width=3)), secondary_y=True)
    fig.add_hline(y=params["I_rated"], line=dict(color="#bbb", dash="dot"),
                  annotation_text="정격 전류", secondary_y=False)
    style(fig, 330, xaxis_title="출력(부하) 토크 TL [N·m]",
          title=dict(text="부하 토크에 따른 전류와 효율", x=0.0))
    fig.update_yaxes(title_text="전류 [A]", secondary_y=False)
    fig.update_yaxes(title_text="효율 [%]", range=[0, 100], tickmode="linear", dtick=20,
                     showgrid=False, secondary_y=True)
    return fig


def render(model, params):
    u = model.default_inputs()
    st.caption(f"파라미터 설정의 V = {params['V']:.0f} V, TL = {params['TL']:.1f} N·m 기준 정상상태입니다.")
    op = model.steady_state(u)
    op_nl = model.no_load(u)
    _warnings(model, op, op_nl, params)

    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(_speed_torque(model, op, op_nl, u, params), width="stretch")
    with c2:
        if op:
            st.plotly_chart(_power_flow(op), width="stretch")
    if op:
        _metrics(op, op_nl, model)
    st.plotly_chart(_load_sweep(model, u, params), width="stretch")
    st.divider()
    _compare_section(model, params)
