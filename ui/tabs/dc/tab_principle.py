"""탭 1. 원리 이해"""
from dataclasses import replace

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from concepts.animation import build_principle_figure
from concepts.commutation import torque_waveforms, ripple_percent
from core.simulate import simulate
from ui.diagrams import wiring_diagram
from ui.plots import info_metric, style

N_FRAMES, FRAME_MS = 80, 70


def _equations():
    st.markdown("**핵심 수식**")
    st.latex(r"E = K\phi\,\omega \qquad T_e = K\phi\, I_a")
    st.latex(r"V = I_a R_a + L_a \frac{dI_a}{dt} + E")
    st.latex(r"J \frac{d\omega}{dt} = T_e - B\omega - T_L")
    st.caption("Kφ [V·s/rad = N·m/A], ω [rad/s], Ia [A], T [N·m]. "
               "두 식 E = Kφω 와 T = Kφ·Ia 의 Kφ 는 같은 값입니다 (에너지 보존: E·Ia = Te·ω).")


def _animation(model, params):
    ss = st.session_state
    u_nom = model.default_inputs()
    # 회전 표시 속도 기준: 사이드바 부하에서의 운전 속도 (직권은 무부하 속도가 너무 큼)
    op_ref = model.steady_state(u_nom) or model.no_load(u_nom)
    w_scale = op_ref.omega if op_ref and op_ref.omega > 1 else 100.0
    if_nom = float(model.field_ss(params["I_rated"], u_nom))
    force_ref = float(model.kphi(params["I_rated"], if_nom) * params["I_rated"])
    T_rated = model.rated_torque()

    st.markdown("#### 슬로모션 단면 애니메이션")
    st.caption("슬라이더를 바꾸면 **현재 상태에서 출발해** 미분방정식을 다시 풀고, "
               "그 과도 응답을 천천히 재생합니다. 회전 속도는 눈에 보이도록 줄여서 그리며 "
               "실제 값은 그림 위 숫자로 표시합니다.")
    c1, c2, c3, c4 = st.columns(4)
    V = c1.slider("전기자 전압 V [V]", 0.0, float(round(1.2 * params["V"])),
                  float(params["V"]), step=5.0, key="pr_V")
    field_ok = model.field_control_input in ("Vf", "Rfx")
    fpct = c2.slider("계자 세기 [% 기준]", 20, 120, 100, step=5, key="pr_f",
                     disabled=not field_ok,
                     help="기준 계자 전류 대비 비율. 줄이면 계자 약화. "
                          "분권·복권은 계자 조정 저항 Rfx 로 조정합니다. "
                          "직권은 계자 전류 = 전기자 전류라 따로 조정하지 않습니다.")
    TL = c3.slider("부하 토크 TL [N·m]", 0.0, float(round(2.0 * T_rated, 1)),
                   float(min(max(params["TL"], 0.0), round(2.0 * T_rated, 1))),
                   step=1.0, key="pr_TL")
    win = c4.select_slider("관찰 구간 [s]", [0.2, 0.4, 0.6, 1.0, 1.5, 2.0], 0.6,
                           key="pr_win")
    b1, b2, _ = st.columns([1, 1, 3])
    restart = b1.button("⟲ 정지 상태에서 다시 기동", use_container_width=True)
    cont = b2.button("▶ 이어서 보기", use_container_width=True)

    sig = (model.key, tuple(sorted(params.items())))
    if ss.get("pr_sig") != sig or restart:
        ss.pr_sig, ss.pr_x, ss.pr_theta, ss.pr_t = sig, None, 0.0, 0.0
        ss.pr_last, ss.pr_html = None, None
    cur = (V, fpct, TL, win)
    if ss.get("pr_html") is None or cur != ss.get("pr_last") or cont:
        u = model.with_field_ratio(u_nom, fpct / 100.0)
        u = replace(u, V=V, TL=TL)
        x0 = ss.pr_x if ss.pr_x is not None else model.initial_state(u)
        res = simulate(model, u, win, x0=x0, n_points=800, max_step=win / 300)
        fig, theta_end = build_principle_figure(res, ss.pr_theta, w_scale, force_ref, if_nom,
                                                N_FRAMES, FRAME_MS, t_offset=ss.pr_t)
        ss.pr_html = fig.to_html(include_plotlyjs=True, full_html=True, auto_play=True,
                                 config={"displayModeBar": False})
        ss.pr_x, ss.pr_theta, ss.pr_t = res.x[:, -1], theta_end, ss.pr_t + win
        ss.pr_last = cur
        ss.pr_end = {k: float(res[k][-1]) for k in ("rpm", "ia", "E", "v_R", "Te")}
    components.html(ss.pr_html, height=620)
    slow = (FRAME_MS / 1000) / (win / N_FRAMES)
    e = ss.pr_end
    st.caption(f"재생 속도: 실제의 1/{slow:.0f} (프레임당 {win / N_FRAMES * 1000:.1f} ms). "
               f"구간 끝 상태 → 속도 {e['rpm']:.0f} rpm, Ia {e['ia']:.1f} A, "
               f"E {e['E']:.0f} V, Ia·R {e['v_R']:.0f} V")
    with st.expander("그림 읽는 법", expanded=False):
        st.markdown("""
- **⊙ / ⊗** : 도체 전류가 지면에서 나오는 / 들어가는 방향. 테두리 색은 연결된 **정류자편** 색과 같습니다.
- **초록 화살표** : 도체가 받는 힘 F = I·L×B. 길이는 Kφ·Ia 에 비례합니다.
  도체가 자극 정면(좌우)에 있을 때 힘이 회전 방향과 같아 토크가 최대이고,
  위·아래(중성축)에서는 힘이 반지름 방향이라 토크가 0 입니다.
- **정류자와 브러시** : 도체가 중성축을 지날 때 정류자편이 반대쪽 브러시로 넘어가면서
  코일 전류 방향이 뒤집힙니다. 그래서 N극 아래 도체는 항상 같은 방향 전류를 가져
  토크 방향이 한쪽으로 유지됩니다.
- **전압 분배 막대** : 기동 직후에는 E ≈ 0 이라 거의 모든 전압이 **Ia·R** 에 걸려
  큰 돌입 전류가 흐릅니다. 속도가 오르면 **E** 가 커지고 전류가 줄어듭니다.
- **보라색 자속선** : 계자 세기. 계자를 약하게 하면 같은 속도에서 E 가 작아져
  더 빨리 돌아야 V 와 균형을 이룹니다 (계자 약화 → 속도 상승).
""")


def _torque_ripple():
    st.markdown("#### 정류자와 코일 수에 따른 토크 파형")
    n = st.slider("코일 수 N (π/N 간격 배치)", 2, 16, 4, key="pr_ncoil")
    th = np.linspace(0, 4 * np.pi, 1000)
    w = torque_waveforms(th, n)
    deg = np.rad2deg(th)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=deg, y=w["no_comm"], name="정류자 없음 (cos θ)",
                             line=dict(color="#adb5bd", dash="dash")))
    fig.add_trace(go.Scatter(x=deg, y=w["single"], name="코일 1개 + 정류자 (|cos θ|)",
                             line=dict(color="#e76f51")))
    fig.add_trace(go.Scatter(x=deg, y=w["multi"], name=f"코일 {n}개 + 정류자",
                             line=dict(color="#264653", width=3)))
    style(fig, 340, xaxis_title="회전각 θ [°]", yaxis_title="토크 (코일 1개 최대 = 1) [p.u.]")
    fig.update_xaxes(dtick=90)
    st.plotly_chart(fig, use_container_width=True)
    c = st.columns(3)
    info_metric(c[0], "정류자 없음: 평균 토크", f"{np.mean(w['no_comm']):.3f} p.u.",
                help="한 바퀴 평균 0 → 진동만 하고 회전을 계속하지 못함")
    info_metric(c[1], "코일 1개: 평균 / 리플", f"{np.mean(w['single']):.3f} p.u.",
                f"리플 {ripple_percent(w['single']):.0f} %")
    info_metric(c[2], f"코일 {n}개: 평균 / 리플", f"{np.mean(w['multi']):.3f} p.u.",
                f"리플 {ripple_percent(w['multi']):.1f} %")
    st.caption("코일을 늘리면 평균 토크(2/π ≈ 0.637)는 그대로이고 리플만 줄어듭니다. "
               "실제 전동기는 코일·정류자편이 수십 개라 토크가 거의 일정합니다.")


def render(model, params):
    left, right = st.columns([3, 1])
    with right:
        _equations()
    with left:
        st.info(f"선택한 전동기: **{getattr(model, 'variant', model.name)}** · "
                "여기서 보는 모든 값은 사이드바 파라미터 기준입니다.")
        if model.excitation == "series":
            st.warning("직권 전동기는 부하 토크를 0 근처로 내리면 속도가 매우 높아집니다 "
                       "(무부하 폭주). 슬라이더로 직접 확인해 보세요.")
    _animation(model, params)
    st.divider()
    _torque_ripple()
    st.divider()
    st.markdown(f"#### {model.name} 전동기 결선도와 특징")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(wiring_diagram(model.excitation, getattr(model, "variant", "")),
                        use_container_width=True,
                        config={"staticPlot": True})
    with c2:
        st.markdown(model.summary_md)
