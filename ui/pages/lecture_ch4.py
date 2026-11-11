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


# ---------------------------------------------------------------- 4.1 아라고의 원판 · 4.1.1 구조·철손
@st.fragment
def _structure():
    ref("4.1 아라고의 원판 (유도 전동기의 기본 개념) · 4.1.1 구조적 특성 — 철손 (히스테리시스·와전류), 분포권")
    st.markdown("##### 아라고의 원판: 자석을 돌리면 구리 원판이 와전류 때문에 조금 느리게 따라 돎")
    c = st.columns(4)
    vm = c[0].slider("자석 속도 [m/s] (원판 둘레 기준)", 0.0, 100.0, 40.0, 1.0, key="l4a_v")
    mat = c[1].selectbox("원판 재질", ["구리 (σ = 5.8×10⁷)", "알루미늄 (3.5×10⁷)", "스테인리스 (1.4×10⁶)", "플라스틱 (부도체)"], key="l4a_m")
    sig = {"구": 5.8e7, "알": 3.5e7, "스": 1.4e6, "플": 0.0}[mat[0]]
    Bfr = c[2].slider("마찰 제동 (상대값)", 0.0, 2.0, 0.3, 0.05, key="l4a_b")
    dv = np.linspace(0, 100, 400)
    F = ch4.arago(dv, sigma=sig) / ch4.arago(40.0)
    # 원판 속도 vd: 와전류 힘(vm − vd) = 마찰·vd
    vd_grid = np.linspace(0, vm, 2000)
    bal = ch4.arago(vm - vd_grid, sigma=sig) / ch4.arago(40.0) - Bfr * vd_grid / 40
    vd = float(vd_grid[np.argmin(np.abs(bal))]) if sig > 0 else 0.0
    fig = go.Figure(go.Scatter(x=dv, y=F, name="와전류 힘 (상대 속도 = 슬립의 함수)"))
    fig.add_trace(go.Scatter(x=[vm - vd], y=[float(ch4.arago(vm - vd, sigma=sig) / ch4.arago(40.0))], mode="markers", marker=dict(size=12, color="#d62828"), name="현재 운전점"))
    fig.update_xaxes(title_text="자석과 원판의 상대 속도 Δv [m/s]"); fig.update_yaxes(title_text="원판을 끄는 힘 (상대값)")
    c = st.columns([3, 2])
    c[0].plotly_chart(lstyle(fig, height=300), width="stretch", key="l4_arago")
    with c[1]:
        info_metric(st, "원판 속도", f"{vd:.1f} m/s", f"자석 {vm:.0f} m/s 보다 {vm - vd:.1f} m/s 느림")
        info_metric(st, "슬립 (vm − vd)/vm", f"{(vm - vd) / vm * 100:.1f} %" if vm > 0 else "—")
        st.caption("원판이 자석과 같은 속도가 되면 자속 변화가 없어 와전류·힘이 0 → 항상 조금 느리게 돎 = 유도 전동기의 슬립. 부도체는 와전류가 없어 돌지 않음.")
    st.markdown("##### 철손: 히스테리시스 손실 (루프 면적 × 주파수) 과 와전류 손실 (주파수² × 두께²)")
    c = st.columns(4)
    mat2 = c[0].radio("철심 재료", ["연자성체 (규소 강판)", "경자성체 (영구자석 재료)"], key="l4h_m")
    Hc = 40.0 if mat2.startswith("연") else 600.0
    thick = c[1].slider("강판 두께 [mm]", 0.1, 2.0, 0.35, 0.05, key="l4h_t")
    fq = c[2].slider("주파수 [Hz]", 10, 400, 60, 10, key="l4h_f")
    Bm = c[3].slider("최대 자속 밀도 [T]", 0.5, 1.8, 1.4, 0.1, key="l4h_B")
    H, up, dn, area = ch4.hysteresis_loop(2000.0, Hc, 1.6, a=200.0)
    ff = np.linspace(1, 400, 200)
    Ph, Pe = ch4.core_loss(ff, Bm, thick)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("B–H 히스테리시스 루프 (면적 = 한 주기 손실)", "주파수에 따른 철손"))
    fig.add_trace(go.Scatter(x=H, y=up, name="자화 증가", line=dict(color="#d62828")), 1, 1)
    fig.add_trace(go.Scatter(x=H, y=dn, name="자화 감소", line=dict(color="#1d4ed8")), 1, 1)
    fig.add_trace(go.Scatter(x=ff, y=Ph, name="히스테리시스 손실 ∝ f"), 1, 2)
    fig.add_trace(go.Scatter(x=ff, y=Pe, name="와전류 손실 ∝ f²·t²"), 1, 2)
    fig.add_trace(go.Scatter(x=ff, y=Ph + Pe, name="철손 합", line=dict(width=3)), 1, 2)
    fig.add_vline(x=fq, line=dict(dash="dot"), row=1, col=2)
    fig.update_xaxes(title_text="H [A/m]", row=1, col=1); fig.update_xaxes(title_text="주파수 [Hz]", row=1, col=2)
    fig.update_yaxes(title_text="B [T]", row=1, col=1); fig.update_yaxes(title_text="손실 [W/kg] (상대값)", row=1, col=2)
    st.plotly_chart(lstyle(fig, height=340), width="stretch", key="l4_loss")
    st.markdown("##### 분포권: 슬롯에 나눠 감은 도체가 만드는 계단 모양 기자력 → 정현파에 가까워짐")
    c = st.columns([1, 3])
    q = c[0].select_slider("매극 매상 슬롯 수 q", [1, 2, 3, 4, 6], value=2, key="l4w_q")
    wmode = c[0].radio("전류", ["a상만", "3상 합성 (ia = 1, ib = ic = −½)"], key="l4w_m")
    th = np.linspace(0, 2 * math.pi, 1440, endpoint=False)
    Fw, fund, kd, thd = ch4.winding_mmf(th, q, "a상만" if wmode == "a상만" else "3상")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.degrees(th), y=Fw, name="실제 기자력 (계단)", line=dict(shape="hv")))
    fig.add_trace(go.Scatter(x=np.degrees(th), y=fund, name="기본파 성분", line=dict(dash="dot")))
    fig.update_xaxes(title_text="공극 위치 (전기각) [°]", dtick=60)
    c[1].plotly_chart(lstyle(fig, height=300), width="stretch", key="l4_wind")
    info_metric(c[0], "분포 계수 kd", f"{kd:.4f}")
    info_metric(c[0], "고조파 비율 (THD)", f"{thd * 100:.1f} %", "q 를 늘리면 줄어듦")
    link("전동기 구조 페이지 (3D 구조·권선 전개도·결선도)", "structure-induction")


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


@st.fragment
def _rotating():
    ref("4.1.2 회전 원리 — 120° 간격 3상 권선 + 120° 위상차 전류 → 크기 일정한 회전자계, 동기 속도 ns = 120f/P")
    c = st.columns(4)
    mode = c[0].selectbox("전류 조건", ["평형 3상", "불평형 (c상 크기 변경)", "한 상 단선 (b상 끊김)", "단상 (a상만)"], key="l4r_mode")
    poles = int(c[1].selectbox("극수 P", [2, 4, 6], key="l4r_P"))
    unb = c[2].slider("c상 전류 크기", 0.0, 1.5, 0.5, 0.1, key="l4r_unb", disabled=not mode.startswith("불평형"))
    f = c[3].number_input("주파수 f [Hz]", 1.0, 400.0, 60.0, 5.0, key="l4r_f")
    st.plotly_chart(_mmf_fig(mode, poles, unb, 60.0), width="stretch", key="l4_mmf")
    tdeg = st.slider("시각 t (전원 전기각) [°] — 아래 전류 파형과 기자력 분포", 0, 360, 0, 15, key="l4r_t")
    tt = np.linspace(0, 360, 361)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("3상 전류", f"t = {tdeg}° 의 기자력 분포"))
    for k, p in enumerate("abc"):
        fig.add_trace(go.Scatter(x=tt, y=np.cos(np.radians(tt - 120 * k)), name=f"i{p}", line=dict(color=COL[p])), 1, 1)
    fig.add_vline(x=tdeg, line=dict(color="#111", width=2), row=1, col=1)
    phi = np.linspace(0, 2 * math.pi, 361)
    F, Fs, cur = ch4.mmf(phi, math.radians(tdeg) / (2 * math.pi * 60), 60, poles, mode=mode, unbalance=unb)
    for k, p in enumerate("abc"):
        fig.add_trace(go.Scatter(x=np.degrees(phi), y=F[k], name=f"F{p}", line=dict(color=COL[p], dash="dot"), showlegend=False), 1, 2)
    fig.add_trace(go.Scatter(x=np.degrees(phi), y=Fs, name="합성", line=dict(color="#111", width=3)), 1, 2)
    fig.update_xaxes(title_text="전원 전기각 [°]", dtick=90, row=1, col=1); fig.update_xaxes(title_text="공극 위치 (기계각) [°]", dtick=90, row=1, col=2)
    st.plotly_chart(lstyle(fig, height=300), width="stretch", key="l4_mmf2")
    st.markdown("##### 고정자 회전자계와 회전자 회전자계: 회전자 속도 nm + 슬립 속도 nr = 동기 속도 ns")
    c = st.columns([1, 2])
    sl = c[0].slider("슬립 s", 0.01, 0.5, 0.1, 0.01, key="l4r_s")
    tq = c[0].slider("시각 (전원 주기 수)", 0.0, 4.0, 1.0, 0.05, key="l4r_tq")
    ang_s = 360 * tq                       # 고정자 자계 (2극 기준)
    ang_m = 360 * tq * (1 - sl)            # 회전자 (기계)
    ang_r = ang_m + 360 * tq * sl - 105     # 회전자 자계 = 회전자 + 슬립 속도, 고정자 자계보다 (90+θ) 뒤짐
    pol = go.Figure()
    pol.add_trace(go.Scatterpolar(r=[0, 1], theta=[0, ang_s], mode="lines+markers", line=dict(color="#1d4ed8", width=6), name="고정자 회전자계 Fs (ns)"))
    pol.add_trace(go.Scatterpolar(r=[0, 0.75], theta=[0, ang_r], mode="lines+markers", line=dict(color="#d62828", width=6), name="회전자 회전자계 Fr (nm + nr)"))
    pol.add_trace(go.Scatterpolar(r=[0.95], theta=[ang_m], mode="markers", marker=dict(size=14, color="#e9c46a", symbol="star"), name="회전자 표시 (nm)"))
    pol.update_layout(height=340, margin=dict(l=30, r=30, t=20, b=20), polar=dict(radialaxis=dict(visible=False)), legend=dict(orientation="h", y=-0.12))
    c[1].plotly_chart(pol, width="stretch", key="l4_rf")
    c[0].caption("시각을 움직여 보세요: Fs 와 Fr 은 같이 돌아 사이 각이 일정 (지속적인 토크), 회전자 표시(별)는 그보다 느리게 뒤처짐.")
    c = st.columns(3)
    info_metric(c[0], "동기 속도 ns = 120f/P", f"{ch4.sync_speed_rpm(f, poles):.0f} rpm")
    info_metric(c[1], "전원 1주기 동안 회전", f"기계각 {720 / poles:.0f}°", "2/P 바퀴")
    info_metric(c[2], "합성 기자력 크기 (평형)", "상 최대값의 1.5 배")
    check("▶ 재생: 평형 3상이면 합성 기자력(검은 선)이 모양과 크기를 유지한 채 a → b → c 방향으로 이동 = 회전자계",
          "극수를 4로 바꾸면 N–S 가 두 쌍, 1주기에 반 바퀴만 돔",
          "단상이면 제자리에서 크기만 변하는 교번 자계 (회전하지 않음), 불평형이면 회전하면서 크기가 출렁임 (타원 회전자계)")
    link("유도전동기 시뮬레이터: 실시간 회전자계와 슬립", "induction")


@st.fragment
def _emf():
    ref("4.1.3 고정자 유기 기전력 (E = 4.44 f N φ Kw) · 회전자 유기 기전력과 주파수 (슬립에 비례) · 회전자 등가회로 변환")
    c = st.columns(4)
    Bmax = c[0].slider("최대 공극 자속 밀도 Bmax [T]", 0.3, 1.2, 0.8, 0.05, key="l4m_B")
    lr = c[1].slider("철심 길이 l × 반지름 r [cm²]", 20.0, 400.0, 120.0, 10.0, key="l4m_lr")
    Ns = c[2].slider("상당 직렬 턴 수 N", 20, 300, 100, 10, key="l4m_N")
    fs = c[3].slider("주파수 f [Hz]", 10, 120, 60, 5, key="l4m_f")
    phi = 2 * Bmax * lr * 1e-4
    Kw = 0.92
    E = 4.44 * fs * Ns * phi * Kw
    th = np.linspace(0, 2 * math.pi, 361)
    tt = np.linspace(0, 2 / fs, 400)
    fig = make_subplots(rows=1, cols=3, subplot_titles=("공극 자속 밀도 B(θ) = Bmax cosθ", "a상 쇄교 자속 λa(t)", "유기 기전력 ea(t) = −dλa/dt"))
    fig.add_trace(go.Scatter(x=np.degrees(th), y=Bmax * np.cos(th), name="B(θ)"), 1, 1)
    fig.add_trace(go.Scatter(x=tt * 1000, y=Ns * phi * Kw * np.cos(2 * math.pi * fs * tt), name="λa"), 1, 2)
    for k, p in enumerate("abc"):
        fig.add_trace(go.Scatter(x=tt * 1000, y=E * math.sqrt(2) * np.sin(2 * math.pi * fs * tt - 2 * math.pi * k / 3), name=f"e{p}", line=dict(color=COL[p])), 1, 3)
    fig.update_xaxes(title_text="θ [°]", row=1, col=1); fig.update_xaxes(title_text="시간 [ms]", row=1, col=2); fig.update_xaxes(title_text="시간 [ms]", row=1, col=3)
    st.plotly_chart(lstyle(fig, height=320), width="stretch", key="l4_emf")
    c = st.columns(3)
    info_metric(c[0], "극당 자속 φ = 2·Bmax·l·r", f"{phi * 1000:.2f} mWb")
    info_metric(c[1], "유기 기전력 실효값 E = 4.44 f N φ Kw", f"{E:.1f} V", f"권선 계수 Kw = {Kw}")
    info_metric(c[2], "공극 자속 ∝ E / f", f"{E / fs:.2f} V/Hz", "V/f 를 일정하게 하면 자속 일정")
    st.markdown("##### 회전자 유기 기전력과 주파수: 슬립에 비례 (정지 시 최대, 동기 속도에서 0)")
    M = dict(IM)
    ns = 120 * M["f"] / M["P"]
    n = np.linspace(0, ns, 200)
    s = 1 - n / ns
    Er0 = 1.0
    fig = make_subplots(rows=1, cols=2, subplot_titles=("회전자 기전력 Er = s·Er0 (상대값)", "회전자 주파수 fr = s·f [Hz]"))
    fig.add_trace(go.Scatter(x=n, y=s * Er0, name="Er"), 1, 1)
    fig.add_trace(go.Scatter(x=n, y=s * M["f"], name="fr"), 1, 2)
    fig.update_xaxes(title_text="회전자 속도 [rpm]")
    st.plotly_chart(lstyle(fig, height=280, showlegend=False), width="stretch", key="l4_rotemf")
    c = st.columns(3)
    sv = c[0].slider("슬립 s", 0.005, 1.0, 0.03, 0.005, key="l4m_s")
    Rr, Xr = M["Rr"], M["Xlr"]
    Ir1 = sv * 100 / complex(Rr, sv * Xr)       # 실제 회전자: sE / (R + j s X)
    Ir2 = 100 / complex(Rr / sv, Xr)            # 변환: E / (R/s + jX)
    info_metric(c[1], "실제 회전자 회로 sE/(Rr + j s Xr)", f"{abs(Ir1):.2f} A", f"주파수 fr = {sv * 60:.2f} Hz")
    info_metric(c[2], "고정자 주파수로 변환 E/(Rr/s + jXr)", f"{abs(Ir2):.2f} A", "크기가 같음 → 등가회로에 Rr/s 로 그림")


@st.fragment
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


@st.fragment
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
    fig.add_trace(go.Scatter(x=n[m], y=np.abs(r["I1"][m]), name="고정자 전류 [A]"), 1, 2)
    fig.add_trace(go.Scatter(x=n[m], y=np.abs(r["I2"][m]), name="회전자 전류 [A]", line=dict(dash="dash")), 1, 2)
    fig.add_trace(go.Scatter(x=n[m], y=(1 - s[m]) * 100, name="이상 효율 1 − s [%]", line=dict(dash="dot")), 1, 2)
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
    Vph = V / math.sqrt(3)
    ws = 2 * math.pi * M["f"] / (M["P"] / 2)
    sp = np.linspace(0.002, 1.0, 400)
    figA = go.Figure()
    figA.add_trace(go.Scatter(x=(1 - sp) * ns, y=ch4.im_circuit(sp, M, V)["T"], name="등가회로 토크", line=dict(width=3)))
    figA.add_trace(go.Scatter(x=(1 - sp) * ns, y=3 / ws * Vph ** 2 / M["Rr"] * sp, name="작은 슬립 근사 T ≈ 3Vs²s/(ωs Rr) (∝ s)", line=dict(dash="dot")))
    figA.add_trace(go.Scatter(x=(1 - sp) * ns, y=3 / ws * Vph ** 2 * M["Rr"] / ((M["Xls"] + M["Xlr"]) ** 2 * sp), name="큰 슬립 근사 T ≈ 3Vs²Rr/(ωs X² s) (∝ 1/s)", line=dict(dash="dash")))
    figA.update_yaxes(range=[0, Tmax * 1.4], title_text="토크 [N·m]"); figA.update_xaxes(title_text="속도 [rpm]")
    st.markdown("##### 토크 식의 근사: 동기 속도 근처는 슬립에 비례, 저속은 슬립에 반비례")
    st.plotly_chart(lstyle(figA, height=300), width="stretch", key="l4_approx")
    with st.expander("교재 예제 1 (5 HP, 220 V, 60 Hz, 1750 r/min, 4극, 역률 0.85, 효율 90 %) · 예제 2 (팬 부하 TL = 0.1ωm, Rr = 0.379 Ω)", expanded=False):
        c = st.columns(4)
        hp = c[0].number_input("출력 [HP]", 0.5, 100.0, 5.0, 0.5, key="l4x_hp")
        VL = c[1].number_input("선간 전압 [V]", 100.0, 1000.0, 220.0, 10.0, key="l4x_V")
        nr = c[2].number_input("정격 속도 [r/min]", 100.0, 3600.0, 1750.0, 10.0, key="l4x_n")
        pf_ = c[3].number_input("역률", 0.5, 1.0, 0.85, 0.01, key="l4x_pf")
        Pm = hp * 746; Ir = Pm / (math.sqrt(3) * VL * pf_ * 0.9); ns1 = 120 * 60 / 4; s1 = (ns1 - nr) / ns1
        st.table({"항목": ["① 정격 전류 = Pm / (√3·V·cosθ·η)", "② 동기 속도 120f/P", "② 정격 슬립", "③ 슬립 주파수 fr = s·f", "④ 정격 토크 Pm/ωm"],
                  "값": [f"{Ir:.1f} A", f"{ns1:.0f} r/min", f"{s1:.4f}", f"{s1 * 60:.3f} Hz", f"{Pm / (nr / 60 * 2 * math.pi):.2f} N·m"]})
        Rr2 = st.number_input("예제 2: Rr [Ω]", 0.05, 5.0, 0.379, 0.001, format="%.3f", key="l4x_Rr")
        ws2 = 60 * math.pi
        wgrid = np.linspace(150, ws2 - 1e-3, 20000)
        Tm = 3 / ws2 * (220 / math.sqrt(3)) ** 2 / Rr2 * (ws2 - wgrid) / ws2
        wsol = float(wgrid[np.argmin(np.abs(Tm - 0.1 * wgrid))])
        st.markdown(f"예제 2: 3/ωs·Vs²/Rr·(ωs − ωm)/ωs = 0.1·ωm 을 풀면 **ωm = {wsol:.1f} rad/s = {wsol * 60 / (2 * math.pi):.1f} r/min** (교재: 183.4 rad/s, 1751.3 r/min)")
    check("최대 토크 속도보다 빠른 쪽(오른쪽 경사)의 교점이 안정, 왼쪽은 불안정 (부하를 키워 교점 두 개를 만들어 보세요)",
          "전압을 낮추면 토크가 전압의 제곱으로 줄어듦 (최대 토크 슬립은 그대로)",
          "동기 속도보다 빠르면 토크가 음(발전기), 역회전 중이면 플러깅(제동)")


@st.fragment
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
    st.markdown("##### 심구형 도체: 회전자 주파수가 높을수록(기동 시) 유효 저항이 커짐 (표피 효과)")
    c = st.columns([1, 3])
    hb = c[0].slider("도체 깊이 [mm]", 5.0, 50.0, 25.0, 1.0, key="l4d_h")
    fr = np.linspace(0.1, 60, 300)
    figd = go.Figure(go.Scatter(x=fr, y=ch4.deep_bar_ratio(fr, hb), name="R_ac / R_dc"))
    figd.add_vrect(x0=0, x1=3, fillcolor="rgba(42,157,143,0.12)", line_width=0, annotation_text="정상 운전 (1~3 Hz)")
    figd.add_vline(x=60, line=dict(dash="dot"), annotation_text="기동 시 (60 Hz)")
    figd.update_xaxes(title_text="회전자 주파수 fr [Hz]"); figd.update_yaxes(title_text="저항비 R_ac / R_dc")
    c[1].plotly_chart(lstyle(figd, height=280), width="stretch", key="l4_deep")
    st.markdown("##### NEMA 형식별 토크–속도 특성 (A·B·C·D 급)")
    fign = go.Figure()
    for cls in ch4.NEMA:
        T2, _ = ch4.nema_curve(cls, s)
        fign.add_trace(go.Scatter(x=n, y=T2, name=cls))
    fign.update_xaxes(title_text="속도 [rpm]"); fign.update_yaxes(title_text="토크 [N·m]")
    st.plotly_chart(lstyle(fign, height=320), width="stretch", key="l4_nema")
    check("회전자 저항이 크면 기동 토크가 크고 기동 전류가 작지만, 운전 슬립이 커져 효율이 나쁨",
          "2중 농형: 기동 때(회전자 주파수 60 Hz)는 리액턴스가 큰 안쪽 도체에 전류가 못 들어가 바깥 고저항 도체가 일함, "
          "운전 때(1~3 Hz)는 안쪽 저저항 도체가 일함 → 두 장점을 모두 얻음")


@st.fragment
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


@st.cache_data(max_entries=16, show_spinner=False)
def _vf_cl(nref, TL, frm, boost):
    return ch4.vf_closed_loop([(0, 0), (0.2, nref)], [(0, 0), (2.0, TL)], fr_max=frm, boost=boost, t_end=3.0)


@st.cache_data(max_entries=8, show_spinner=False)
def _regions(Ilim):
    return ch4.speed_regions(npts=70, I_lim=Ilim)


@st.fragment
def _speed_control():
    ref("4.1.8 유도 전동기의 속도 제어 — 고정자 전압 제어, 회전자 저항 제어, 주파수 제어, V/f 일정 제어 · 4.1.9 속도 영역")
    M = dict(IM)
    c = st.columns(2)
    method = c[0].radio("방법", ["고정자 전압 제어", "회전자 저항 제어 (권선형)", "주파수 제어 (전압 일정)", "V/f 일정 제어"], index=3, key="l4s_m")
    TLv = c[1].slider("부하 토크 (동기 속도에서) [N·m]", 0.0, 80.0, 40.0, 5.0, key="l4s_TL")
    ltype = c[1].radio("부하 종류", ["일정 토크", "팬·펌프 (속도 제곱)"], horizontal=True, key="l4s_lt")
    boost = c[1].slider("V/f 저속 전압 부스트 [V]", 0.0, 40.0, 0.0, 2.0, key="l4s_bst")
    fig = go.Figure()
    s = np.linspace(1.0, 0.0005, 500)
    cols = ["#264653", "#2a9d8f", "#e9c46a", "#e76f51", "#d62828", "#7c3aed"]
    if method.startswith("고정자"):
        cases = [(f"V = {k}%", dict(V=M["V"] * k / 100), M["f"]) for k in (100, 85, 70, 55)]
    elif method.startswith("회전자"):
        cases = [(f"Rr′ = {k:g} Ω", dict(Rr=k), M["f"]) for k in (0.4, 1.0, 2.0, 4.0)]
    elif method.startswith("주파수"):
        cases = [(f"f = {k} Hz", dict(), k) for k in (20, 30, 40, 50, 60, 70)]
    else:
        cases = [(f"f = {k} Hz, V = {float(ch4.vf_voltage(k, M, boost)):.0f} V", dict(V=float(ch4.vf_voltage(k, M, boost))), k) for k in (10, 20, 30, 40, 50, 60)]
    nsync = 120 * M["f"] / M["P"]
    loadf = (lambda x: TLv + 0 * x) if ltype == "일정 토크" else (lambda x: TLv * (x / nsync) ** 2)
    rows = []
    for (lab, kw, f), colr in zip(cases, cols):
        MM = dict(M, **kw)
        V = MM["V"]
        r = ch4.im_circuit(s, MM, V, f)
        fig.add_trace(go.Scatter(x=r["n"], y=r["T"], name=lab, line=dict(color=colr)))
        pts, ns = ch4.operating_points(MM, loadf, V, f)
        st_pts = [p for p in pts if p[1]]
        if st_pts:
            fig.add_trace(go.Scatter(x=[st_pts[-1][0]], y=[float(loadf(np.array([st_pts[-1][0]]))[0])], mode="markers", marker=dict(size=11, color=colr), showlegend=False))
            rows.append((lab, f"{st_pts[-1][0]:.0f}", f"{(1 - st_pts[-1][0] / ns) * 100:.1f} %"))
        else:
            rows.append((lab, "정지 (토크 부족)", "—"))
    nn = np.linspace(0, nsync * 1.25, 200)
    fig.add_trace(go.Scatter(x=nn, y=loadf(nn), name="부하 토크", line=dict(color="#999", dash="dash")))
    fig.update_xaxes(title_text="속도 [rpm]", rangemode="tozero"); fig.update_yaxes(title_text="토크 [N·m]", rangemode="tozero")
    st.plotly_chart(lstyle(fig, height=380), width="stretch", key="l4_sc")
    st.table({"조건": [r[0] for r in rows], "운전 속도 [rpm]": [r[1] for r in rows], "슬립": [r[2] for r in rows]})
    check("전압·회전자 저항 제어는 슬립을 키워 속도를 낮춤 → 손실(회전자 동손) 증가, 범위 좁음",
          "주파수만 바꾸면 자속이 1/f 로 변해 고주파에서 토크가 1/f² 로 줄어듦 → V/f 일정 제어로 자속을 유지하면 곡선이 평행 이동",
          "V/f 일정 제어에서도 저주파에서는 고정자 저항 강하 때문에 최대 토크가 줄어듦 (10 Hz 곡선)")
    st.markdown("##### V/f 패턴과 저속 전압 부스트")
    fv = np.linspace(0, 80, 200)
    figv = go.Figure()
    figv.add_trace(go.Scatter(x=fv, y=ch4.vf_voltage(fv, M, 0.0), name="V/f 일정"))
    figv.add_trace(go.Scatter(x=fv, y=ch4.vf_voltage(fv, M, max(boost, 20.0)), name=f"부스트 {max(boost, 20.0):.0f} V"))
    figv.update_xaxes(title_text="고정자 주파수 [Hz]"); figv.update_yaxes(title_text="선간 전압 [V]")
    st.plotly_chart(lstyle(figv, height=260), width="stretch", key="l4_vf")
    st.caption("저주파에서는 고정자 저항 전압 강하 비율이 커 자속이 줄어듦 → 전압을 조금 올려(부스트) 토크를 보완. 위 'V/f 일정 제어' 에서 부스트를 올려 10 Hz 곡선을 비교해 보세요.")
    st.markdown("##### 일정 V/f + 슬립 주파수 조절 폐루프 속도 제어 (fs* = fm + fr*)")
    c = st.columns(4)
    nref = c[0].slider("속도 지령 [rpm]", 200, 1700, 1200, 50, key="l4v_n")
    TLc = c[1].slider("2 s 에 거는 부하 [N·m]", 0.0, 80.0, 40.0, 5.0, key="l4v_TL")
    frm = c[2].slider("슬립 주파수 제한 [Hz]", 0.5, 5.0, 3.0, 0.5, key="l4v_fr")
    cl = _vf_cl(nref, TLc, frm, boost)
    figc = make_subplots(rows=1, cols=3, subplot_titles=("속도 [rpm]", "주파수 fs, 슬립 주파수 fr [Hz]", "토크 [N·m]"))
    figc.add_trace(go.Scatter(x=cl["t"], y=cl["nref"], name="지령", line=dict(dash="dash", color="#999")), 1, 1)
    figc.add_trace(go.Scatter(x=cl["t"], y=cl["n"], name="속도"), 1, 1)
    figc.add_trace(go.Scatter(x=cl["t"], y=cl["fs"], name="fs"), 1, 2)
    figc.add_trace(go.Scatter(x=cl["t"], y=cl["fr"] * 10, name="fr × 10"), 1, 2)
    figc.add_trace(go.Scatter(x=cl["t"], y=cl["T"], name="토크"), 1, 3)
    figc.update_xaxes(title_text="시간 [s]")
    st.plotly_chart(lstyle(figc, height=320), width="stretch", key="l4_vfcl")
    st.caption("속도가 지령보다 낮으면 슬립 주파수를 키워 토크를 늘리고(제한값까지), 높으면 줄임 → 운전점이 토크 곡선을 갈아타며 이동 (교재 그림 4.45).")
    with st.expander("교재 예제: 220 V, 60 Hz, 1750 r/min, 4극 전동기를 V/f 일정으로 50 Hz 운전", expanded=False):
        f50 = st.slider("운전 주파수 [Hz]", 10, 60, 50, 5, key="l4v_ex")
        st.markdown(f"① 공급 전압 V = 220 × {f50}/60 = **{220 * f50 / 60:.2f} V** ② 전부하 슬립 속도 = 1800 − 1750 = 50 r/min (V/f 일정이면 그대로) → "
                    f"동기 속도 {120 * f50 / 4:.0f} r/min − 50 = **{120 * f50 / 4 - 50:.0f} r/min** (교재: 183.33 V, 1450 r/min)")
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
    fig.add_trace(go.Scatter(x=R["n"], y=np.where(R["f"] > 0, R["V"] / np.maximum(R["f"], 1e-6) / (IM["V"] / IM["f"]) * 100, 0), name="공극 자속 ∝ V/f [% 정격]", line=dict(dash="dot")), 1, 2)
    fig.add_trace(go.Scatter(x=R["n"], y=R["I"] / IM["I_rated"] * 100, name="고정자 전류 [% 정격]", line=dict(dash="dash")), 1, 2)
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


@st.fragment
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
    figts = go.Figure()
    figts.add_trace(go.Scatter(x=[1800, 1800], y=[0, float((Tf + Tr).max())], mode="lines", line=dict(width=5), name="동기 전동기: 동기 속도에서만 토크"))
    figts.add_trace(go.Scatter(x=[1800], y=[Tnow], mode="markers", marker=dict(size=12, color="#d62828"), name="현재 토크 (토크각 δ 로 결정)"))
    figts.update_xaxes(range=[0, 2200], title_text="속도 [rpm]"); figts.update_yaxes(title_text="토크 [N·m]")
    st.markdown("##### 동기 전동기의 토크–속도 특성: 속도는 동기 속도로 고정, 부하가 늘면 δ 가 커짐 (최대 토크를 넘으면 탈조)")
    st.plotly_chart(lstyle(figts, height=260), width="stretch", key="l4_syncTN")
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
    tabs = st.tabs(["4.1 아라고 원판·구조·철손", "4.1.2 회전자계", "4.1.3 유기 기전력·슬립", "4.1.3 등가회로·전력 흐름", "4.1.4 특성·운전점", "4.1.6 회전자 구조",
                    "4.1.7 정수 측정", "4.1.8 속도 제어·영역", "4.2 동기 전동기"])
    for tab, fn in zip(tabs, (_structure, _rotating, _emf, _equivalent, _characteristics, _rotor_types, _tests, _speed_control, _synchronous)):
        with tab:
            fn()
