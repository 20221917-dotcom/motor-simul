"""강의 실습 2장: 직류 전동기의 토크 제어."""
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lectures import ch2
from lectures.ch2 import RPM, TEXTBOOK
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
def _sim_spd(Pt, bw, alpha, rpm, TLs):
    return ch2.simulate(dict(Pt), 0.3, 2e-5, alpha=alpha, w_ref=lambda t: rpm / RPM if t >= 0.01 else 0.0,
                        TL=lambda t: TLs if t >= 0.15 else 0.0, wcs=2 * math.pi * bw, wcc=2 * math.pi * 1000)


@st.cache_data(max_entries=64, show_spinner=False)
def _chop(mode, V, va, fsw, Ra, La, E):
    return ch2.chopper_waveforms(mode, V, va, fsw, Ra, La, E, periods=3)


def _motor_inputs(key, show=True):
    """교재 전동기 값 (원하면 바꿀 수 있음)."""
    P = dict(TEXTBOOK)
    if show:
        with st.expander("전동기 파라미터 (기본값 = 교재 2.9절 140 V, 25 A, 3000 r/min 전동기)", expanded=False):
            c = st.columns(5)
            P["Ra"] = c[0].number_input("Ra [Ω]", 0.05, 5.0, P["Ra"], 0.05, key=key + "Ra")
            P["La"] = c[1].number_input("La [mH]", 0.1, 50.0, P["La"] * 1e3, 0.5, key=key + "La") * 1e-3
            P["J"] = c[2].number_input("J [kg·m²]", 1e-4, 0.1, P["J"], 1e-4, format="%.4f", key=key + "J")
            P["K"] = c[3].number_input("Kφ [V·s/rad]", 0.05, 2.0, P["K"], 0.01, format="%.4f", key=key + "K")
            P["B"] = c[4].number_input("B [N·m·s]", 0.0, 0.01, P["B"], 1e-4, format="%.4f", key=key + "B")
            st.caption("교재 m-file 값은 슬라이드에 없어서, 정격(140 V, 25 A, 3000 r/min)과 '감쇠비 0.37 의 부족감쇠' 를 만족하도록 정한 값입니다.")
    return P


def _types():
    ref("2.1 직류 전동기의 구조·종류·동작 원리 (정류자와 브러시)")
    st.markdown("여자 방식(타여자·분권·직권·가동/차동 복권)별 결선도, 속도–토크 특성, 정류자와 코일 수에 따른 토크 리플, "
                "실시간 단면 애니메이션은 기존 시뮬레이터에 있습니다.")
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
    if mode.startswith("전기자"):
        for V in (35, 70, 105, 140):
            fig.add_trace(go.Scatter(x=T, y=ch2.speed_torque(T, V, P["K"], P["Ra"]) * RPM, name=f"V = {V} V"))
        c[0].caption("기울기(−Ra/K²)는 같고 무부하 속도 V/K 만 비례해서 변함 → 기저 속도 이하에서 쓰는 방법")
    else:
        for r in (1.0, 0.8, 0.6, 0.5):
            fig.add_trace(go.Scatter(x=T, y=ch2.speed_torque(T, P["V"], P["K"] * r, P["Ra"]) * RPM, name=f"Φ = {r:.0%} 정격"))
        c[0].caption("자속을 줄이면 무부하 속도는 1/Φ 로 오르고 기울기는 1/Φ² 로 가팔라짐 → 기저 속도 이상(약계자)")
    fig.update_xaxes(title_text="토크 T [N·m]"); fig.update_yaxes(title_text="속도 [rpm]", rangemode="tozero")
    c[1].plotly_chart(lstyle(fig, height=360), width="stretch", key="l2_st")
    cap = ch2.capability(P)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("능력 곡선: 토크·출력", "전압·자속"))
    x = cap["w"] * RPM
    fig.add_trace(go.Scatter(x=x, y=cap["T"], name="최대 토크 [N·m]"), 1, 1)
    fig.add_trace(go.Scatter(x=x, y=cap["P"] / 1000, name="출력 [kW]"), 1, 1)
    fig.add_trace(go.Scatter(x=x, y=cap["V"], name="전기자 전압 [V]"), 1, 2)
    fig.add_trace(go.Scatter(x=x, y=cap["K"] / P["K"] * 100, name="계자 자속 [% 정격]"), 1, 2)
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
    check("J 를 줄이거나 Ra 를 줄이면 극점에 허수부가 생겨 진동 (서보·대형 전동기), Ra 를 키우면 진동 없음 (소형 전동기)",
          "La = 0 근사(점선)는 1차 저역 통과 특성: 진동 없이 Tm 으로 올라감",
          "속도는 전압에 비례: 70 V 는 140 V 의 절반 속도")


def _control_basics():
    ref("2.5 제어 시스템 — 개루프·폐루프, P·I·PI 제어기, 정상상태 오차, 안정성(위상 여유)·대역폭")
    P = _motor_inputs("l2c_", show=False)
    st.markdown("대상: 회전자를 멈춘 전기자 회로 (Ra–La, 1차 시스템) 의 전류를 20 A 로 제어")
    c = st.columns(3)
    Kp = c[0].slider("비례 이득 Kp [V/A]", 0.5, 60.0, 15.7, 0.1, key="l2c_kp")
    Ki = c[1].slider("적분 이득 Ki [V/(A·s)]", 0.0, 5000.0, 1570.0, 10.0, key="l2c_ki")
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
    check("P 만 쓰면 오차가 남고 Kp 를 키우면 줄어듦, I 만 쓰면 오차는 없지만 느림, PI 는 둘의 장점",
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
    check("극점-영점 상쇄로 전류 응답이 1차(오버슈트 없음)가 되고 대역폭이 2배면 2배 빠름",
          "전향 보상을 끄면 역기전력(외란) 때문에 전류가 지령에 늦게 붙음 (회전 속도를 올려 보세요)",
          "전압 한계를 켜고(예: 80 V) 누적 방지를 끄면 지령이 0 으로 돌아갈 때 전류가 한동안 내려오지 않음 (wind-up)")


def _speed():
    ref("2.7 속도 제어기 — PI 속도 제어 (전류 제어 대역폭의 1/5 이하), 50 Hz / 100 Hz 비교, IP 제어기와 혼합 제어기(α)")
    P = _motor_inputs("l2w_")
    c = st.columns(5)
    bw = c[0].selectbox("속도 제어 대역폭", [20, 50, 100], index=1, format_func=lambda x: f"{x} Hz", key="l2w_bw")
    alpha = c[1].slider("α (1 = PI, 0 = IP)", 0.0, 1.0, 1.0, 0.05, key="l2w_a")
    rpm = c[2].slider("속도 지령 [rpm]", 200, 3000, 1000, 100, key="l2w_rpm")
    TLs = c[3].slider("0.15 s 에 걸리는 부하 [N·m]", 0.0, 10.0, 4.0, 0.5, key="l2w_tl")
    cmp = c[4].checkbox("PI·IP 함께 보기", True, key="l2w_cmp")
    runs = [("현재 설정", alpha, "#d62828")]
    if cmp:
        runs += [("PI (α = 1)", 1.0, "#1d4ed8"), ("IP (α = 0)", 0.0, "#2a9d8f")]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("속도 [rpm]", "전류 지령 i* [A]"))
    rows = []
    for name, a, col in runs:
        r = _sim_spd(_pt(P), bw, a, rpm, TLs)
        fig.add_trace(go.Scatter(x=r["t"], y=r["w"] * RPM, name=name, line=dict(color=col, dash=None if name == "현재 설정" else "dot")), 1, 1)
        fig.add_trace(go.Scatter(x=r["t"], y=r["istar"], name=name, line=dict(color=col, dash=None if name == "현재 설정" else "dot"), showlegend=False), 1, 2)
        os_, tr = ch2.step_metrics(r["t"][r["t"] < 0.15], r["w"][r["t"] < 0.15], rpm / RPM, 0.01)
        dip = (rpm / RPM - r["w"][r["t"] >= 0.15].min()) * RPM
        rows.append((name, os_, tr, dip))
    fig.add_trace(go.Scatter(x=r["t"], y=r["wref"] * RPM, name="지령", line=dict(color="#999", dash="dash")), 1, 1)
    fig.update_xaxes(title_text="시간 [s]")
    st.plotly_chart(lstyle(fig, height=360), width="stretch", key="l2_spd")
    st.table({"제어기": [x[0] for x in rows], "오버슈트 [%]": [f"{x[1]:.1f}" for x in rows],
              "상승 시간 [ms]": [f"{x[2] * 1000:.1f}" for x in rows], "부하 투입 시 속도 저하 [rpm]": [f"{x[3]:.0f}" for x in rows]})
    g = r["gains"]
    st.caption(f"속도 PI 이득: Kp = J·ωcs/K = {g['Kps']:.3f} A·s/rad, Ki = Kp·ωcs/5 = {g['Kis']:.1f} A/rad (전류 제어 1000 Hz)")
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
    rpm = c[3].slider("전동기 속도 (고정) [rpm]", 0, 3000, 1300, 100, key="l2p_rpm")
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
    link("회로 시뮬레이터에서 H-브리지를 직접 연결해 보기 (예제 'H-브리지 4상한 초퍼')", "circuit")


def render():
    st.title("📗 2장 직류 전동기의 토크 제어")
    st.caption("강의 자료 2장의 정상상태·과도 특성, 전류·속도 제어기, 초퍼 PWM 을 직접 바꿔 가며 확인합니다.")
    tabs = st.tabs(["2.1 종류·원리", "2.3 정상상태 특성", "2.4 과도 특성", "2.5 제어 기초 (P·I·PI)",
                    "2.6 전류 제어기", "2.7 속도 제어기 (PI·IP)", "2.8 초퍼 (PWM)"])
    for tab, fn in zip(tabs, (_types, _steady, _transient, _control_basics, _current, _speed, _chopper)):
        with tab:
            fn()
