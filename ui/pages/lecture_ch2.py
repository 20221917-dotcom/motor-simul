"""강의 실습 2장: 직류 전동기의 토크 제어. 계산·그래프는 브라우저(ui/realtime/lab_ch2.js)에서 돌아
슬라이더를 끄는 동안에도 바로 다시 그려집니다. 같은 식의 파이썬 버전은 lectures/ch2.py (테스트 기준)."""
import streamlit as st

from ui import realtime
from ui.pages.lecture_common import check, link, ref

# 각 탭 iframe 높이 [px]
HEIGHTS = {"types": 563, "steady": 1260, "transient": 1311, "basics": 2542, "current": 1106, "speed": 1591, "chopper": 2068}


def _lab(tab):
    realtime.render(realtime.lab_html(2, tab), height=HEIGHTS[tab])


def _types():
    ref("2.1 직류 전동기의 구조·종류·동작 원리 (정류자와 브러시)")
    _lab("types")
    c = st.columns(3)
    with c[0]: link("DC 전동기 시뮬레이터 (원리·정상상태·동특성·제어)", "")
    with c[1]: link("DC 전동기 구조 (3D·전기자 권선·정류자)", "structure-dc")
    with c[2]: link("회로 시뮬레이터 (DC 전동기 기동)", "circuit")


def _steady():
    ref("2.3 정상상태 특성 — 전기자 전압 제어, 계자 자속 제어(약계자), 일정 토크·일정 출력 영역과 능력 곡선")
    _lab("steady")
    check("전기자 전압 제어는 정격 속도 이하, 계자 자속 제어는 정격 이상 (보통 3배까지)",
          "기저 속도 이하: 전류 일정 → 토크 일정, 이상: 전압·전류 일정 → 출력 일정 (토크는 1/ω)")


def _transient():
    ref("2.4 과도상태 특성 — 전달함수 ω/V, 극점과 감쇠비 ζ, 전기 기계 시정수 Tm·전기자 시정수 Ta, La = 0 근사 / 2.9.1 Simulink 결과 (0.05 s 에 70 V, 140 V)")
    _lab("transient")
    st.latex(r"\frac{\omega(s)}{V(s)}=\frac{K}{L_aJs^2+(R_aJ+L_aB)s+(R_aB+K^2)},\qquad \zeta=\frac{R_aJ+L_aB}{2\sqrt{L_aJ\,(R_aB+K^2)}}")
    check("J 를 줄이거나 Ra 를 줄이면 극점에 허수부가 생겨 진동 (서보·대형 전동기), Ra 를 키우면 진동 없음 (소형 전동기)",
          "La = 0 근사(점선)는 1차 저역 통과 특성: 진동 없이 Tm 으로 올라감",
          "속도는 전압에 비례: 70 V 는 140 V 의 절반 속도",
          "예제 2 를 고르면 극점 −75.29 ± j281.63, ζ = 0.258 (교재 값)")


def _control_basics():
    ref("2.5 제어 시스템 — 개루프·폐루프, P·I·PI 제어기, 정상상태 오차, 안정성(위상 여유)·대역폭")
    _lab("basics")
    check("P 만 쓰면 오차가 남고 Kp 를 키우면 줄어듦 (Type 0), I·PI 는 적분기가 있어 계단 지령 오차 0 (Type 1)",
          "Kp 를 키우면 교차 주파수(대역폭)가 커져 응답이 빨라짐")


def _current():
    ref("2.6 전류 제어기 — 극점-영점 상쇄 PI (Kp = La·ωcc, Ki = Ra·ωcc), 역기전력 전향 보상, 적분기 누적 방지(Anti wind-up)")
    _lab("current")
    check("극점-영점 상쇄로 전류 응답이 1차(오버슈트 없음)가 되고 대역폭이 2배면 2배 빠름",
          "전향 보상을 끄면 역기전력(외란) 때문에 전류가 지령에 늦게 붙음 (회전 속도를 올려 보세요)",
          "전압 한계를 켜고(예: 80 V) 누적 방지를 끄면 지령이 0 으로 돌아갈 때 전류가 한동안 내려오지 않음 (wind-up)")


def _speed():
    ref("2.7 속도 제어기 — PI 속도 제어 (전류 제어 대역폭의 1/5 이하), 50 Hz / 100 Hz 비교, IP 제어기와 혼합 제어기(α)")
    _lab("speed")
    check("PI 는 영점 때문에 오버슈트가 생기고, IP 는 오버슈트가 없지만 지령 응답이 느림",
          "외란(부하) 응답은 PI 와 IP 가 같음 → α 로 지령 응답과 외란 응답을 절충",
          "대역폭 50 → 100 Hz 로 키우면 빨라지고 부하 투입 시 속도 저하도 줄어듦")


def _chopper():
    ref("2.8 전력 변환 장치 — 1상한 초퍼, 4상한 초퍼(H-브리지) 바이폴라·유니폴라 PWM / 2.9.4 초퍼 구동 시스템 (5 kHz, 유니폴라)")
    _lab("chopper")
    link("회로 시뮬레이터에서 H-브리지를 직접 연결해 보기 (예제 'H-브리지 4상한 초퍼')", "circuit")
    check("바이폴라는 va 가 +Vdc ↔ −Vdc 로, 유니폴라는 +Vdc ↔ 0 (또는 0 ↔ −Vdc) 로 바뀜 → 유니폴라 전류 리플이 훨씬 작음",
          "유니폴라는 출력 전압 펄스가 스위칭 주파수의 2배로 나와 리플이 줄어듦",
          "1상한 초퍼는 전압·전류가 한 방향뿐 → 역회전·회생 제동 불가, H-브리지는 4상한 운전 가능")


def render():
    st.title("📗 2장 직류 전동기의 토크 제어")
    st.caption("강의 자료 2장의 정상상태·과도 특성, 전류·속도 제어기, 초퍼 PWM 을 직접 바꿔 가며 확인합니다.")
    tabs = st.tabs(["2.1 종류·원리", "2.3 정상상태 특성", "2.4 과도 특성", "2.5 제어 기초 (P·I·PI)",
                    "2.6 전류 제어기", "2.7 속도 제어기 (PI·IP)", "2.8 초퍼 (PWM)"])
    for tab, fn in zip(tabs, (_types, _steady, _transient, _control_basics, _current, _speed, _chopper)):
        with tab:
            fn()
