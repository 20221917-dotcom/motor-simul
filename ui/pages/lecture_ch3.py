"""강의 실습 3장: BLDC 전동기. 스위칭 시뮬레이션과 그래프는 브라우저(ui/realtime/lab_ch3.js)에서 돌아
슬라이더를 끄는 동안에도 바로 다시 그려집니다. 같은 모델의 파이썬 버전은 lectures/ch3.py (테스트 기준)."""
import streamlit as st

from ui import realtime
from ui.pages.lecture_common import check, link, ref

HEIGHTS = {"shapes": 790, "sixstep": 1423, "commutation": 1179, "pwm": 1872, "sensorless": 705}


def _lab(tab):
    realtime.render(realtime.lab_html(3, tab), height=HEIGHTS[tab])


def _shapes():
    ref("3.1 BLDC 전동기의 구조 · BLDC 와 영구자석 동기 전동기의 비교 — 사다리꼴 역기전력 + 120° 사각파 전류 vs 정현파 + 정현파")
    _lab("shapes")
    check("BLDC: 사다리꼴 120° 평탄부 + 120° 사각파 전류 → 리플 0 (이상적인 경우)",
          "PMSM: 정현파 역기전력 + 정현파 전류 → 리플 0",
          "짝이 안 맞으면(정현파 역기전력에 사각파 전류 등) 토크가 60° 마다 출렁임, 평탄부가 120° 보다 좁아도 리플")


def _six_step():
    ref("3.2 3상 BLDC 전동기의 기본 구동 방법 — 홀 센서 3개로 6구간 검출, 2상 여자(120° 통전), 6-스텝 구동")
    _lab("sixstep")
    check("항상 두 상만 통전되고 한 상은 개방 (2상 여자), 스위치마다 한 주기에 120° 씩 켜짐",
          "홀 신호 3개의 조합이 60° 마다 바뀌어 6구간을 구별")


def _commutation():
    ref("3.3 모델링·상전류 전환 시 토크 리플 — 전환 전류의 증가율과 감소율이 달라 비전환 전류가 출렁임 (운전 주파수 한 주기에 6번)")
    _lab("commutation")
    check("상 전환 때마다(60° 마다) 꺼지는 상 전류는 다이오드로 환류하며 줄고, 켜지는 상 전류는 늘어남 — 두 속도가 다르면 토크가 출렁임",
          "속도가 낮으면(Vdc > 4E) 전환 순간 토크가 솟고, 높으면 움푹 꺼짐",
          "홀 센서 위치가 틀어지면 역기전력 평탄부를 벗어나 리플과 평균 토크가 나빠짐")
    link("BLDC 전동기 시뮬레이터 (실시간 6스텝, 속도·전류 제어)", "bldc")


def _pwm():
    ref("3.4 제어 — 속도 제어(PI), 전류 제어, PWM 기법: 바이폴라, 유니폴라(H_PWM-L_ON, H_ON-L_PWM, PWM_ON, ON_PWM)")
    _lab("pwm")
    check("바이폴라는 꺼진 동안 −Vdc 가 걸려 같은 듀티에서 평균 전압이 (2D−1)·Vdc 로 작고 전류 리플이 큼 (듀티를 0.8 이상으로 올려 보세요)",
          "유니폴라는 한 스위치만 PWM → 스위칭 손실·전류 리플이 작지만, 개방 상의 다이오드 환류로 리플 전류가 생길 수 있음",
          "PWM_ON / ON_PWM 은 120° 통전 구간의 앞·뒤 60° 에만 PWM 을 해 스위치마다 손실을 고르게 나눔")


def _sensorless():
    ref("3.5 센서리스 제어 — 개방 상 단자 전압으로 역기전력 영점(ZCP) 검출 → 30° 뒤 상 전환")
    _lab("sensorless")
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
