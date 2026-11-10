"""탭 1. 원리 이해"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from concepts.commutation import torque_waveforms, ripple_percent
from ui import realtime
from ui.diagrams import wiring_diagram
from ui.plots import info_metric, style


def _animation(model, params):
    st.markdown("#### 실시간 단면 애니메이션")
    st.caption("계산이 브라우저에서 실시간으로 돌아갑니다. 슬라이더를 움직이면 **지금 상태에서 "
               "바로** 반응하고, 처음부터 보려면 **⟲ 정지 상태에서 다시 기동** 버튼을 누르세요. "
               "재생 속도로 슬로모션 정도를 바꿀 수 있습니다.")
    realtime.render(realtime.principle_html(model, params), height=800)
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


def torque_ripple_section():
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
    st.plotly_chart(fig, width="stretch")
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
    st.info(f"선택한 전동기: **{getattr(model, 'variant', model.name)}** · "
            "여기서 보는 모든 값은 위 파라미터 설정 기준입니다.")
    if model.excitation == "series":
        st.warning("직권 전동기는 부하 토크를 0 근처로 내리면 속도가 매우 높아집니다 "
                   "(무부하 폭주). 슬라이더로 직접 확인해 보세요.")
    _animation(model, params)
    st.divider()
    torque_ripple_section()
    st.divider()
    st.markdown(f"#### {model.name} 전동기 결선도와 특징")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(wiring_diagram(model.excitation, getattr(model, "variant", "")),
                        width="stretch",
                        config={"staticPlot": True})
    with c2:
        st.markdown(model.summary_md)
