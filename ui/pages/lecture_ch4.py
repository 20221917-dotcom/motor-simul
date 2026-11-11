"""강의 실습 4장: 교류 전동기의 회전 원리 (유도 전동기, 동기 전동기)."""
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lectures import ch4
from lectures.ch4 import IM
from ui.lecture_draw import im_equivalent, phasors
from ui.pages.lecture_common import check, link, lstyle, ref
from ui.plots import info_metric

COL = {"a": "#d62828", "b": "#2a9d8f", "c": "#1d4ed8"}


def _im_inputs(key):
    M = dict(IM)
    with st.expander("유도 전동기 파라미터 (기본값 = 유도전동기 시뮬레이터와 같은 380 V, 60 Hz, 4극)", expanded=False):
        c = st.columns(6)
        M["Rs"] = c[0].number_input("Rs [Ω]", 0.01, 5.0, M["Rs"], 0.05, key=key + "Rs")
        M["Rr"] = c[1].number_input("Rr′ [Ω]", 0.01, 5.0, M["Rr"], 0.05, key=key + "Rr")
        M["Xls"] = c[2].number_input("Xls [Ω]", 0.05, 10.0, round(M["Xls"], 3), 0.05, key=key + "Xls")
        M["Xlr"] = c[3].number_input("Xlr′ [Ω]", 0.05, 10.0, round(M["Xlr"], 3), 0.05, key=key + "Xlr")
        M["Xm"] = c[4].number_input("Xm [Ω]", 1.0, 200.0, round(M["Xm"], 2), 1.0, key=key + "Xm")
        M["P"] = int(c[5].selectbox("극수 P", [2, 4, 6, 8], index=1, key=key + "P"))
    return M


# ---------------------------------------------------------------- 4.1.2 회전자계
@st.cache_data(max_entries=32, show_spinner=False)
def _mmf_fig(mode, poles, unb, f):
    phi = np.linspace(0, 2 * math.pi, 361)
    T = 1 / f
    ts = np.linspace(0, T, 25)
    deg = np.degrees(phi)
    def traces(t):
        F, Fs, cur = ch4.mmf(phi, t, f, poles, mode=mode, unbalance=unb)
        out = [go.Scatter(x=deg, y=F[k], name=f"{p}상 기자력", line=dict(color=COL[p], width=1.4, dash="dot"), xaxis="x", yaxis="y")
               for k, p in enumerate("abc")]
        out.append(go.Scatter(x=deg, y=Fs, name="합성 기자력", line=dict(color="#111", width=3), xaxis="x", yaxis="y"))
        k = int(np.argmax(Fs)); ang = phi[k]; amp = Fs[k]
        out.append(go.Scatterpolar(r=[0, max(amp, 0)], theta=[0, math.degrees(ang)], mode="lines+markers", line=dict(color="#111", width=4),
                                   marker=dict(size=[0, 10]), name="합성 기자력 최대 위치", subplot="polar"))
        for kk, p in enumerate("abc"):
            out.append(go.Scatterpolar(r=[0, abs(cur[kk])], theta=[0, (120 * kk if cur[kk] >= 0 else 120 * kk + 180) / (poles / 2)],
                                       mode="lines", line=dict(color=COL[p], width=2), name=f"{p}상 축 방향 성분", subplot="polar", showlegend=False))
        return out
    fig = go.Figure(data=traces(0.0))
    fig.frames = [go.Frame(data=traces(t), name=f"{k}") for k, t in enumerate(ts)]
    fig.update_layout(
        xaxis=dict(domain=[0, 0.62], title="공극 둘레 위치 (기계각) [°]", dtick=45), yaxis=dict(range=[-1.7, 1.7], title="기자력 (단위값)"),
        polar=dict(domain=dict(x=[0.7, 1.0], y=[0.05, 0.95]), radialaxis=dict(range=[0, 1.7], showticklabels=False), angularaxis=dict(direction="counterclockwise")),
        height=420, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", legend=dict(orientation="h", y=1.08),
        updatemenus=[dict(type="buttons", x=0.0, y=-0.18, xanchor="left", buttons=[
            dict(label="▶ 재생", method="animate", args=[None, dict(frame=dict(duration=120, redraw=True), fromcurrent=True, mode="immediate")]),
            dict(label="⏸ 멈춤", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
        sliders=[dict(x=0.15, y=-0.12, len=0.85, currentvalue=dict(prefix="시간 (전원 1주기 중) "),
                      steps=[dict(method="animate", label=f"{k * 15}°", args=[[f"{k}"], dict(mode="immediate", frame=dict(duration=0, redraw=True))])
                             for k in range(len(ts))])])
    return fig


def _rotating():
    ref("4.1.2 회전 원리 — 120° 간격 3상 권선 + 120° 위상차 전류 → 크기 일정한 회전자계, 동기 속도 ns = 120f/P")
    c = st.columns(4)
    mode = c[0].selectbox("전류 조건", ["평형 3상", "불평형 (c상 크기 변경)", "한 상 단선 (b상 끊김)", "단상 (a상만)"], key="l4r_mode")
    poles = int(c[1].selectbox("극수 P", [2, 4, 6], key="l4r_P"))
    unb = c[2].slider("c상 전류 크기", 0.0, 1.5, 0.5, 0.1, key="l4r_unb", disabled=not mode.startswith("불평형"))
    f = c[3].number_input("주파수 f [Hz]", 1.0, 400.0, 60.0, 5.0, key="l4r_f")
    st.plotly_chart(_mmf_fig(mode, poles, unb, 60.0), width="stretch", key="l4_mmf")
    c = st.columns(3)
    info_metric(c[0], "동기 속도 ns = 120f/P", f"{ch4.sync_speed_rpm(f, poles):.0f} rpm")
    info_metric(c[1], "전원 1주기 동안 회전", f"기계각 {720 / poles:.0f}°", "2/P 바퀴")
    info_metric(c[2], "합성 기자력 크기 (평형)", "상 최대값의 1.5 배")
    check("▶ 재생: 평형 3상이면 합성 기자력(검은 선)이 모양과 크기를 유지한 채 a → b → c 방향으로 이동 = 회전자계",
          "극수를 4로 바꾸면 N–S 가 두 쌍, 1주기에 반 바퀴만 돔",
          "단상이면 제자리에서 크기만 변하는 교번 자계 (회전하지 않음), 불평형이면 회전하면서 크기가 출렁임 (타원 회전자계)")
    link("유도전동기 시뮬레이터: 실시간 회전자계와 슬립", "induction")


def _equivalent():
    ref("4.1.3 등가회로 · 4.1.4 특성 — 상당 등가회로, 전력 흐름 (공극 전력·동손·기계적 출력), 역률·효율")
    M = _im_inputs("l4e_")
    ns = 120 * M["f"] / M["P"]
    c = st.columns([1, 2])
    n = c[0].slider("회전 속도 [rpm]", 0.0, float(ns), float(ns * 0.97), float(ns / 300), key=f"l4e_n_{M['P']}")
    s = max(1 - n / ns, 1e-4)
    r = ch4.im_circuit(s, M)
    I1, I2 = complex(r["I1"]), complex(r["I2"])
    vals = dict(Rs=f"{M['Rs']:.2f}", Xls=f"{M['Xls']:.2f}", Xlr=f"{M['Xlr']:.2f}", Xm=f"{M['Xm']:.1f}", Rr_s=f"Rr′/s = {M['Rr'] / s:.2f} Ω",
                I1=f"I1 = {abs(I1):.1f} A", I2=f"I2′ = {abs(I2):.1f} A", Im=f"Im = {abs(I1 - I2):.1f} A")
    c[1].plotly_chart(im_equivalent(vals), width="stretch", key="l4_eq")
    with c[0]:
        info_metric(st, "슬립 s", f"{s:.4f}")
        info_metric(st, "토크", f"{float(r['T']):.1f} N·m")
        info_metric(st, "역률", f"{float(r['pf']):.3f} (지상)")
        info_metric(st, "효율", f"{float(r['eta']) * 100:.1f} %" if np.isfinite(r["eta"]) else "—")
    labels = ["입력 전력", "고정자 동손", "공극 전력", "회전자 동손 s·Pag", "기계적 출력 (1−s)Pag"]
    vals = [r["Pin"], r["Pcu1"], r["Pag"], r["Pcu2"], r["Pmech"]]
    fig = go.Figure(go.Bar(x=labels, y=[float(v) / 1000 for v in vals], marker_color=["#264653", "#e76f51", "#2a9d8f", "#e76f51", "#e9c46a"],
                           text=[f"{float(v) / 1000:.2f} kW" for v in vals], textposition="outside"))
    fig.update_yaxes(title_text="kW")
    st.plotly_chart(lstyle(fig, height=320, showlegend=False), width="stretch", key="l4_pf")
    check("공극 전력 Pag 중 s 만큼이 회전자 동손, (1−s) 만큼이 기계적 출력 → 효율을 위해 슬립을 작게 운전 (정격 슬립 1~5 %)",
          "속도를 낮추면(부하 증가) 전류가 크게 늘고 역률은 좋아짐, 기동(s = 1)에서는 출력 0")


def _characteristics():
    ref("4.1.4 유도 전동기의 특성 · 4.1.5 동작 모드 — 토크–속도 곡선, 최대 토크, 안정 운전점, 전동기·발전기·플러깅 모드")
    M = _im_inputs("l4c_")
    ns = 120 * M["f"] / M["P"]
    c = st.columns(3)
    load = c[0].selectbox("부하", ["일정 토크", "속도 제곱 (팬·펌프)", "없음"], key="l4c_load")
    TL = c[1].slider("부하 토크 (동기 속도 기준) [N·m]", 0.0, 150.0, 50.0, 5.0, key="l4c_TL")
    Vr = c[2].slider("전압 [% 정격]", 50, 110, 100, 5, key="l4c_V")
    V = M["V"] * Vr / 100
    s = np.linspace(2.0, -1.0, 1201)
    s = s[np.abs(s) > 1e-4]
    r = ch4.im_circuit(s, M, V)
    n = (1 - s) * ns
    Tmax, smax = ch4.max_torque(M, V)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("토크–속도 특성", "전류·역률·효율 (전동기 영역)"), column_widths=[0.6, 0.4])
    fig.add_trace(go.Scatter(x=n, y=r["T"], name="전동기 토크", line=dict(color="#264653", width=3)), 1, 1)
    fn = {"일정 토크": lambda x: TL + 0 * x, "속도 제곱 (팬·펌프)": lambda x: TL * (x / ns) ** 2, "없음": lambda x: 0 * x}[load]
    nn = np.linspace(0, ns, 200)
    if load != "없음":
        fig.add_trace(go.Scatter(x=nn, y=fn(nn), name="부하 토크", line=dict(color="#e76f51", width=2)), 1, 1)
        pts, _ = ch4.operating_points(M, fn, V)
        for nk, stable in pts:
            fig.add_trace(go.Scatter(x=[nk], y=[float(fn(np.array([nk]))[0])], mode="markers",
                                     marker=dict(size=13, color="#16a34a" if stable else "#d62828", symbol="circle" if stable else "x"),
                                     name="안정 운전점" if stable else "불안정 운전점"), 1, 1)
    for x0, x1, lab, colr in ((-ns, 0, "플러깅 (s > 1)", "rgba(29,78,216,0.08)"), (0, ns, "전동기 (0 < s < 1)", "rgba(42,157,143,0.08)"),
                              (ns, 2 * ns, "발전기 (s < 0)", "rgba(231,111,81,0.08)")):
        fig.add_vrect(x0=x0, x1=x1, fillcolor=colr, line_width=0, row=1, col=1)
        fig.add_annotation(x=(x0 + x1) / 2, y=1.0, yref="y domain", text=lab, showarrow=False, font=dict(size=11))
    fig.add_trace(go.Scatter(x=[(1 - smax) * ns], y=[Tmax], mode="markers+text", text=["최대 토크"], textposition="top center",
                             marker=dict(size=10, color="#111"), name="최대 토크"), 1, 1)
    m = (s > 0) & (s <= 1)
    fig.add_trace(go.Scatter(x=n[m], y=np.abs(r["I1"][m]), name="전류 [A]"), 1, 2)
    fig.add_trace(go.Scatter(x=n[m], y=r["pf"][m] * 100, name="역률 [%]"), 1, 2)
    fig.add_trace(go.Scatter(x=n[m], y=r["eta"][m] * 100, name="효율 [%]"), 1, 2)
    fig.update_xaxes(title_text="속도 [rpm]")
    fig.update_yaxes(title_text="토크 [N·m]", row=1, col=1)
    st.plotly_chart(lstyle(fig, height=420), width="stretch", key="l4_tn")
    c = st.columns(4)
    info_metric(c[0], "최대 토크", f"{Tmax:.0f} N·m", f"슬립 {smax:.3f} ({(1 - smax) * ns:.0f} rpm)")
    info_metric(c[1], "기동 토크 (s = 1)", f"{float(ch4.im_circuit(1.0, M, V)['T']):.0f} N·m")
    info_metric(c[2], "기동 전류", f"{float(abs(ch4.im_circuit(1.0, M, V)['I1'])):.0f} A")
    info_metric(c[3], "동기 속도", f"{ns:.0f} rpm")
    check("최대 토크 속도보다 빠른 쪽(오른쪽 경사)의 교점이 안정, 왼쪽은 불안정 (부하를 키워 교점 두 개를 만들어 보세요)",
          "전압을 낮추면 토크가 전압의 제곱으로 줄어듦 (최대 토크 슬립은 그대로)",
          "동기 속도보다 빠르면 토크가 음(발전기), 역회전 중이면 플러깅(제동)")


def _rotor_types():
    ref("4.1.6 회전자 구조에 따른 특성 — 회전자 저항의 영향, 심구형·2중 농형 회전자 (기동 시 고저항, 운전 시 저저항)")
    M = dict(IM)
    ns = 120 * M["f"] / M["P"]
    s = np.linspace(1.0, 0.002, 400)
    n = (1 - s) * ns
    fig = make_subplots(rows=1, cols=2, subplot_titles=("토크–속도", "전류–속도"))
    for lab, Rr, colr in (("일반 농형 (저저항 0.4 Ω)", 0.4, "#264653"), ("고저항 농형 (1.6 Ω)", 1.6, "#e76f51")):
        r = ch4.im_circuit(s, dict(M, Rr=Rr))
        fig.add_trace(go.Scatter(x=n, y=r["T"], name=lab, line=dict(color=colr)), 1, 1)
        fig.add_trace(go.Scatter(x=n, y=np.abs(r["I1"]), name=lab, line=dict(color=colr), showlegend=False), 1, 2)
    c = st.columns(4)
    Ro = c[0].slider("바깥 도체 저항 [Ω]", 0.5, 5.0, 2.0, 0.1, key="l4t_Ro")
    Xo = c[1].slider("바깥 도체 리액턴스 [Ω]", 0.1, 3.0, 0.6, 0.1, key="l4t_Xo")
    Ri = c[2].slider("안쪽 도체 저항 [Ω]", 0.1, 1.0, 0.3, 0.05, key="l4t_Ri")
    Xi = c[3].slider("안쪽 도체 리액턴스 [Ω]", 0.5, 8.0, 3.0, 0.1, key="l4t_Xi")
    T2, I2 = ch4.double_cage_torque(s, M, Ro, Xo, Ri, Xi)
    fig.add_trace(go.Scatter(x=n, y=T2, name="2중 농형", line=dict(color="#2a9d8f", width=3)), 1, 1)
    fig.add_trace(go.Scatter(x=n, y=I2, name="2중 농형", line=dict(color="#2a9d8f", width=3), showlegend=False), 1, 2)
    fig.update_xaxes(title_text="속도 [rpm]")
    st.plotly_chart(lstyle(fig, height=380), width="stretch", key="l4_cage")
    check("회전자 저항이 크면 기동 토크가 크고 기동 전류가 작지만, 운전 슬립이 커져 효율이 나쁨",
          "2중 농형: 기동 때(회전자 주파수 60 Hz)는 리액턴스가 큰 안쪽 도체에 전류가 못 들어가 바깥 고저항 도체가 일함, "
          "운전 때(1~3 Hz)는 안쪽 저저항 도체가 일함 → 두 장점을 모두 얻음")


def _tests():
    ref("4.1.7 유도 전동기의 정수 측정 — 고정자 저항 측정, 무부하 시험, 구속 시험")
    st.markdown("기준 전동기(파라미터를 알고 있는 전동기)로 세 가지 시험을 **가상으로** 해서 측정값을 만들고, 교재 방법으로 등가회로 정수를 다시 구합니다. "
                "측정값을 직접 바꿔 넣어 볼 수도 있습니다.")
    meas = ch4.run_tests()
    c = st.columns(4)
    m = {}
    m["R_ll"] = c[0].number_input("① 단자 사이 직류 저항 [Ω]", 0.01, 20.0, round(meas["R_ll"], 3), 0.01, key="l4m_R")
    m["V_nl"] = c[1].number_input("② 무부하: 선간 전압 [V]", 10.0, 1000.0, round(meas["V_nl"], 1), 1.0, key="l4m_Vn")
    m["I_nl"] = c[1].number_input("② 무부하: 상전류 [A]", 0.1, 100.0, round(meas["I_nl"], 3), 0.01, key="l4m_In")
    m["P_nl"] = c[1].number_input("② 무부하: 3상 입력 전력 [W]", 0.0, 10000.0, round(meas["P_nl"], 1), 1.0, key="l4m_Pn")
    m["V_bl"] = c[2].number_input("③ 구속: 선간 전압 [V]", 1.0, 1000.0, round(meas["V_bl"], 2), 0.5, key="l4m_Vb")
    m["I_bl"] = c[2].number_input("③ 구속: 상전류 [A]", 0.1, 200.0, round(meas["I_bl"], 2), 0.1, key="l4m_Ib")
    m["P_bl"] = c[2].number_input("③ 구속: 3상 입력 전력 [W]", 1.0, 50000.0, round(meas["P_bl"], 1), 1.0, key="l4m_Pb")
    split = c[3].slider("Xls : Xlr′ 분배 (Xls 비율)", 0.3, 0.7, 0.5, 0.05, key="l4m_sp", help="NEMA A·D 급은 0.5, B 급 0.4, C 급 0.3")
    est = ch4.estimate_params(m, split=split)
    keys = [("Rs", "Rs [Ω]"), ("Rr", "Rr′ [Ω]"), ("Xls", "Xls [Ω]"), ("Xlr", "Xlr′ [Ω]"), ("Xm", "Xm [Ω]")]
    st.table({"정수": [k[1] for k in keys], "시험으로 구한 값": [f"{est[k[0]]:.3f}" for k in keys],
              "기준 전동기 실제 값": [f"{IM[k[0]]:.3f}" for k in keys],
              "오차": [f"{(est[k[0]] / IM[k[0]] - 1) * 100:+.1f} %" for k in keys]})
    st.latex(r"R_s=\tfrac{R_{LL}}{2},\quad R_s+R_r'=\frac{P_{BL}}{3I_{BL}^2},\quad X_{ls}+X_{lr}'=\sqrt{\Big(\frac{V_{BL}/\sqrt3}{I_{BL}}\Big)^2-\Big(\frac{P_{BL}}{3I_{BL}^2}\Big)^2},\quad X_{ls}+X_m\approx\frac{V_{NL}/\sqrt3}{I_{NL}}")
    check("구속 시험에서는 자화 가지를 무시하므로 Rr′ 를 조금 작게 구함 (Xm 이 유한해서 생기는 근사 오차)",
          "무부하 입력 전력에서 고정자 동손을 빼면 철손 + 기계손")


@st.cache_data(max_entries=8, show_spinner=False)
def _regions(Ilim):
    return ch4.speed_regions(npts=70, I_lim=Ilim)


def _speed_control():
    ref("4.1.8 유도 전동기의 속도 제어 — 고정자 전압 제어, 회전자 저항 제어, 주파수 제어, V/f 일정 제어 · 4.1.9 속도 영역")
    M = dict(IM)
    c = st.columns(2)
    method = c[0].radio("방법", ["고정자 전압 제어", "회전자 저항 제어 (권선형)", "주파수 제어 (전압 일정)", "V/f 일정 제어"], index=3, key="l4s_m")
    TLv = c[1].slider("부하 토크 (일정) [N·m]", 0.0, 80.0, 40.0, 5.0, key="l4s_TL")
    fig = go.Figure()
    s = np.linspace(1.0, 0.0005, 500)
    cols = ["#264653", "#2a9d8f", "#e9c46a", "#e76f51", "#d62828"]
    if method.startswith("고정자"):
        cases = [(f"V = {k}%", dict(V=M["V"] * k / 100), M["f"]) for k in (100, 85, 70, 55)]
    elif method.startswith("회전자"):
        cases = [(f"Rr′ = {k:g} Ω", dict(Rr=k), M["f"]) for k in (0.4, 1.0, 2.0, 4.0)]
    elif method.startswith("주파수"):
        cases = [(f"f = {k} Hz", dict(), k) for k in (30, 45, 60, 75, 90)]
    else:
        cases = [(f"f = {k} Hz, V = {M['V'] * k / 60:.0f} V", dict(V=M["V"] * k / 60), k) for k in (10, 20, 30, 45, 60)]
    rows = []
    for (lab, kw, f), colr in zip(cases, cols):
        MM = dict(M, **kw)
        V = MM["V"]
        r = ch4.im_circuit(s, MM, V, f)
        fig.add_trace(go.Scatter(x=r["n"], y=r["T"], name=lab, line=dict(color=colr)))
        pts, ns = ch4.operating_points(MM, lambda x: TLv + 0 * x, V, f)
        st_pts = [p for p in pts if p[1]]
        if st_pts:
            fig.add_trace(go.Scatter(x=[st_pts[-1][0]], y=[TLv], mode="markers", marker=dict(size=11, color=colr), showlegend=False))
            rows.append((lab, f"{st_pts[-1][0]:.0f}", f"{(1 - st_pts[-1][0] / ns) * 100:.1f} %"))
        else:
            rows.append((lab, "정지 (토크 부족)", "—"))
    fig.add_hline(y=TLv, line=dict(color="#999", dash="dash"))
    fig.update_xaxes(title_text="속도 [rpm]", rangemode="tozero"); fig.update_yaxes(title_text="토크 [N·m]", rangemode="tozero")
    st.plotly_chart(lstyle(fig, height=380), width="stretch", key="l4_sc")
    st.table({"조건": [r[0] for r in rows], "운전 속도 [rpm]": [r[1] for r in rows], "슬립": [r[2] for r in rows]})
    check("전압·회전자 저항 제어는 슬립을 키워 속도를 낮춤 → 손실(회전자 동손) 증가, 범위 좁음",
          "주파수만 바꾸면 자속이 1/f 로 변해 고주파에서 토크가 1/f² 로 줄어듦 → V/f 일정 제어로 자속을 유지하면 곡선이 평행 이동",
          "V/f 일정 제어에서도 저주파에서는 고정자 저항 강하 때문에 최대 토크가 줄어듦 (10 Hz 곡선)")
    st.markdown("##### 4.1.9 속도 영역: 정격 전류·정격 전압 안에서 낼 수 있는 최대 토크")
    Ilim = st.slider("전류 한계 [A]", 8.0, 30.0, float(IM["I_rated"]), 1.0, key="l4s_I")
    R = _regions(Ilim)
    ns_b = 120 * IM["f"] / IM["P"]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("토크·출력", "전압·슬립 주파수·주파수"))
    fig.add_trace(go.Scatter(x=R["n"], y=R["T"], name="최대 토크 [N·m]"), 1, 1)
    fig.add_trace(go.Scatter(x=R["n"], y=R["P"] / 1000, name="출력 [kW]"), 1, 1)
    fig.add_trace(go.Scatter(x=R["n"], y=R["V"] / IM["V"] * 100, name="전압 [% 정격]"), 1, 2)
    fig.add_trace(go.Scatter(x=R["n"], y=R["slip_f"] * 10, name="슬립 주파수 ×10 [Hz]"), 1, 2)
    fig.add_trace(go.Scatter(x=R["n"], y=R["f"], name="인버터 주파수 [Hz]"), 1, 2)
    k_brk = np.argmax(R["slip_f"] >= R["slip_f"].max() * 0.98) if R["slip_f"].max() > 0 else len(R["n"]) - 1
    for col in (1, 2):
        fig.add_vrect(x0=0, x1=ns_b, fillcolor="rgba(42,157,143,0.08)", line_width=0, row=1, col=col)
        fig.add_vrect(x0=ns_b, x1=R["n"][k_brk], fillcolor="rgba(233,196,106,0.15)", line_width=0, row=1, col=col)
        fig.add_vrect(x0=R["n"][k_brk], x1=R["n"][-1], fillcolor="rgba(231,111,81,0.10)", line_width=0, row=1, col=col)
    for x, lab in ((ns_b / 2, "일정 토크"), ((ns_b + R["n"][k_brk]) / 2, "일정 출력"), ((R["n"][k_brk] + R["n"][-1]) / 2, "특성 영역")):
        fig.add_annotation(x=x, y=1.02, yref="paper", text=lab, showarrow=False)
    fig.update_xaxes(title_text="속도 [rpm]")
    st.plotly_chart(lstyle(fig, height=360), width="stretch", key="l4_reg")
    check("기저 속도 이하: V/f 일정 → 자속 일정, 슬립 주파수 일정 → 토크 일정",
          "기저 속도 이상: 전압이 정격에 묶여 자속이 1/f 로 줄고, 슬립 주파수를 늘려 출력을 유지",
          "슬립 주파수가 최대 토크 슬립에 닿으면 그 뒤로는 토크가 1/f² 로 줄어드는 특성 영역")
    link("유도전동기 시뮬레이터: V/f · 벡터 제어 실시간", "induction")


def _synchronous():
    ref("4.2 동기 전동기 — 원통형·돌극형, 등가회로, 페이저도(부족·과여자), 토크각 δ, 릴럭턴스 토크, V 곡선, 기동 방법")
    c = st.columns(5)
    Vs = c[0].slider("상전압 Vs [V]", 100.0, 300.0, 220.0, 10.0, key="l4y_V")
    Ef = c[1].slider("여자 전압 Ef [V] (계자 전류)", 50.0, 400.0, 260.0, 5.0, key="l4y_E")
    delta = c[2].slider("토크각 δ [°]", 0.0, 180.0, 30.0, 1.0, key="l4y_d")
    Xd = c[3].slider("동기 리액턴스 Xd [Ω]", 1.0, 20.0, 6.0, 0.5, key="l4y_Xd")
    Xq = c[4].slider("q축 리액턴스 Xq [Ω] (= Xd 이면 원통형)", 1.0, 20.0, 6.0, 0.5, key="l4y_Xq")
    ws = 2 * math.pi * 60 / 2
    r = ch4.sync_phasor(Vs, Ef, math.radians(delta), Xd, Xq)
    I = r["I"]
    jXI = Vs - r["Ef"]
    sc = Vs / max(abs(I), 1e-9) * 0.6
    items = [(complex(Vs, 0), 0j, "Vs", "#111"), (r["Ef"], 0j, "Ef", "#2a9d8f"), (complex(Vs, 0), r["Ef"], "jX·I", "#e9c46a"),
             (I * sc, 0j, "Ia (배율)", "#d62828")]
    c = st.columns([2, 3])
    c[0].plotly_chart(phasors(items, title="페이저도 (Vs 기준)"), width="stretch", key="l4_ph")
    d = np.radians(np.linspace(0, 180, 181))
    Tf, Tr = ch4.sync_torque(d, Vs, Ef, Xd, Xq, ws)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.degrees(d), y=Tf, name="여자 토크 Tf", line=dict(dash="dot")))
    if abs(Xd - Xq) > 1e-9:
        fig.add_trace(go.Scatter(x=np.degrees(d), y=Tr, name="릴럭턴스 토크 Tr", line=dict(dash="dot")))
    fig.add_trace(go.Scatter(x=np.degrees(d), y=Tf + Tr, name="전체 토크", line=dict(width=3)))
    Tnow = float(sum(ch4.sync_torque(math.radians(delta), Vs, Ef, Xd, Xq, ws)))
    fig.add_trace(go.Scatter(x=[delta], y=[Tnow], mode="markers", marker=dict(size=12, color="#d62828"), name="현재"))
    kmax = int(np.argmax(Tf + Tr))
    fig.add_vrect(x0=0, x1=np.degrees(d[kmax]), fillcolor="rgba(42,157,143,0.08)", line_width=0)
    fig.add_annotation(x=np.degrees(d[kmax]) / 2, y=1.02, yref="paper", text="안정 운전 범위", showarrow=False)
    fig.update_xaxes(title_text="토크각 δ [°]"); fig.update_yaxes(title_text="토크 [N·m] (4극, 60 Hz)")
    c[1].plotly_chart(lstyle(fig, height=380), width="stretch", key="l4_td")
    c = st.columns(4)
    info_metric(c[0], "전기자 전류", f"{abs(I):.1f} A")
    lag = r["Q"] > 0
    info_metric(c[1], "역률", f"{abs(r['pf']):.3f} {'지상' if lag else '진상'}", "부족여자" if lag else "과여자")
    info_metric(c[2], "입력 전력 (3상)", f"{r['P'] / 1000:.2f} kW")
    info_metric(c[3], "토크", f"{Tnow:.1f} N·m", f"최대 {float((Tf + Tr).max()):.1f} N·m @ {np.degrees(d[kmax]):.0f}°")
    st.markdown("##### V 곡선: 부하 일정에서 여자(계자 전류)에 따른 전기자 전류")
    Efr = np.linspace(60, 450, 200)
    fig = go.Figure()
    for P_kw in (0, 5, 10, 15):
        Ia, pf = ch4.v_curve(Vs, Xd, P_kw * 1000, Efr)
        fig.add_trace(go.Scatter(x=Efr, y=Ia, name=f"부하 {P_kw} kW"))
    fig.add_vline(x=Ef, line=dict(color="#d62828", dash="dot"))
    fig.update_xaxes(title_text="여자 전압 Ef [V] (∝ 계자 전류)"); fig.update_yaxes(title_text="전기자 전류 [A]", rangemode="tozero")
    st.plotly_chart(lstyle(fig, height=330), width="stretch", key="l4_vc")
    check("Ef 를 키우면(과여자) 전류가 전압보다 앞서고(진상 역률), 줄이면(부족여자) 뒤짐 — V 곡선의 가장 낮은 점이 역률 1",
          "원통형은 δ = 90° 에서 최대 토크, 돌극형(Xq < Xd)은 릴럭턴스 토크가 더해져 최대 토크가 크고 90° 보다 앞에서 생김",
          "δ 가 최대 토크 각을 넘으면 탈조 (동기를 잃음)",
          "Ef = 0 이어도 돌극형이면 릴럭턴스 토크가 남음 (Xq 를 Xd 와 다르게 하고 Ef 를 최소로)")
    st.info("기동: 정지 상태에서 60 Hz 를 바로 걸면 평균 토크가 0 이라 기동하지 못합니다. 댐퍼 권선으로 유도 전동기처럼 기동하거나, "
            "인버터로 낮은 주파수부터 올립니다. PMSM 시뮬레이터의 '계통 직결' 탭에서 동기 운전·탈조를 볼 수 있습니다.")
    link("PMSM 시뮬레이터 (계통 직결: 동기 운전·탈조, 벡터 제어)", "pmsm")


def render():
    st.title("📕 4장 교류 전동기의 회전 원리")
    st.caption("강의 자료 4장의 회전자계, 유도 전동기 등가회로·특성·정수 측정·속도 제어, 동기 전동기를 직접 바꿔 가며 확인합니다.")
    tabs = st.tabs(["4.1.2 회전자계", "4.1.3 등가회로·전력 흐름", "4.1.4 특성·운전점", "4.1.6 회전자 구조",
                    "4.1.7 정수 측정", "4.1.8 속도 제어·영역", "4.2 동기 전동기"])
    for tab, fn in zip(tabs, (_rotating, _equivalent, _characteristics, _rotor_types, _tests, _speed_control, _synchronous)):
        with tab:
            fn()
