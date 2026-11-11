"""강의 실습 2장: 직류 전동기의 토크 제어."""
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lectures import ch2
from concepts.commutation import torque_waveforms
from lectures.ch2 import EXAMPLE2, RPM, TEXTBOOK
from ui.lecture_draw import hbridge
from ui.pages.lecture_common import check, link, lstyle, ref
from ui.plots import info_metric


# ---- 계산 캐시 (슬라이더를 움직일 때 같은 계산을 반복하지 않도록) ----
def _pt(P):
    return tuple(sorted(P.items()))


@st.cache_data(max_entries=64, show_spinner=False)
def _vstep(Pt, V, La=None):
    return ch2.voltage_step(dict(Pt), [(0.05, V)], 0.2, La=La)


@st.cache_data(max_entries=64, show_spinner=False)
def _rl(Pt, kind, Kp, Ki):
    return ch2.rl_controller_demo(dict(Pt), kind, Kp, Ki)


@st.cache_data(max_entries=64, show_spinner=False)
def _sim_cur(Pt, bw, rpm, iref, ff, aw, Vlim):
    return ch2.simulate(dict(Pt), 0.04, 2e-6, i_ref=lambda t: iref if 0.005 <= t < 0.025 else 0.0, wcc=2 * math.pi * bw,
                        fixed_speed=rpm / RPM, Vlim=Vlim, ff=ff, antiwindup=aw)


@st.cache_data(max_entries=64, show_spinner=False)
def _sim_spd(Pt, bw, alpha, rpm, TLs, t_step=0.01, Ilim=None, t_end=0.3, t_load=0.15):
    return ch2.simulate(dict(Pt), t_end, 2e-5, alpha=alpha, w_ref=lambda t: rpm / RPM if t >= t_step else 0.0,
                        TL=lambda t: TLs if t >= t_load else 0.0, wcs=2 * math.pi * bw, wcc=2 * math.pi * 1000, Ilim=Ilim)


@st.cache_data(max_entries=16, show_spinner=False)
def _drive(Pt, mode, fsw, bw):
    return ch2.simulate_chopper_drive(dict(Pt), fsw=fsw, mode=mode, wcs=2 * math.pi * bw)


@st.cache_data(max_entries=64, show_spinner=False)
def _chop(mode, V, va, fsw, Ra, La, E):
    return ch2.chopper_waveforms(mode, V, va, fsw, Ra, La, E, periods=3)


def _motor_inputs(key, show=True):
    """교재 전동기 값 (원하면 바꿀 수 있음)."""
    P = dict(TEXTBOOK)
    if show:
        pre = st.radio("전동기", ["교재 2.9절 전동기 (140 V, 25 A, 3000 r/min)", "교재 예제 2 (5 kW, 125 V, 1800 r/min)"],
                       horizontal=True, key=key + "pre")
        if pre.startswith("교재 예제"):
            P = dict(EXAMPLE2)
        with st.expander("전동기 파라미터 (바꿔 볼 수 있음)", expanded=False):
            c = st.columns(5)
            P["Ra"] = c[0].number_input("Ra [Ω]", 0.05, 5.0, P["Ra"], 0.05, key=key + "Ra")
            P["La"] = c[1].number_input("La [mH]", 0.1, 50.0, P["La"] * 1e3, 0.5, key=key + "La") * 1e-3
            P["J"] = c[2].number_input("J [kg·m²]", 1e-4, 0.1, P["J"], 1e-4, format="%.4f", key=key + "J")
            P["K"] = c[3].number_input("Kφ [V·s/rad]", 0.05, 2.0, P["K"], 0.01, format="%.4f", key=key + "K")
            P["B"] = c[4].number_input("B [N·m·s]", 0.0, 0.01, P["B"], 1e-4, format="%.4f", key=key + "B")
            st.caption("교재 m-file 값: Power = 3336 W, Ra = 0.26 Ω, La = 1.7 mH, J = 0.00252 kg·m², B = 0, K = Te정격/Ia정격 = 0.4248. "
                       "예제 2: Ra = 0.256 Ω, La = 1.7 mH, J = 0.00252, kφ = 0.6034.")
    return P


def _types():
    ref("2.1 직류 전동기의 구조·종류·동작 원리 (정류자와 브러시)")
    st.markdown("여자 방식(타여자·분권·직권·가동/차동 복권)별 결선도, 속도–토크 특성, 정류자와 코일 수에 따른 토크 리플, "
                "실시간 단면 애니메이션은 기존 시뮬레이터에 있습니다.")
    st.markdown("##### 정류자와 브러시의 역할: 전기자 도체 전류(교류)와 토크")
    n = st.slider("전기자 코일 수", 1, 12, 1, key="l21_n")
    th = np.linspace(0, 4 * math.pi, 1441)
    wv = torque_waveforms(th, n)
    cur = np.sign(np.sin(th))
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("한 도체의 전류 (정류자가 반 바퀴마다 뒤집음 → 교류)", "토크"))
    fig.add_trace(go.Scatter(x=np.degrees(th), y=cur, name="도체 전류", line=dict(shape="hv")), 1, 1)
    fig.add_trace(go.Scatter(x=np.degrees(th), y=wv["no_comm"], name="정류자 없음 (평균 0)", line=dict(dash="dot")), 2, 1)
    fig.add_trace(go.Scatter(x=np.degrees(th), y=wv["single"], name="코일 1개 + 정류자"), 2, 1)
    if n > 1:
        fig.add_trace(go.Scatter(x=np.degrees(th), y=wv["multi"], name=f"코일 {n}개 + 정류자", line=dict(width=3)), 2, 1)
    fig.update_xaxes(title_text="회전 각도 [°]", dtick=90, row=2, col=1)
    st.plotly_chart(lstyle(fig, height=380), width="stretch", key="l21_comm")
    st.caption("정류자가 없으면 도체 전류가 한 방향이라 토크가 +, − 를 오가며 평균 0. 정류자로 반 바퀴마다 전류를 뒤집으면 토크가 한 방향, "
               "코일을 늘리면 리플이 작아져 거의 일정한 토크가 됨.")
    c = st.columns(3)
    with c[0]: link("DC 전동기 시뮬레이터 (원리·정상상태·동특성·제어)", "")
    with c[1]: link("DC 전동기 구조 (3D·전기자 권선·정류자)", "structure-dc")
    with c[2]: link("회로 시뮬레이터 (DC 전동기 기동)", "circuit")


def _steady():
    ref("2.3 정상상태 특성 — 전기자 전압 제어, 계자 자속 제어(약계자), 일정 토크·일정 출력 영역과 능력 곡선")
    P = _motor_inputs("l2s_")
    c = st.columns([1, 3])
    mode = c[0].radio("속도 제어 방법", ["전기자 전압 제어", "계자 자속 제어 (약계자)"], key="l2s_mode")
    T = np.linspace(0, 2 * P["I"] * P["K"], 50)
    fig = go.Figure()
    TLop = c[0].slider("부하 토크 TL [N·m]", 0.0, float(2 * P["I"] * P["K"]), float(round(P["I"] * P["K"] * 0.6, 1)), 0.5, key="l2s_TL")
    Trated = P["I"] * P["K"]
    if mode.startswith("전기자"):
        for V in (35, 70, 105, 140):
            fig.add_trace(go.Scatter(x=T, y=ch2.speed_torque(T, V, P["K"], P["Ra"]) * RPM, name=f"V = {V} V"))
            fig.add_trace(go.Scatter(x=[TLop], y=[float(ch2.speed_torque(TLop, V, P["K"], P["Ra"])) * RPM], mode="markers",
                                     marker=dict(size=9, color="#111"), showlegend=False))
        c[0].caption("기울기(−Ra/K²)는 같고 무부하 속도 V/K 만 비례해서 변함 → 기저 속도 이하에서 쓰는 방법")
    else:
        for r in (1.0, 0.8, 0.6, 0.5):
            fig.add_trace(go.Scatter(x=T, y=ch2.speed_torque(T, P["V"], P["K"] * r, P["Ra"]) * RPM, name=f"Φ = {r:.0%} 정격"))
            fig.add_trace(go.Scatter(x=[TLop], y=[float(ch2.speed_torque(TLop, P["V"], P["K"] * r, P["Ra"])) * RPM], mode="markers",
                                     marker=dict(size=9, color="#111"), showlegend=False))
            fig.add_trace(go.Scatter(x=[P["K"] * r * P["I"]] * 2, y=[0, float(ch2.speed_torque(P["K"] * r * P["I"], P["V"], P["K"] * r, P["Ra"])) * RPM],
                                     mode="lines", line=dict(color="#aaa", dash="dot", width=1), showlegend=False))
        c[0].caption("자속을 줄이면 무부하 속도는 1/Φ 로 오르고 기울기는 1/Φ² 로 가팔라짐 → 기저 속도 이상(약계자)")
    fig.add_vline(x=TLop, line=dict(color="#e76f51"), annotation_text="부하 토크")
    fig.add_vline(x=Trated, line=dict(color="#d62828", dash="dash"), annotation_text="정격 전류 시 토크 한계")
    fig.update_xaxes(title_text="토크 T [N·m]"); fig.update_yaxes(title_text="속도 [rpm]", rangemode="tozero")
    c[1].plotly_chart(lstyle(fig, height=380), width="stretch", key="l2_st")
    if not mode.startswith("전기자"):
        If = np.linspace(0, 2, 100)
        figf = go.Figure(go.Scatter(x=If, y=np.tanh(1.3 * If) / np.tanh(1.3), name="자속 Φ (상대값)"))
        for r, lab in ((1.0, "정격 (A)"), (0.8, "B"), (0.6, "C")):
            xf = np.arctanh(r * np.tanh(1.3)) / 1.3
            figf.add_trace(go.Scatter(x=[xf], y=[r], mode="markers+text", text=[lab], textposition="top left", marker=dict(size=9), showlegend=False))
        figf.update_xaxes(title_text="계자 전류 If (상대값)"); figf.update_yaxes(title_text="계자 자속 Φ")
        st.markdown("계자 전류–자속 특성: 정격 자속은 포화 직전이라 자속을 더 키우기 어렵고, 주로 줄이는(약계자) 쪽으로 씀")
        st.plotly_chart(lstyle(figf, height=260), width="stretch", key="l2_flux")
    with st.expander("교재 예제 1: 5 kW, 125 V, 1800 r/min 직류 전동기 (효율 91 %, Ra = 0.256 Ω)", expanded=False):
        c = st.columns(4)
        Pe = c[0].number_input("출력 [kW]", 0.1, 100.0, 5.0, 0.5, key="l2e1_P") * 1000
        Ve = c[1].number_input("정격 전압 [V]", 10.0, 1000.0, 125.0, 5.0, key="l2e1_V")
        ne = c[2].number_input("정격 속도 [r/min]", 100.0, 10000.0, 1800.0, 50.0, key="l2e1_n")
        eta = c[3].number_input("효율 [%]", 50.0, 100.0, 91.0, 1.0, key="l2e1_eta") / 100
        Rae = st.number_input("전기자 저항 Ra [Ω]", 0.01, 5.0, 0.256, 0.01, key="l2e1_Ra")
        Ia = Pe / eta / Ve; wme = ne / RPM; Te = Pe / wme; kphi = (Ve - Ia * Rae) / wme
        w10 = (0.9 * Ve - Ia * Rae) / kphi; w_f = (Ve - Ia * Rae) / (0.9 * kphi)
        st.table({"항목": ["① 정격 전기자 전류 Ia = P/(η·V)", "① 정격 토크 Te = P/ωm", "kφ = (V − Ia·Ra)/ωm",
                          "② 전압 10 % 감소 시 속도 (정격 전류)", "③ 자속 10 % 감소 시 속도", "③ 그때 낼 수 있는 토크 0.9kφ·Ia"],
                  "값": [f"{Ia:.2f} A", f"{Te:.2f} N·m", f"{kphi:.5f} V·s/rad", f"{w10 * RPM:.0f} r/min ({w10:.2f} rad/s)",
                        f"{w_f * RPM:.0f} r/min ({w_f:.2f} rad/s)", f"{0.9 * kphi * Ia:.2f} N·m"]})
    cap = ch2.capability(P)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("능력 곡선: 토크·출력", "전압·자속"))
    x = cap["w"] * RPM
    fig.add_trace(go.Scatter(x=x, y=cap["T"], name="최대 토크 [N·m]"), 1, 1)
    fig.add_trace(go.Scatter(x=x, y=cap["P"] / 1000, name="출력 [kW]"), 1, 1)
    fig.add_trace(go.Scatter(x=x, y=cap["V"], name="전기자 전압 [V]"), 1, 2)
    fig.add_trace(go.Scatter(x=x, y=cap["K"] / P["K"] * 100, name="계자 자속 [% 정격]"), 1, 2)
    fig.add_trace(go.Scatter(x=x, y=cap["K"] * cap["w"], name="역기전력 E [V]", line=dict(dash="dot")), 1, 2)
    fig.add_trace(go.Scatter(x=x, y=cap["I"], name="전기자 전류 [A]", line=dict(dash="dash")), 1, 2)
    for col in (1, 2):
        fig.add_vrect(x0=0, x1=cap["wb"] * RPM, fillcolor="rgba(42,157,143,0.10)", line_width=0, row=1, col=col)
        fig.add_vrect(x0=cap["wb"] * RPM, x1=x[-1], fillcolor="rgba(231,111,81,0.10)", line_width=0, row=1, col=col)
    fig.add_annotation(x=cap["wb"] * RPM / 2, y=1.02, yref="paper", text="일정 토크 영역", showarrow=False)
    fig.add_annotation(x=cap["wb"] * RPM * 2, y=1.02, yref="paper", text="일정 출력 영역 (약계자)", showarrow=False)
    fig.update_xaxes(title_text="속도 [rpm]")
    st.plotly_chart(lstyle(fig, height=340), width="stretch", key="l2_cap")
    check("전기자 전압 제어는 정격 속도 이하, 계자 자속 제어는 정격 이상 (보통 3배까지)",
          "기저 속도 이하: 전류 일정 → 토크 일정, 이상: 전압·전류 일정 → 출력 일정 (토크는 1/ω)")


def _transient():
    ref("2.4 과도상태 특성 — 전달함수 ω/V, 극점과 감쇠비 ζ, 전기 기계 시정수 Tm·전기자 시정수 Ta, La = 0 근사 / 2.9.1 Simulink 결과 (0.05 s 에 70 V, 140 V)")
    P = _motor_inputs("l2t_")
    num, den, poles, zeta, wn, Tm, Ta = ch2.voltage_to_speed(P)
    c = st.columns(4)
    info_metric(c[0], "감쇠비 ζ", f"{zeta:.3f}", "부족감쇠 (진동)" if zeta < 1 else "과감쇠 (진동 없음)")
    info_metric(c[1], "고유 주파수 ωn", f"{wn:.1f} rad/s")
    info_metric(c[2], "전기 기계 시정수 Tm = JRa/K²", f"{Tm * 1000:.2f} ms")
    info_metric(c[3], "전기자 시정수 Ta = La/Ra", f"{Ta * 1000:.2f} ms", "Tm < 4Ta 이면 진동")
    t, V, ia, w = _vstep(_pt(P), 70.0)
    _, _, ia2, w2 = _vstep(_pt(P), 140.0)
    _, _, ia0, w0 = _vstep(_pt(P), 140.0, 0.0)
    fig = make_subplots(rows=1, cols=3, subplot_titles=("속도 [rpm]", "전기자 전류 [A]", "극점 (s 평면)"), column_widths=[0.38, 0.38, 0.24])
    fig.add_trace(go.Scatter(x=t, y=w * RPM, name="70 V"), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=w2 * RPM, name="140 V"), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=w0 * RPM, name="140 V, La = 0 근사 (1차)", line=dict(dash="dot")), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=ia, name="70 V", showlegend=False), 1, 2)
    fig.add_trace(go.Scatter(x=t, y=ia2, name="140 V", showlegend=False), 1, 2)
    fig.add_trace(go.Scatter(x=poles.real, y=poles.imag, mode="markers", marker=dict(symbol="x", size=14, color="#d62828"), name="극점"), 1, 3)
    fig.update_xaxes(title_text="시간 [s]", row=1, col=1); fig.update_xaxes(title_text="시간 [s]", row=1, col=2)
    fig.update_xaxes(title_text="실수부", row=1, col=3); fig.update_yaxes(title_text="허수부", row=1, col=3)
    st.plotly_chart(lstyle(fig, height=360), width="stretch", key="l2_tr")
    st.latex(r"\frac{\omega(s)}{V(s)}=\frac{K}{L_aJs^2+(R_aJ+L_aB)s+(R_aB+K^2)},\qquad \zeta=\frac{R_aJ+L_aB}{2\sqrt{L_aJ\,(R_aB+K^2)}}")
    st.markdown("##### 극점 위치와 과도 응답 (교재 그림: 안정·불안정 영역, 부족·임계·과감쇠)")
    c = st.columns([1, 1, 2])
    sig = c[0].slider("극점 실수부 −σ (오른쪽 = 불안정)", -200.0, 60.0, -75.0, 5.0, key="l2p_s")
    wd = c[1].slider("극점 허수부 ±ωd", 0.0, 400.0, 280.0, 10.0, key="l2p_w")
    tt = np.linspace(0, 0.08, 800)
    y = ch2.second_order_step(-sig, wd, tt)
    figp = make_subplots(rows=1, cols=2, subplot_titles=("s 평면", "계단 응답"))
    figp.add_vrect(x0=-250, x1=0, fillcolor="rgba(42,157,143,0.08)", line_width=0, row=1, col=1)
    figp.add_vrect(x0=0, x1=80, fillcolor="rgba(214,40,40,0.08)", line_width=0, row=1, col=1)
    figp.add_trace(go.Scatter(x=[sig, sig], y=[wd, -wd], mode="markers", marker=dict(symbol="x", size=14, color="#d62828"), name="극점"), 1, 1)
    figp.add_trace(go.Scatter(x=tt, y=np.clip(y, -5, 5), name="응답"), 1, 2)
    figp.add_hline(y=1, line=dict(dash="dot", color="#999"), row=1, col=2)
    figp.update_xaxes(range=[-250, 80], title_text="실수축 (왼쪽 = 빨리 수렴)", row=1, col=1); figp.update_yaxes(range=[-420, 420], title_text="허수축 (멀수록 진동↑)", row=1, col=1)
    figp.update_xaxes(title_text="시간 [s]", row=1, col=2)
    c[2].plotly_chart(lstyle(figp, height=330), width="stretch", key="l2_pole")
    zz = sig / math.hypot(sig, wd) * -1 if (sig or wd) else 0
    c[0].markdown(f"ζ = {zz:.2f} → " + ("**불안정 (발산)**" if sig > 0 else "진동하며 수렴 (부족감쇠)" if wd > 0 else "진동 없음"))
    figz = go.Figure()
    for zeta, lab in ((0.3, "부족감쇠 ζ = 0.3"), (1.0, "임계감쇠 ζ = 1"), (2.0, "과감쇠 ζ = 2")):
        figz.add_trace(go.Scatter(x=tt, y=ch2.zeta_step(zeta, 150, tt), name=lab))
    figz.update_xaxes(title_text="시간 [s]")
    st.plotly_chart(lstyle(figz, height=280), width="stretch", key="l2_zeta")
    check("J 를 줄이거나 Ra 를 줄이면 극점에 허수부가 생겨 진동 (서보·대형 전동기), Ra 를 키우면 진동 없음 (소형 전동기)",
          "La = 0 근사(점선)는 1차 저역 통과 특성: 진동 없이 Tm 으로 올라감",
          "속도는 전압에 비례: 70 V 는 140 V 의 절반 속도",
          "예제 2 를 고르면 극점 −75.29 ± j281.63, ζ = 0.258 (교재 값)")


def _control_basics():
    ref("2.5 제어 시스템 — 개루프·폐루프, P·I·PI 제어기, 정상상태 오차, 안정성(위상 여유)·대역폭")
    P = _motor_inputs("l2c_", show=False)
    st.markdown("대상: 회전자를 멈춘 전기자 회로 (Ra–La, 1차 시스템) 의 전류를 20 A 로 제어")
    c = st.columns(3)
    kp0, ki0 = ch2.current_gains(P, 2 * math.pi * 500)
    Kp = c[0].slider("비례 이득 Kp [V/A]", 0.5, 30.0, round(kp0, 1), 0.1, key="l2c_kp")
    Ki = c[1].slider("적분 이득 Ki [V/(A·s)]", 0.0, 3000.0, float(round(ki0, -1)), 10.0, key="l2c_ki")
    c[2].caption(f"극점-영점 상쇄 값 (500 Hz): Kp = La·ωcc = {P['La'] * 2 * math.pi * 500:.1f}, Ki = Ra·ωcc = {P['Ra'] * 2 * math.pi * 500:.0f}")
    fig = make_subplots(rows=1, cols=2, subplot_titles=("전류 응답", "제어기 출력 전압"))
    res = {}
    for kind, col in (("P", "#e76f51"), ("I", "#2a9d8f"), ("PI", "#264653")):
        t, i, v = _rl(_pt(P), kind, Kp, max(Ki, 1e-9))
        res[kind] = i[-1]
        fig.add_trace(go.Scatter(x=t * 1000, y=i, name=f"{kind} 제어", line=dict(color=col)), 1, 1)
        fig.add_trace(go.Scatter(x=t * 1000, y=v, name=f"{kind}", line=dict(color=col), showlegend=False), 1, 2)
    fig.add_hline(y=20, line=dict(dash="dot", color="#999"), row=1, col=1)
    fig.update_xaxes(title_text="시간 [ms]")
    st.plotly_chart(lstyle(fig, height=330), width="stretch", key="l2_pi")
    c = st.columns(3)
    info_metric(c[0], "P 제어 정상상태 오차", f"{20 - res['P']:.2f} A", f"이론 20·Ra/(Ra+Kp) = {20 * P['Ra'] / (P['Ra'] + Kp):.2f} A")
    info_metric(c[1], "I 제어 최종 값", f"{res['I']:.2f} A", "느리고 진동할 수 있음")
    info_metric(c[2], "PI 제어 최종 값", f"{res['PI']:.2f} A", "정상상태 오차 0")
    w = np.logspace(1, 6, 600)
    mag, ph, wc, pm = ch2.loop_bode(P, Kp, Ki, w)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("개루프 이득 |L(jω)| [dB]", "위상 [°]"))
    fig.add_trace(go.Scatter(x=w / (2 * math.pi), y=mag, name="이득"), 1, 1)
    fig.add_trace(go.Scatter(x=w / (2 * math.pi), y=ph, name="위상"), 2, 1)
    fig.add_hline(y=0, line=dict(dash="dot"), row=1, col=1); fig.add_hline(y=-180, line=dict(dash="dot", color="#d62828"), row=2, col=1)
    if np.isfinite(wc):
        fig.add_vline(x=wc / (2 * math.pi), line=dict(dash="dash", color="#999"))
    fig.update_xaxes(type="log", title_text="주파수 [Hz]", row=2, col=1)
    st.plotly_chart(lstyle(fig, height=380, showlegend=False), width="stretch", key="l2_bode")
    c = st.columns(3)
    info_metric(c[0], "이득 교차 주파수 (≈ 대역폭)", f"{wc / (2 * math.pi):.0f} Hz" if np.isfinite(wc) else "—")
    info_metric(c[1], "위상 여유", f"{pm:.0f}°" if np.isfinite(pm) else "—", "클수록 안정 (보통 45° 이상)")
    st.markdown("##### 오차가 일정할 때 제어기 출력 u(t) (교재 그림: P 는 계단, I 는 경사, PI 는 둘의 합)")
    tt = np.linspace(0, 0.01, 200)
    figu = go.Figure()
    figu.add_trace(go.Scatter(x=tt * 1000, y=np.full_like(tt, Kp * 1.0), name="P: Kp·e"))
    figu.add_trace(go.Scatter(x=tt * 1000, y=Ki * tt, name="I: Ki·∫e dt"))
    figu.add_trace(go.Scatter(x=tt * 1000, y=Kp + Ki * tt, name="PI: 합", line=dict(width=3)))
    figu.update_xaxes(title_text="시간 [ms] (오차 e = 1 A 일정)"); figu.update_yaxes(title_text="제어기 출력 u [V]")
    st.plotly_chart(lstyle(figu, height=260), width="stretch", key="l2_u")
    st.markdown("##### 주파수 응답: 정현파 입력에 대한 정상상태 출력 (폐루프 전류 제어 = 1차 저역 통과)")
    c = st.columns(2)
    fin = c[0].slider("입력 주파수 [Hz]", 10, 5000, 500, 10, key="l2f_f")
    wcc_ = Kp / P["La"]
    G = wcc_ / (1j * 2 * math.pi * fin + wcc_)
    tt = np.linspace(0, 3 / fin, 600)
    figs = go.Figure()
    figs.add_trace(go.Scatter(x=tt * 1000, y=np.sin(2 * math.pi * fin * tt), name="입력 r(t) = sin ωt"))
    figs.add_trace(go.Scatter(x=tt * 1000, y=abs(G) * np.sin(2 * math.pi * fin * tt + np.angle(G)), name="출력 y(t) = |G| sin(ωt + ∠G)"))
    figs.update_xaxes(title_text="시간 [ms]")
    c[1].plotly_chart(lstyle(figs, height=260), width="stretch", key="l2_sine")
    info_metric(c[0], "크기 비 |G(jω)|", f"{abs(G):.3f} ({20 * math.log10(abs(G)):.1f} dB)")
    info_metric(c[0], "위상 ∠G(jω)", f"{math.degrees(np.angle(G)):.1f}°", f"대역폭 {wcc_ / (2 * math.pi):.0f} Hz 에서 −3 dB, −45°")
    st.markdown("##### 대역폭이 넓을수록 빠른 응답 (폐루프 주파수 응답과 시간 응답)")
    figb = make_subplots(rows=1, cols=2, subplot_titles=("폐루프 크기 [dB]", "계단 응답"))
    wv = np.logspace(1, 5, 400)
    for bwh, col in ((250, "#1d4ed8"), (1000, "#d62828")):
        mag, ph = ch2.pi_closed_bode(P, 2 * math.pi * bwh, wv)
        figb.add_trace(go.Scatter(x=wv / (2 * math.pi), y=mag, name=f"대역폭 {bwh} Hz", line=dict(color=col)), 1, 1)
        figb.add_trace(go.Scatter(x=tt * 0 + np.linspace(0, 0.005, 600) * 1000, y=1 - np.exp(-2 * math.pi * bwh * np.linspace(0, 0.005, 600)),
                                  name=f"{bwh} Hz", line=dict(color=col), showlegend=False), 1, 2)
    figb.add_hline(y=-3, line=dict(dash="dot"), row=1, col=1)
    figb.update_xaxes(type="log", title_text="주파수 [Hz]", row=1, col=1); figb.update_xaxes(title_text="시간 [ms]", row=1, col=2)
    st.plotly_chart(lstyle(figb, height=300), width="stretch", key="l2_bw")
    st.markdown("##### 안정도: 이득 여유와 위상 여유 (개루프 L(s) = K / [s (s/a + 1)(s/b + 1)])")
    c = st.columns(3)
    Kg = c[0].slider("루프 이득 K", 0.5, 30.0, 5.0, 0.5, key="l2g_K")
    a_ = c[1].slider("극점 a [rad/s]", 1.0, 20.0, 2.0, 0.5, key="l2g_a")
    b_ = c[2].slider("극점 b [rad/s]", 5.0, 50.0, 10.0, 1.0, key="l2g_b")
    wv = np.logspace(-2, 3, 1200)
    mag, ph, wc, pm, w180, gm, num, den = ch2.generic_loop(Kg, a_, b_, wv)
    tt = np.linspace(0, 10, 1000)
    yc = ch2.closed_loop_step(num, den, tt)
    figg = make_subplots(rows=2, cols=2, shared_xaxes=False, specs=[[{}, {"rowspan": 2}], [{}, None]],
                         subplot_titles=("|L(jω)| [dB]", "폐루프 계단 응답", "∠L(jω) [°]"))
    figg.add_trace(go.Scatter(x=wv, y=mag, name="이득"), 1, 1); figg.add_hline(y=0, line=dict(dash="dot"), row=1, col=1)
    figg.add_trace(go.Scatter(x=wv, y=ph, name="위상"), 2, 1); figg.add_hline(y=-180, line=dict(dash="dot", color="#d62828"), row=2, col=1)
    figg.add_trace(go.Scatter(x=tt, y=np.clip(yc, -3, 4), name="출력"), 1, 2); figg.add_hline(y=1, line=dict(dash="dot"), row=1, col=2)
    figg.update_xaxes(type="log", row=1, col=1); figg.update_xaxes(type="log", title_text="ω [rad/s]", row=2, col=1)
    figg.update_xaxes(title_text="시간 [s]", row=1, col=2)
    st.plotly_chart(lstyle(figg, height=420, showlegend=False), width="stretch", key="l2_stab")
    c = st.columns(3)
    info_metric(c[0], "위상 여유", f"{pm:.0f}°" if np.isfinite(pm) else "—", "30~60° 가 좋음")
    info_metric(c[1], "이득 여유", f"{gm:.1f} dB" if np.isfinite(gm) else "∞", "2~10 dB 정도")
    info_metric(c[2], "판정", "안정" if (np.isfinite(pm) and pm > 0 and gm > 0) else "불안정 (발산)")
    check("P 만 쓰면 오차가 남고 Kp 를 키우면 줄어듦 (Type 0), I·PI 는 적분기가 있어 계단 지령 오차 0 (Type 1)",
          "Kp 를 키우면 교차 주파수(대역폭)가 커져 응답이 빨라짐")


def _current():
    ref("2.6 전류 제어기 — 극점-영점 상쇄 PI (Kp = La·ωcc, Ki = Ra·ωcc), 역기전력 전향 보상, 적분기 누적 방지(Anti wind-up)")
    P = _motor_inputs("l2i_")
    c = st.columns(5)
    bw = c[0].selectbox("전류 제어 대역폭", [250, 500, 1000, 2000], index=1, format_func=lambda x: f"{x} Hz", key="l2i_bw")
    rpm = c[1].slider("회전 속도 (고정) [rpm]", 0, 3000, 1500, 100, key="l2i_rpm")
    iref = c[2].slider("전류 지령 [A]", 5.0, 60.0, 20.0, 1.0, key="l2i_ref")
    ff = c[3].checkbox("역기전력 전향 보상", True, key="l2i_ff")
    aw = c[4].checkbox("적분기 누적 방지", True, key="l2i_aw")
    c = st.columns([1, 3])
    lim_on = c[0].checkbox("전압 한계 적용", False, key="l2i_lim",
                           help="끄면 교재 Simulink 결과처럼 전압 제한이 없는 경우. 켜면 인가 전압이 ±한계로 잘려 적분기 누적(wind-up)을 볼 수 있습니다.")
    Vlim = c[1].slider("전압 한계 [V]", 20.0, 200.0, 140.0, 5.0, key="l2i_vl", disabled=not lim_on) if lim_on else 1e6
    r = _sim_cur(_pt(P), bw, rpm, iref, ff, aw, Vlim)
    r2 = _sim_cur(_pt(P), bw * (2 if bw < 2000 else 0.5), rpm, iref, ff, aw, Vlim)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("전기자 전류", "인가 전압"))
    fig.add_trace(go.Scatter(x=r["t"] * 1000, y=r["istar"], name="지령 i*", line=dict(dash="dot", color="#999")), 1, 1)
    fig.add_trace(go.Scatter(x=r["t"] * 1000, y=r["ia"], name=f"{bw} Hz", line=dict(color="#d62828")), 1, 1)
    bw2 = bw * 2 if bw < 2000 else bw // 2
    fig.add_trace(go.Scatter(x=r2["t"] * 1000, y=r2["ia"], name=f"{bw2} Hz (비교)", line=dict(color="#1d4ed8")), 1, 1)
    fig.add_trace(go.Scatter(x=r["t"] * 1000, y=r["vstar"], name="제어기 출력 v*", line=dict(color="#e76f51", dash="dash")), 1, 2)
    fig.add_trace(go.Scatter(x=r["t"] * 1000, y=r["v"], name="실제 인가 v (제한 후)", line=dict(color="#264653")), 1, 2)
    if lim_on:
        fig.add_hline(y=Vlim, line=dict(color="#d62828", dash="dot"), row=1, col=2)
    fig.update_xaxes(title_text="시간 [ms]")
    st.plotly_chart(lstyle(fig, height=360), width="stretch", key="l2_cur")
    g = r["gains"]
    os_, tr = ch2.step_metrics(r["t"], r["ia"], iref, 0.005)
    c = st.columns(4)
    info_metric(c[0], "Kp = La·ωcc", f"{g['Kpc']:.2f} V/A"); info_metric(c[1], "Ki = Ra·ωcc", f"{g['Kic']:.0f} V/(A·s)")
    info_metric(c[2], "상승 시간 (10→90 %)", f"{tr * 1000:.3f} ms", f"1차 시스템이면 2.2/ωcc = {2.2 / (2 * math.pi * bw) * 1000:.3f} ms")
    info_metric(c[3], "오버슈트", f"{os_:.1f} %")
    figx = make_subplots(rows=1, cols=3, subplot_titles=("적분기 값 (누적 방지 비교)", "PI 제어기 보드 (크기 dB)", "전류 제어 개루프·폐루프 (dB)"))
    figx.add_trace(go.Scatter(x=r["t"] * 1000, y=r["xi"], name="적분기 출력"), 1, 1)
    wv = np.logspace(1, 6, 500)
    Kpc_, Kic_ = g["Kpc"], g["Kic"]
    figx.add_trace(go.Scatter(x=wv, y=20 * np.log10(np.abs(Kpc_ + Kic_ / (1j * wv))), name="PI: Kp + Ki/s"), 1, 2)
    figx.add_vline(x=Kic_ / Kpc_, line=dict(dash="dot"), row=1, col=2)
    magL, _, _, _ = ch2.loop_bode(P, Kpc_, Kic_, wv)
    magC, _ = ch2.pi_closed_bode(P, 2 * math.pi * bw, wv)
    figx.add_trace(go.Scatter(x=wv, y=magL, name="개루프 (−20 dB/dec 적분기)"), 1, 3)
    figx.add_trace(go.Scatter(x=wv, y=magC, name="폐루프 (대역폭 ωcc)"), 1, 3)
    figx.add_hline(y=0, line=dict(dash="dot"), row=1, col=3)
    figx.update_xaxes(title_text="시간 [ms]", row=1, col=1); figx.update_xaxes(type="log", title_text="ω [rad/s]", row=1, col=2); figx.update_xaxes(type="log", title_text="ω [rad/s]", row=1, col=3)
    st.plotly_chart(lstyle(figx, height=320), width="stretch", key="l2_cur2")
    st.caption("PI 절점 주파수 Ki/Kp = Ra/La (점선) 가 전동기 극점과 같아 상쇄되고, 개루프는 −20 dB/dec 적분기 모양 → 위상 여유 90°.")
    check("극점-영점 상쇄로 전류 응답이 1차(오버슈트 없음)가 되고 대역폭이 2배면 2배 빠름",
          "전향 보상을 끄면 역기전력(외란) 때문에 전류가 지령에 늦게 붙음 (회전 속도를 올려 보세요)",
          "전압 한계를 켜고(예: 80 V) 누적 방지를 끄면 지령이 0 으로 돌아갈 때 전류가 한동안 내려오지 않음 (wind-up)")


def _speed():
    ref("2.7 속도 제어기 — PI 속도 제어 (전류 제어 대역폭의 1/5 이하), 50 Hz / 100 Hz 비교, IP 제어기와 혼합 제어기(α)")
    P = _motor_inputs("l2w_")
    scen = st.radio("시나리오", ["교재 2.9.3 (0.05 s 에 2500 r/min, 토크 제한 = 정격)", "직접 설정 (지령·부하 단계)"], horizontal=True, key="l2w_sc")
    c = st.columns(5)
    bw = c[0].selectbox("속도 제어 대역폭", [20, 50, 100], index=1, format_func=lambda x: f"{x} Hz", key="l2w_bw")
    alpha = c[1].slider("α (1 = PI, 0 = IP)", 0.0, 1.0, 1.0, 0.05, key="l2w_a")
    rpm = c[2].slider("속도 지령 [rpm]", 200, 3000, 1000, 100, key="l2w_rpm")
    TLs = c[3].slider("0.15 s 에 걸리는 부하 [N·m]", 0.0, 10.0, 4.0, 0.5, key="l2w_tl")
    cmp = c[4].checkbox("PI·IP 함께 보기", True, key="l2w_cmp")
    runs = [("현재 설정", alpha, "#d62828")]
    if cmp:
        runs += [("PI (α = 1)", 1.0, "#1d4ed8"), ("IP (α = 0)", 0.0, "#2a9d8f")]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("속도 [rpm]", "토크 Te = K·ia [N·m]"))
    rows = []
    book = scen.startswith("교재")
    for name, a, col in runs:
        r = _sim_spd(_pt(P), bw, a, 2500 if book else rpm, 0.0 if book else TLs, 0.05 if book else 0.01,
                     P["I"] if book else None, 0.2 if book else 0.3, 1.0 if book else 0.15)
        fig.add_trace(go.Scatter(x=r["t"], y=r["w"] * RPM, name=name, line=dict(color=col, dash=None if name == "현재 설정" else "dot")), 1, 1)
        fig.add_trace(go.Scatter(x=r["t"], y=P["K"] * r["ia"], name=name, line=dict(color=col, dash=None if name == "현재 설정" else "dot"), showlegend=False), 1, 2)
        tl = 1.0 if book else 0.15
        os_, tr = ch2.step_metrics(r["t"][r["t"] < tl], r["w"][r["t"] < tl], (2500 if book else rpm) / RPM, 0.05 if book else 0.01)
        dip = 0.0 if book else (rpm / RPM - r["w"][r["t"] >= 0.15].min()) * RPM
        rows.append((name, os_, tr, dip))
    fig.add_trace(go.Scatter(x=r["t"], y=r["wref"] * RPM, name="지령", line=dict(color="#999", dash="dash")), 1, 1)
    fig.update_xaxes(title_text="시간 [s]")
    st.plotly_chart(lstyle(fig, height=360), width="stretch", key="l2_spd")
    st.table({"제어기": [x[0] for x in rows], "오버슈트 [%]": [f"{x[1]:.1f}" for x in rows],
              "상승 시간 [ms]": [f"{x[2] * 1000:.1f}" for x in rows], "부하 투입 시 속도 저하 [rpm]": [f"{x[3]:.0f}" for x in rows]})
    g = r["gains"]
    st.caption(f"속도 PI 이득: Kp = J·ωcs/K = {g['Kps']:.3f} A·s/rad, Ki = Kp·ωcs/5 = {g['Kis']:.1f} A/rad (전류 제어 1000 Hz)")
    if book:
        st.caption("토크 제한(정격 토크)에 걸려 있는 동안 속도는 직선으로 오르고(가속도 = Te정격/J), 지령에 닿으면 토크가 0 근처로 떨어짐 — 교재 그림 2.70.")
    wv = np.logspace(0, 5, 600)
    figb = make_subplots(rows=1, cols=2, subplot_titles=("속도 제어 개루프 보드 (크기 dB)", "PI 폐루프 응답의 두 성분 (전류 제어 이상적)"))
    for bwh, col in ((50, "#1d4ed8"), (100, "#d62828")):
        mag, ph = ch2.speed_open_bode(P, 2 * math.pi * bwh, 2 * math.pi * 1000, wv)
        figb.add_trace(go.Scatter(x=wv, y=mag, name=f"ωcs = {bwh} Hz", line=dict(color=col)), 1, 1)
    figb.add_hline(y=0, line=dict(dash="dot"), row=1, col=1)
    tt = np.linspace(0, 0.06, 400)
    y1, y2, zeta, wn = ch2.pi_speed_decomposition(P, 2 * math.pi * bw, tt)
    figb.add_trace(go.Scatter(x=tt * 1000, y=y1, name="ωn²/(s²+2ζωn s+ωn²)", line=dict(dash="dot")), 1, 2)
    figb.add_trace(go.Scatter(x=tt * 1000, y=y2, name="2ζωn s/(…) — 영점 항 (오버슈트의 근원)", line=dict(dash="dash")), 1, 2)
    figb.add_trace(go.Scatter(x=tt * 1000, y=y1 + y2, name="합 = PI 응답", line=dict(width=3)), 1, 2)
    figb.update_xaxes(type="log", title_text="ω [rad/s]", row=1, col=1); figb.update_xaxes(title_text="시간 [ms]", row=1, col=2)
    st.plotly_chart(lstyle(figb, height=340), width="stretch", key="l2_spd_bode")
    st.caption(f"감쇠비 ζ = √(ωcs/ωpi)/2 = √5/2 = {zeta:.3f} (과감쇠) 인데도 영점 항 때문에 오버슈트가 생김.")
    st.markdown("##### 같은 오버슈트가 되도록 IP 제어기 대역폭을 키우면 (교재: 약 5.44 배)")
    r_pi = _sim_spd(_pt(P), bw, 1.0, 1000, 3.0, 0.01, None, 0.3, 0.15)
    r_ip = _sim_spd(_pt(P), bw * 5.44, 0.0, 1000, 3.0, 0.01, None, 0.3, 0.15)
    figi = go.Figure()
    figi.add_trace(go.Scatter(x=r_pi["t"], y=r_pi["w"] * RPM, name=f"PI ({bw} Hz)"))
    figi.add_trace(go.Scatter(x=r_ip["t"], y=r_ip["w"] * RPM, name=f"IP ({bw * 5.44:.0f} Hz)"))
    figi.update_xaxes(title_text="시간 [s] (0.15 s 에 부하 3 N·m)"); figi.update_yaxes(title_text="속도 [rpm]")
    st.plotly_chart(lstyle(figi, height=300), width="stretch", key="l2_ip544")
    check("PI 는 영점 때문에 오버슈트가 생기고, IP 는 오버슈트가 없지만 지령 응답이 느림",
          "외란(부하) 응답은 PI 와 IP 가 같음 → α 로 지령 응답과 외란 응답을 절충",
          "대역폭 50 → 100 Hz 로 키우면 빨라지고 부하 투입 시 속도 저하도 줄어듦")


def _chopper():
    ref("2.8 전력 변환 장치 — 1상한 초퍼, 4상한 초퍼(H-브리지) 바이폴라·유니폴라 PWM / 2.9.4 초퍼 구동 시스템 (5 kHz, 유니폴라)")
    P = _motor_inputs("l2p_", show=False)
    c = st.columns(5)
    mode = c[0].radio("방식", ["1상한", "바이폴라", "유니폴라"], index=2, key="l2p_mode")
    va = c[1].slider("평균 전압 지령 Va* [V]", -140.0 if mode != "1상한" else 0.0, 140.0, 70.0, 5.0, key=f"l2p_va_{mode}")
    fsw = c[2].selectbox("스위칭 주파수", [1000, 2000, 5000, 10000], index=2, format_func=lambda x: f"{x / 1000:g} kHz", key="l2p_f")
    rpm = c[3].slider("전동기 속도 (고정) [rpm]", 0, 3000, 1450, 50, key="l2p_rpm")
    tsel = c[4].slider("회로도에 보일 시점 [주기 %]", 0, 99, 20, 1, key="l2p_t")
    E = P["K"] * rpm / RPM
    w = _chop(mode, P["V"], va, fsw, P["Ra"], P["La"], E)
    k = int(tsel / 100 * len(w["t"]) / 3)
    if mode == "1상한":
        st_ = {"T1": bool(w["S1"][k]), "T4": True}
        title = "1상한 초퍼 (T4 는 항상 켜짐, T2 쪽 다이오드로 환류)"
    elif mode == "바이폴라":
        st_ = {"T1": bool(w["S1"][k]), "T4": bool(w["S1"][k]), "T2": bool(w["S2"][k]), "T3": bool(w["S2"][k])}
        title = "바이폴라: 대각 스위치 (T1·T4) ↔ (T2·T3) 를 쌍으로"
    else:
        st_ = {"T1": bool(w["S1"][k]), "T2": not bool(w["S1"][k]), "T3": bool(w["S2"][k]), "T4": not bool(w["S2"][k])}
        title = "유니폴라: A 레그는 Va*, B 레그는 −Va* 와 삼각파 비교"
    c = st.columns([2, 3])
    c[0].plotly_chart(hbridge(st_, i_dir=1 if w["i"][k] > 0 else -1 if w["i"][k] < 0 else 0,
                              va_label=f"va = {w['v'][k]:+.0f} V", title=title), width="stretch", key="l2_hb")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        subplot_titles=("삼각 반송파와 지령", "스위칭 신호", "출력 전압 va [V]", "전기자 전류 ia [A]"))
    tm = w["t"] * 1000
    fig.add_trace(go.Scatter(x=tm, y=w["tri"] if mode != "1상한" else (w["tri"] + 1) / 2, name="반송파", line=dict(color="#999")), 1, 1)
    fig.add_hline(y=va / P["V"], line=dict(color="#d62828"), row=1, col=1)
    if mode == "유니폴라":
        fig.add_hline(y=-va / P["V"], line=dict(color="#1d4ed8"), row=1, col=1)
    fig.add_trace(go.Scatter(x=tm, y=w["S1"], name="Sa (T1)", line=dict(shape="hv", color="#d62828")), 2, 1)
    fig.add_trace(go.Scatter(x=tm, y=w["S2"] * 0.9, name="Sb (T3)" if mode == "유니폴라" else "T2·T3", line=dict(shape="hv", color="#1d4ed8")), 2, 1)
    fig.add_trace(go.Scatter(x=tm, y=w["v"], name="va", line=dict(shape="hv", color="#264653")), 3, 1)
    fig.add_hline(y=float(np.mean(w["v"])), line=dict(dash="dot", color="#e76f51"), row=3, col=1)
    fig.add_trace(go.Scatter(x=tm, y=w["i"], name="ia", line=dict(color="#e76f51")), 4, 1)
    fig.add_vline(x=tm[k], line=dict(color="#16a34a", dash="dot"))
    fig.update_xaxes(title_text="시간 [ms]", row=4, col=1)
    c[1].plotly_chart(lstyle(fig, height=560, showlegend=False), width="stretch", key="l2_pwm")
    rows = []
    for m in ("바이폴라", "유니폴라"):
        ww = _chop(m, P["V"], va, fsw, P["Ra"], P["La"], E)
        rows.append((m, float(np.mean(ww["v"])), float(np.ptp(ww["i"]))))
    st.table({"방식": [r[0] for r in rows], "평균 전압 [V]": [f"{r[1]:.1f}" for r in rows], "전류 리플 (최대−최소) [A]": [f"{r[2]:.2f}" for r in rows]})
    check("바이폴라는 va 가 +Vdc ↔ −Vdc 로, 유니폴라는 +Vdc ↔ 0 (또는 0 ↔ −Vdc) 로 바뀜 → 유니폴라 전류 리플이 훨씬 작음",
          "유니폴라는 출력 전압 펄스가 스위칭 주파수의 2배로 나와 리플이 줄어듦",
          "1상한 초퍼는 전압·전류가 한 방향뿐 → 역회전·회생 제동 불가, H-브리지는 4상한 운전 가능")
    st.markdown("##### 지령 Va* 를 +Vdc 에서 −Vdc 로 천천히 바꿀 때의 출력 전압 (교재 그림 아래쪽)")
    figr = make_subplots(rows=1, cols=2, subplot_titles=("바이폴라", "유니폴라"))
    for col, m in ((1, "바이폴라"), (2, "유니폴라")):
        tr_, vr_, v_ = ch2.chopper_ramp(m, P["V"], 1000)
        figr.add_trace(go.Scatter(x=tr_ * 1000, y=v_, name=f"{m} va", line=dict(width=1, shape="hv")), 1, col)
        figr.add_trace(go.Scatter(x=tr_ * 1000, y=vr_, name="평균 전압 Va*", line=dict(color="#d62828", width=2)), 1, col)
    figr.update_xaxes(title_text="시간 [ms]")
    st.plotly_chart(lstyle(figr, height=300, showlegend=False), width="stretch", key="l2_ramp")
    st.caption("바이폴라: 0 V 근처에서도 ±Vdc 펄스 (부드럽게 0 을 지남). 유니폴라: + 쪽은 +Vdc/0, − 쪽은 0/−Vdc 펄스.")
    st.markdown("##### 2.9.4 초퍼가 포함된 전체 구동 시스템 (속도 PI → 전류 PI → 초퍼 스위칭 → 전동기)")
    c = st.columns(3)
    dmode = c[0].radio("PWM 방식", ["유니폴라", "바이폴라"], horizontal=True, key="l2d_m")
    dfsw = c[1].selectbox("스위칭 주파수", [2000, 5000, 10000], index=1, format_func=lambda x: f"{x // 1000} kHz", key="l2d_f")
    dbw = c[2].selectbox("속도 제어 대역폭", [20, 50], index=1, format_func=lambda x: f"{x} Hz", key="l2d_bw")
    d = _drive(_pt(TEXTBOOK), dmode, dfsw, dbw)
    figd = make_subplots(rows=1, cols=2, subplot_titles=("속도 지령·속도 [r/min]", "전기자 전류 Ia [A] · 토크 Te [N·m]"))
    figd.add_trace(go.Scatter(x=d["t"], y=np.where(d["t"] >= 0.05, 2500, 0), name="지령", line=dict(dash="dash", color="#999")), 1, 1)
    figd.add_trace(go.Scatter(x=d["t"], y=d["w"] * RPM, name="속도"), 1, 1)
    figd.add_trace(go.Scatter(x=d["t"], y=d["ia"], name="Ia", line=dict(width=1)), 1, 2)
    figd.add_trace(go.Scatter(x=d["t"], y=d["Te"], name="Te", line=dict(width=1)), 1, 2)
    figd.update_xaxes(title_text="시간 [s]")
    st.plotly_chart(lstyle(figd, height=320), width="stretch", key="l2_drive")
    z = (d["t"] >= 0.1) & (d["t"] <= 0.1 + 3 / dfsw)
    figz = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=("Vref 와 반송파", "스위칭 펄스 Sa, Sb", "출력 전압 Va 와 전류 Ia"))
    tz = (d["t"][z] - 0.1) * 1000
    figz.add_trace(go.Scatter(x=tz, y=d["tri"][z], name="반송파", line=dict(color="#999")), 1, 1)
    figz.add_trace(go.Scatter(x=tz, y=d["vref"][z] / TEXTBOOK["V"], name="Vref/Vdc"), 1, 1)
    if dmode == "유니폴라":
        figz.add_trace(go.Scatter(x=tz, y=-d["vref"][z] / TEXTBOOK["V"], name="−Vref/Vdc"), 1, 1)
    figz.add_trace(go.Scatter(x=tz, y=d["Sa"][z] + 1.2, name="Sa", line=dict(shape="hv")), 2, 1)
    figz.add_trace(go.Scatter(x=tz, y=d["Sb"][z], name="Sb", line=dict(shape="hv")), 2, 1)
    figz.add_trace(go.Scatter(x=tz, y=d["va"][z], name="Va", line=dict(shape="hv")), 3, 1)
    figz.add_trace(go.Scatter(x=tz, y=d["ia"][z] * 4, name="Ia × 4", line=dict(color="#e76f51")), 3, 1)
    figz.update_xaxes(title_text="시간 [ms] (t = 0.1 s 부근 확대)", row=3, col=1)
    st.plotly_chart(lstyle(figz, height=460), width="stretch", key="l2_drive_zoom")
    st.caption("초퍼가 만든 PWM 전압 때문에 전기자 전류와 토크에 스위칭 주파수 리플이 남음 (교재 그림 2.72).")
    link("회로 시뮬레이터에서 H-브리지를 직접 연결해 보기 (예제 'H-브리지 4상한 초퍼')", "circuit")


def render():
    st.title("📗 2장 직류 전동기의 토크 제어")
    st.caption("강의 자료 2장의 정상상태·과도 특성, 전류·속도 제어기, 초퍼 PWM 을 직접 바꿔 가며 확인합니다.")
    tabs = st.tabs(["2.1 종류·원리", "2.3 정상상태 특성", "2.4 과도 특성", "2.5 제어 기초 (P·I·PI)",
                    "2.6 전류 제어기", "2.7 속도 제어기 (PI·IP)", "2.8 초퍼 (PWM)"])
    for tab, fn in zip(tabs, (_types, _steady, _transient, _control_basics, _current, _speed, _chopper)):
        with tab:
            fn()
