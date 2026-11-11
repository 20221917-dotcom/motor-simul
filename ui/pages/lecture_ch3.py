"""강의 실습 3장: BLDC 전동기."""
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lectures import ch3
from ui.lecture_draw import bldc_inverter
from ui.pages.lecture_common import check, link, lstyle, ref, thin
from ui.plots import info_metric

COL = {"a": "#d62828", "b": "#2a9d8f", "c": "#1d4ed8"}


@st.cache_data(max_entries=64, show_spinner=False)
def _sim(rpm, duty, method, flat, hall_off, fsw, cycles=3, show=1):
    return ch3.simulate_bldc(rpm, duty, method, P=dict(fsw=fsw), flat_deg=flat, hall_offset_deg=hall_off, cycles=cycles, show_cycles=show)


@st.cache_data(max_entries=16, show_spinner=False)
def _drive(rpm, ctrl, method, TL):
    return ch3.simulate_bldc_drive(rpm, ctrl, method, TL=TL)


@st.fragment
def _shapes():
    ref("3.1 BLDC 전동기의 구조 · BLDC 와 영구자석 동기 전동기의 비교 — 사다리꼴 역기전력 + 120° 사각파 전류 vs 정현파 + 정현파")
    c = st.columns(3)
    ek = c[0].radio("역기전력 모양", ["사다리꼴", "정현파"], key="l3s_e")
    flat = c[1].slider("사다리꼴 평탄부 폭 [°]", 0, 180, 120, 10, key="l3s_flat", disabled=ek != "사다리꼴")
    ik = c[2].radio("상전류 모양", ["120° 사각파", "정현파"], key="l3s_i")
    th, e, i, T = ch3.torque_from_shapes(ek, ik, flat)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("상 역기전력 e (단위값)", "상전류 i (단위값)", "토크 ∝ Σ e·i"))
    x = np.degrees(th)
    for k, p in enumerate("abc"):
        fig.add_trace(go.Scatter(x=x, y=e[k], name=f"e{p}", line=dict(color=COL[p])), 1, 1)
        fig.add_trace(go.Scatter(x=x, y=i[k], name=f"i{p}", line=dict(color=COL[p], shape="hv" if ik != "정현파" else None)), 2, 1)
    for k, p in enumerate("abc"):
        fig.add_trace(go.Scatter(x=x, y=e[k] * i[k], name=f"T{p} = e{p}·i{p}", line=dict(color=COL[p], dash="dot")), 3, 1)
    fig.add_trace(go.Scatter(x=x, y=T, name="3상 토크 (합)", line=dict(color="#111", width=3)), 3, 1)
    fig.update_xaxes(title_text="전기각 θe [°]", row=3, col=1, dtick=60)
    st.plotly_chart(lstyle(fig, height=520, side_legend=True), width="stretch", key="l3_shape")
    info_metric(st.columns(3)[0], "토크 리플 (최대−최소)/평균", f"{ch3.ripple_percent(T):.1f} %")
    check("BLDC: 사다리꼴 120° 평탄부 + 120° 사각파 전류 → 리플 0 (이상적인 경우)",
          "PMSM: 정현파 역기전력 + 정현파 전류 → 리플 0",
          "짝이 안 맞으면(정현파 역기전력에 사각파 전류 등) 토크가 60° 마다 출렁임, 평탄부가 120° 보다 좁아도 리플")


@st.fragment
def _six_step():
    ref("3.2 3상 BLDC 전동기의 기본 구동 방법 — 홀 센서 3개로 6구간 검출, 2상 여자(120° 통전), 6-스텝 구동")
    c = st.columns([1, 2])
    deg = c[0].slider("회전자 위치 θe [°] (전기각)", 0, 359, 45, 1, key="l3h_deg")
    th = math.radians(deg)
    k = ch3.sector(th)
    hi, lo, fl = ch3.step_info(k)
    H = [int(h) for h in ch3.hall(th)]
    roles = {p: ("+" if p == hi else "−" if p == lo else "개방") for p in "abc"}
    sw = {hi + "+": True, lo + "-": True}
    with c[0]:
        st.markdown(f"#### 구간 {k + 1}  ({30 + 60 * k}° ~ {90 + 60 * k}°)")
        info_metric(st, "홀 센서 (H1 H2 H3)", f"{H[0]} {H[1]} {H[2]}")
        info_metric(st, "켜는 스위치", f"{hi.upper()}+ , {lo.upper()}−")
        st.markdown(f"전류 경로: **Vdc(+) → {hi.upper()}+ → {hi}상 → 중성점 → {lo}상 → {lo.upper()}− → Vdc(−)**, "
                    f"**{fl}상은 개방** (역기전력만 나타남)")
    c[1].plotly_chart(bldc_inverter(sw, roles, title=f"θe = {deg}° : {hi}+ / {lo}− 통전, {fl} 개방"), width="stretch", key="l3_inv")
    # 고정자 자계 (통전 두 상의 기자력 합) 와 회전자 N 극 방향
    ax = {"a": 0.0, "b": 120.0, "c": 240.0}
    v = np.exp(1j * np.radians(ax[hi])) - np.exp(1j * np.radians(ax[lo]))
    rot = (deg + 180) % 360
    pol = go.Figure()
    pol.add_trace(go.Scatterpolar(r=[0, 1], theta=[0, math.degrees(np.angle(v))], mode="lines+markers", line=dict(color="#7c3aed", width=6),
                                  name="고정자 자계 (통전 상의 기자력)"))
    pol.add_trace(go.Scatterpolar(r=[0, 0.8], theta=[0, rot], mode="lines+markers", line=dict(color="#d62828", width=6), name="회전자 N 극"))
    for p_, a_ in ax.items():
        pol.add_trace(go.Scatterpolar(r=[0, 1.1], theta=[0, a_], mode="lines", line=dict(color=COL[p_], width=1, dash="dot"), name=f"{p_}상 축", showlegend=False))
    pol.update_layout(height=320, margin=dict(l=30, r=30, t=30, b=30), polar=dict(radialaxis=dict(visible=False)), legend=dict(orientation="h", y=-0.15))
    c = st.columns([2, 3])
    c[0].plotly_chart(pol, width="stretch", key="l3_pol")
    lead = (math.degrees(np.angle(v)) - rot + 540) % 360 - 180
    c[0].caption(f"고정자 자계가 회전자보다 {lead:.0f}° 앞섬 (60°~120° 사이에서 회전 방향 토크, 90° 에서 최대). "
                 "θe 슬라이더를 움직이면 자계가 60° 마다 한 칸씩 뜀.")
    with c[1]:
        st.markdown("**홀 센서 전압** V_H = (R_H/d)·I_H·B → 비교기로 0/1 신호")
        xh = np.linspace(0, 360, 721)
        figh = go.Figure()
        figh.add_trace(go.Scatter(x=xh, y=np.sin(np.radians(xh)), name="H1 홀 전압 (∝ 자속 밀도 B)", line=dict(color=COL["a"])))
        figh.add_trace(go.Scatter(x=xh, y=(np.sin(np.radians(xh)) > 0).astype(float) * 1.2, name="H1 디지털 출력", line=dict(color="#111", shape="hv")))
        figh.add_vline(x=deg, line=dict(color="#16a34a", width=2))
        figh.update_xaxes(title_text="θe [°]", dtick=60)
        st.plotly_chart(lstyle(figh, height=260), width="stretch", key="l3_hallv")
    x = np.linspace(0, 360, 721)
    xr = np.radians(x)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("홀 센서 신호", "역기전력 (사다리꼴)", "이상적인 상전류 (120° 통전)"))
    Hs = ch3.hall(xr)
    for j, p in enumerate("abc"):
        fig.add_trace(go.Scatter(x=x, y=Hs[j] * 0.8 + (2 - j) * 1.1, name=f"H{j + 1}", line=dict(color=COL[p], shape="hv")), 1, 1)
        fig.add_trace(go.Scatter(x=x, y=ch3.trap(xr - ch3.SHIFT[j]), name=f"e{p}", line=dict(color=COL[p])), 2, 1)
        fig.add_trace(go.Scatter(x=x, y=ch3.current_shape(xr - ch3.SHIFT[j]), name=f"i{p}", line=dict(color=COL[p], shape="hv")), 3, 1)
    for b in range(30, 360, 60):
        fig.add_vline(x=b, line=dict(color="#ddd", width=1))
    fig.add_vline(x=deg, line=dict(color="#16a34a", width=3))
    fig.update_xaxes(title_text="θe [°]", dtick=60, row=3, col=1)
    st.plotly_chart(lstyle(fig, height=480, side_legend=True), width="stretch", key="l3_hall")
    st.table({"구간": [f"{i + 1}: {30 + 60 * i}°~{90 + 60 * i}°" for i in range(6)],
              "홀 (H1H2H3)": ["".join(str(int(h)) for h in ch3.hall(math.radians(60 + 60 * i))) for i in range(6)],
              "켜는 스위치": [f"{a.upper()}+, {b.upper()}−" for a, b in ch3.STEP_TABLE],
              "개방 상": [ch3.step_info(i)[2] for i in range(6)]})
    check("항상 두 상만 통전되고 한 상은 개방 (2상 여자), 스위치마다 한 주기에 120° 씩 켜짐",
          "홀 신호 3개의 조합이 60° 마다 바뀌어 6구간을 구별")


@st.fragment
def _commutation():
    ref("3.3 모델링·상전류 전환 시 토크 리플 — 전환 전류의 증가율과 감소율이 달라 비전환 전류가 출렁임 (운전 주파수 한 주기에 6번)")
    c = st.columns(4)
    rpm = c[0].slider("속도 [rpm] (고정)", 200, 4000, 1500, 100, key="l3c_rpm")
    duty = c[1].slider("PWM 듀티", 0.05, 1.0, 0.6, 0.05, key="l3c_d")
    hoff = c[2].slider("홀 센서 위치 오차 [°]", -30, 30, 0, 5, key="l3c_h")
    flat = c[3].slider("역기전력 평탄부 [°]", 60, 180, 120, 10, key="l3c_f")
    r = _sim(rpm, duty, "hpwm", flat, hoff, 10e3)
    t = r["t"] * 1000
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("상전류 [A]", "역기전력 [V]", "토크 [N·m]"))
    for k, p in enumerate("abc"):
        fig.add_trace(go.Scatter(x=t, y=r["i"][k], name=f"i{p}", line=dict(color=COL[p])), 1, 1)
        fig.add_trace(go.Scatter(x=t, y=r["e"][k], name=f"e{p}", line=dict(color=COL[p], dash="dot"), showlegend=False), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=r["Te"], name="Te", line=dict(color="#111")), 3, 1)
    fig.update_xaxes(title_text="시간 [ms] (전기각 1주기)", row=3, col=1)
    st.plotly_chart(lstyle(fig, height=520, side_legend=True), width="stretch", key="l3_comm")
    sec = r["sector"]; kk = np.where(np.diff(sec) != 0)[0]
    if len(kk):
        k0 = kk[len(kk) // 2]; win = int(len(t) / 6 * 0.6)
        zs = slice(max(k0 - win // 3, 0), min(k0 + win, len(t)))
        figz = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("상 전환 구간 확대: 상전류", "토크 (전환 구간에서 솟거나 꺼짐)"))
        for k, p in enumerate("abc"):
            figz.add_trace(go.Scatter(x=t[zs], y=r["i"][k][zs], name=f"i{p}", line=dict(color=COL[p])), 1, 1)
        figz.add_trace(go.Scatter(x=t[zs], y=r["Te"][zs], name="Te", line=dict(color="#111")), 2, 1)
        figz.add_vline(x=t[k0 + 1], line=dict(color="#16a34a", dash="dot"))
        figz.update_xaxes(title_text="시간 [ms]", row=2, col=1)
        st.plotly_chart(lstyle(figz, height=380), width="stretch", key="l3_commz")
    E = r["P"]["ke"] * r["wm"]
    c = st.columns(4)
    info_metric(c[0], "평균 토크", f"{np.mean(r['Te']):.3f} N·m")
    info_metric(c[1], "토크 리플", f"{ch3.ripple_percent(r['Te']):.0f} %")
    info_metric(c[2], "상 역기전력 E", f"{E:.1f} V")
    info_metric(c[3], "Vdc / 4E", f"{r['P']['Vdc'] / (4 * E):.2f}", "1 보다 크면 전환 시 토크가 솟고, 작으면 꺼짐")
    st.caption(f"전동기: Vdc = {r['P']['Vdc']:.0f} V, R = {r['P']['R']} Ω, L = {r['P']['L'] * 1e3:.1f} mH, "
               f"ke = {r['P']['ke']} V·s/rad, {r['P']['poles']}극, PWM {r['P']['fsw'] / 1000:.0f} kHz (H_PWM-L_ON).")
    check("상 전환 때마다(60° 마다) 꺼지는 상 전류는 다이오드로 환류하며 줄고, 켜지는 상 전류는 늘어남 — 두 속도가 다르면 토크가 출렁임",
          "속도가 낮으면(Vdc > 4E) 전환 순간 토크가 솟고, 높으면 움푹 꺼짐",
          "홀 센서 위치가 틀어지면 역기전력 평탄부를 벗어나 리플과 평균 토크가 나빠짐")
    link("BLDC 전동기 시뮬레이터 (실시간 6스텝, 속도·전류 제어)", "bldc")


@st.fragment
def _pwm():
    ref("3.4 제어 — 속도 제어(PI), 전류 제어, PWM 기법: 바이폴라, 유니폴라(H_PWM-L_ON, H_ON-L_PWM, PWM_ON, ON_PWM)")
    c = st.columns(4)
    mlabel = c[0].selectbox("PWM 기법", list(ch3.PWM_METHODS), index=1, key="l3p_m")
    rpm = c[1].slider("속도 [rpm] (고정)", 300, 3000, 1500, 100, key="l3p_rpm")
    duty = c[2].slider("PWM 듀티", 0.1, 1.0, 0.6, 0.05, key="l3p_d")
    fsw = c[3].selectbox("PWM 주파수", [5000, 10000, 20000], index=1, format_func=lambda x: f"{x // 1000} kHz", key="l3p_f")
    method = ch3.PWM_METHODS[mlabel]
    r = _sim(rpm, duty, method, 120.0, 0, fsw)
    t = r["t"] * 1000
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("상전류 [A]", "a상 단자 전압 va [V] (점선: 중성점 전압 vn)", "토크 [N·m]"))
    for k, p in enumerate("abc"):
        fig.add_trace(go.Scatter(x=t, y=r["i"][k], name=f"i{p}", line=dict(color=COL[p])), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=r["v"][0], name="va", line=dict(color=COL["a"], width=1)), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=r["vn"], name="vn", line=dict(color="#666", dash="dot", width=1)), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=r["Te"], name="Te", line=dict(color="#111")), 3, 1)
    fig.update_xaxes(title_text="시간 [ms]", row=3, col=1)
    st.plotly_chart(lstyle(fig, height=540, side_legend=True), width="stretch", key="l3_pwm")
    figg = go.Figure()
    for k, p in enumerate("abc"):
        figg.add_trace(go.Scatter(x=t, y=r["up"][k] * 0.8 + (5 - 2 * k) * 1.0, name=f"{p.upper()}+", line=dict(color=COL[p], shape="hv", width=1)))
        figg.add_trace(go.Scatter(x=t, y=r["dn"][k] * 0.8 + (4 - 2 * k) * 1.0, name=f"{p.upper()}−", line=dict(color=COL[p], shape="hv", width=1, dash="dot")))
    figg.update_yaxes(tickvals=[5.4, 4.4, 3.4, 2.4, 1.4, 0.4], ticktext=["A+", "A−", "B+", "B−", "C+", "C−"])
    figg.update_xaxes(title_text="시간 [ms] — 6개 스위치의 게이트 신호 (교재 그림: 상단·하단·선단·후단 PWM)")
    st.plotly_chart(lstyle(figg, height=320, showlegend=False), width="stretch", key="l3_gates")
    rows = []
    for lab, m in ch3.PWM_METHODS.items():
        rr = _sim(rpm, duty, m, 120.0, 0, fsw)
        rows.append((lab, float(np.mean(rr["Te"])), ch3.ripple_percent(rr["Te"])))
    st.table({"PWM 기법": [x[0] for x in rows], "평균 토크 [N·m]": [f"{x[1]:.3f}" for x in rows], "토크 리플 [%]": [f"{x[2]:.0f}" for x in rows]})
    check("바이폴라는 꺼진 동안 −Vdc 가 걸려 같은 듀티에서 평균 전압이 (2D−1)·Vdc 로 작고 전류 리플이 큼 (듀티를 0.8 이상으로 올려 보세요)",
          "유니폴라는 한 스위치만 PWM → 스위칭 손실·전류 리플이 작지만, 개방 상의 다이오드 환류로 리플 전류가 생길 수 있음",
          "PWM_ON / ON_PWM 은 120° 통전 구간의 앞·뒤 60° 에만 PWM 을 해 스위치마다 손실을 고르게 나눔")
    st.markdown("##### 3.4.1 속도 제어로 정지 상태에서 기동 (교재 Simulink 결과: 속도·토크·역기전력·상전류)")
    c = st.columns(3)
    ctrl = c[0].radio("제어 구조", ["전류 제어", "전압(듀티) 제어"], key="l3d_c",
                      help="전압(듀티) 제어: 속도 PI 출력이 바로 PWM 듀티 → 간단하지만 지령이 크게 바뀌면 과전류. 전류 제어: 속도 PI → 직류 전류 지령 → 전류 PI → 듀티")
    rpmr = c[1].slider("속도 지령 [rpm]", 500, 3500, 2000, 100, key="l3d_rpm")
    TLd = c[2].slider("0.08 s 에 거는 부하 [N·m]", 0.0, 0.3, 0.1, 0.01, key="l3d_tl")
    d = thin(_drive(rpmr, ctrl, "hpwm", TLd), 4000)
    figd = make_subplots(rows=2, cols=2, shared_xaxes=True, subplot_titles=("속도 [rpm]", "토크 [N·m]", "a상 역기전력 [V]", "상전류 [A]"))
    figd.add_trace(go.Scatter(x=d["t"], y=d["rpm"], name="속도"), 1, 1)
    figd.add_hline(y=rpmr, line=dict(dash="dot", color="#999"), row=1, col=1)
    figd.add_trace(go.Scatter(x=d["t"], y=d["Te"], name="토크", line=dict(width=1)), 1, 2)
    figd.add_trace(go.Scatter(x=d["t"], y=d["ea"], name="ea", line=dict(width=1)), 2, 1)
    for k, p in enumerate("abc"):
        figd.add_trace(go.Scatter(x=d["t"], y=d["i"][k], name=f"i{p}", line=dict(color=COL[p], width=1)), 2, 2)
    figd.update_xaxes(title_text="시간 [s]", row=2, col=1); figd.update_xaxes(title_text="시간 [s]", row=2, col=2)
    st.plotly_chart(lstyle(figd, height=480), width="stretch", key="l3_drive")
    info_metric(st.columns(3)[0], "최대 상전류", f"{np.max(np.abs(d['i'])):.1f} A", "전류 제어는 10 A 로 제한" if ctrl == "전류 제어" else "전류 제한 없음")


@st.fragment
def _sensorless():
    ref("3.5 센서리스 제어 — 개방 상 단자 전압으로 역기전력 영점(ZCP) 검출 → 30° 뒤 상 전환")
    c = st.columns(3)
    rpm = c[0].slider("속도 [rpm] (고정)", 300, 4000, 1500, 100, key="l3z_rpm")
    duty = c[1].slider("PWM 듀티", 0.1, 1.0, 0.6, 0.05, key="l3z_d")
    fsw = c[2].selectbox("PWM 주파수", [5000, 10000, 20000], index=1, format_func=lambda x: f"{x // 1000} kHz", key="l3z_f")
    zl = st.selectbox("PWM 기법 (교재 그림: 상단·하단·선단·후단 구동의 단자 전압)", list(ch3.PWM_METHODS)[1:], key="l3z_m")
    r = _sim(rpm, duty, ch3.PWM_METHODS[zl], 120.0, 0, fsw)
    det, true = ch3.zero_crossings(r, 0)
    t = r["t"] * 1000
    Vh = r["P"]["Vdc"] / 2
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("a상 단자 전압 va 와 Vdc/2 (가상 중성점)", "a상 역기전력 ea 와 개방 구간"))
    fig.add_trace(go.Scatter(x=t, y=r["v"][0], name="va (측정)", line=dict(color=COL["a"], width=1)), 1, 1)
    fig.add_trace(go.Scatter(x=t, y=r["e"][0] + Vh, name="ea + Vdc/2", line=dict(color="#111", dash="dot")), 1, 1)
    fig.add_hline(y=Vh, line=dict(color="#16a34a", dash="dash"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=r["e"][0], name="ea", line=dict(color=COL["a"])), 2, 1)
    fig.add_trace(go.Scatter(x=t, y=np.where(r["floating"][0], 0, np.nan), name="개방 구간 (전류 0)", line=dict(color="#16a34a", width=8)), 2, 1)
    we = r["wm"] * r["P"]["poles"] / 2
    for k, td in enumerate(det):
        fig.add_vline(x=td * 1000, line=dict(color="#16a34a", width=2))
        fig.add_vline(x=(td + math.radians(30) / we) * 1000, line=dict(color="#e76f51", dash="dash"))
    for tt in true:
        fig.add_trace(go.Scatter(x=[tt * 1000], y=[0], mode="markers", marker=dict(size=11, symbol="x", color="#111"),
                                 name="실제 영점", showlegend=False), 2, 1)
    fig.update_xaxes(title_text="시간 [ms] (전기각 1주기)", row=2, col=1)
    st.plotly_chart(lstyle(fig, height=480, side_legend=True), width="stretch", key="l3_zcp")
    c = st.columns(3)
    info_metric(c[0], "검출한 영점 수", f"{len(det)}")
    if det and true:
        err = min(abs(d - tr) for d in det for tr in true) * we
        info_metric(c[1], "검출 오차 (전기각)", f"{math.degrees(err):.1f}°")
    info_metric(c[2], "영점 → 상 전환 지연", "30° (주황 점선)")
    check("개방 상의 단자 전압 = 역기전력 + 중성점 전압 → PWM 이 켜진 순간 Vdc/2 와 비교하면 역기전력 영점을 알 수 있음 (초록 선)",
          "측정 전압에 PWM 파형이 겹쳐 있어, 켜진 순간에만 비교하거나 필터를 써야 함",
          "속도가 낮으면 역기전력이 작아 검출이 어려움 → 센서리스는 저속 기동에 별도 방법이 필요")


def render():
    st.title("📙 3장 BLDC 전동기")
    st.caption("강의 자료 3장의 6스텝 구동, 상전환 토크 리플, PWM 기법, 센서리스 검출을 스위칭 단위 시뮬레이션으로 확인합니다.")
    tabs = st.tabs(["3.1 역기전력·전류 모양 (BLDC vs PMSM)", "3.2 홀 센서·6스텝", "3.3 상전환 토크 리플", "3.4 PWM 기법", "3.5 센서리스 (ZCP)"])
    for tab, fn in zip(tabs, (_shapes, _six_step, _commutation, _pwm, _sensorless)):
        with tab:
            fn()
