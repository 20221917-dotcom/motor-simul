"""강의 실습 1장: 전동기의 기본 원리."""
import math

import streamlit as st

from ui import realtime
from ui.lecture_draw import blocks
from ui.pages.lecture_common import check, link, ref

RPM = 60 / (2 * math.pi)
# 각 탭 iframe 높이 [px] (브라우저에서 잰 내용 높이 + 여유)
HEIGHTS = {"principle": 600, "magnetic": 1105, "force": 2005, "double": 658, "load": 1354, "quadrant": 547}


def _lab(tab, height):
    realtime.render(realtime.lab_html(1, tab), height=height)


def _principle():
    ref("1.1 전동기의 동작 원리 — 로렌츠의 힘 F = I·l·B, 두 자석의 상호 작용 (자석–자석, 자석–자성체), 직류·교류(동기·유도) 전동기의 자석")
    _lab("principle", HEIGHTS["principle"])
    check("자석–자석: θ = 90° 에서 토크 최대, 0° 에서 0 → 직류 전동기는 정류자로 두 자석을 항상 90° 로 유지",
          "자석–자성체: 토크가 sin2θ 로 작고 180° 마다 반복 (릴럭턴스 토크) → 회전자가 원통형이면 생기지 않음",
          "교류 전동기는 고정자 자석(회전자계)이 돌고 회전자 자석이 같은 속도로 따라 돎: 동기 = 회전자 자석이 직류, 유도 = 회전자 자석이 유도 전류")


def _magnetic():
    ref("1.2.1 자기 에너지 — 기자력과 자속, λ-i 특성(선형·포화 영역), 인덕턴스, 자기 에너지와 코에너지")
    _lab("magnetic", HEIGHTS["magnetic"])
    check("전류를 키우면 처음엔 λ 가 비례하다가(선형 영역) Bs 근처에서 거의 늘지 않음(포화 영역)",
          "공극 x 가 길어지면 자기 저항이 커져 기울기(인덕턴스)가 작아지고 포화가 늦게 옴",
          "포화되면 L 이 작아지고, 에너지 W 와 코에너지 W′ 가 달라짐 (선형이면 같음)")


def _force_reluctance():
    ref("1.2.2 직선 운동 기계 · 1.2.3 회전 기계 — 힘은 인덕턴스가 커지는(자기 저항이 작아지는) 방향, 릴럭턴스 토크와 평균 토크 조건")
    _lab("force", HEIGHTS["force"])
    check("ωm/ωs 를 1 에서 조금만 벗어나도 평균 토크가 0 → 동기 속도로 돌 때만 회전력이 생김 (동기 릴럭턴스 전동기)",
          "δ 를 바꾸면 평균 토크가 sin2δ 로 변하고, 회전자가 원통형(L2 = 0)이면 토크가 없음")


def _double():
    ref("1.2.3 이중 여자 기기·원통형 기기 — T = −is·ir·M·sinθ, 평균 토크 조건 ωm = ωs ± ωr (직류·동기·유도 전동기)")
    _lab("double", HEIGHTS["double"])
    check("평균 토크는 ωm = ωs + ωr 또는 ωm = |ωs − ωr| 일 때만 0 이 아님",
          "직류 전동기: ωs = 0 이면 ωr = ωm (정류자가 맞춰 줌) · 동기: ωr = 0 이면 ωm = ωs · 유도: ωr = ωs − ωm (슬립)",
          "θ0 를 바꾸면 평균 토크 크기가 변함 (브러시 위치·부하각)")


def _load():
    ref("1.3 부하 시스템 — 운동 방정식 J·dω/dt = Te − TL − Bω, 부하 토크 종류, 기어·직선 운동의 등가 관성")
    _lab("load", HEIGHTS["load"])
    check("일정 토크 부하는 속도에 관계없이 같은 토크, 일정 출력 부하는 저속일수록 큰 토크, 팬·펌프는 속도 제곱",
          "감속비 n 을 키우면 부하 관성이 n² 로 작아져 보이고 토크도 1/n 로 작아짐 (대신 속도는 n 배 필요)")


def _quadrant():
    ref("1.3.3 전동기의 동작 모드 — 전동기 모드/발전기(제동) 모드, 4상한 운전 (엘리베이터 예)")
    _lab("quadrant", HEIGHTS["quadrant"])
    check("사람이 탄 카 상승 → 1상한, 빈 카 상승 → 2상한, 빈 카 하강 → 3상한, 사람이 탄 카 하강 → 4상한",
          "균형추가 카보다 무거우면 토크 부호가 바뀜")


@st.fragment
def _system():
    ref("1.4 전동기 구동 시스템의 구성 — 전원, 전력 변환 장치, 전동기, 제어기, 센서")
    st.plotly_chart(blocks([("전원<br>(단상·3상 교류)", "#fff3d6"), ("전력 변환 장치<br>정류기·초퍼·인버터", "#fdf0e6"),
                            ("전동기", "#eef4fb"), ("기계 부하", "#e6f5ec")], feedback=(3, 1, "센서 (전류·속도·위치) → 제어기 → 스위칭 지령")),
                    width="stretch", key="l1_sys")
    st.markdown("""
| 전동기 | 전력 변환 장치 | 이 앱에서 확인 |
|---|---|---|
| 직류 전동기 | 정류기 / 초퍼 (1상한, H-브리지 4상한) | 2장 초퍼 탭, 회로 시뮬레이터 '강압 초퍼'·'H-브리지' 예제 |
| BLDC 전동기 | 3상 인버터 (6스텝, 120° 통전) | 3장, BLDC 전동기 시뮬레이터 |
| 유도·동기 전동기 | (정류기 +) 3상 PWM 인버터 | 4장, 회로 시뮬레이터 '3상 인버터' 예제, 유도전동기·PMSM 시뮬레이터 |
""")
    c = st.columns(3)
    with c[0]: link("회로 시뮬레이터", "circuit")
    with c[1]: link("제어 블록 편집기", "blocks")
    with c[2]: link("DC 전동기 시뮬레이터", "")


def render():
    st.title("📘 1장 전동기의 기본 원리")
    st.caption("강의 자료 1장의 내용을 직접 값을 바꿔 가며 확인합니다. 탭은 교재 절 순서입니다.")
    tabs = st.tabs(["1.1 동작 원리", "1.2 자기회로·λ-i 특성", "1.2 힘·릴럭턴스 토크", "1.2 이중 여자·평균 토크 조건",
                    "1.3 부하 시스템", "1.3.3 4상한 운전", "1.4 구동 시스템 구성"])
    for tab, fn in zip(tabs, (_principle, _magnetic, _force_reluctance, _double, _load, _quadrant, _system)):
        with tab:
            fn()
