"""교류 전동기 페이지 (준비 중). 구현되면 motors/ac/ 모델과 ui/tabs/ac/ 탭으로 교체한다."""
import streamlit as st


def _coming(title, summary, eqs, plan):
    st.title(title)
    st.info("🚧 **준비 중입니다.** 직류 전동기와 같은 구조(원리 · 정상상태 · 동특성 · 제어 탭)로 "
            "추가할 예정입니다. 아래는 다룰 내용 미리보기입니다.")
    st.markdown(summary)
    st.markdown("**핵심 수식 (예정)**")
    for e in eqs:
        st.latex(e)
    st.markdown("**예정 기능**")
    st.markdown("\n".join(f"- {x}" for x in plan))


def induction():
    _coming(
        "🌀 유도전동기 (Induction Motor)",
        "고정자 3상 권선이 만드는 **회전자계**가 회전자 도체에 전류를 유도하고, 그 전류와 자계가 "
        "토크를 만든다. 회전자는 회전자계보다 조금 느리게 돈다 (**슬립**).",
        [r"n_s = \frac{120 f}{P},\qquad s = \frac{n_s - n}{n_s}",
         r"T = \frac{3}{\omega_s}\,\frac{V_{th}^2\,(R_2'/s)}{(R_{th} + R_2'/s)^2 + (X_{th} + X_2')^2}"],
        ["회전자계 애니메이션 (3상 전류 → 회전하는 자계)", "등가회로와 슬립–토크 곡선, 최대 토크·기동 토크",
         "V/f 제어, 벡터 제어(자속 기준 제어) 기초", "기동 방식 비교 (직입, Y-Δ, 인버터)"])


def pmsm():
    _coming(
        "🧲 영구자석 동기전동기 (PMSM)",
        "회전자에 영구자석이 있어 회전자계와 **동기 속도**로 돈다. dq 좌표로 바꾸면 "
        "DC 전동기처럼 토크와 자속을 따로 제어할 수 있다.",
        [r"v_d = R_s i_d + L_d \frac{di_d}{dt} - \omega_e L_q i_q,\quad "
         r"v_q = R_s i_q + L_q \frac{di_q}{dt} + \omega_e (L_d i_d + \lambda_f)",
         r"T_e = \frac{3}{2}\frac{P}{2}\left[\lambda_f i_q + (L_d - L_q) i_d i_q\right]"],
        ["abc ↔ dq 좌표 변환 애니메이션", "dq 전류 제어 + 속도 제어 (DC 제어 탭과 비교)",
         "약계자 제어, MTPA", "SPWM / SVPWM 인버터 평균값 모델"])


def bldc():
    _coming(
        "⚡ BLDC 전동기",
        "구조는 PMSM 과 비슷하지만 역기전력이 **사다리꼴**이고, 홀 센서 위치에 따라 "
        "두 상씩 120° 통전하는 **전자식 정류**를 한다. 기계식 정류자를 전자 스위치로 바꾼 DC 전동기로 볼 수 있다.",
        [r"v_x = R i_x + L \frac{di_x}{dt} + e_x\quad(x = a, b, c)",
         r"T_e = \frac{e_a i_a + e_b i_b + e_c i_c}{\omega_m}"],
        ["홀 센서와 6스텝 통전 순서 애니메이션", "사다리꼴 역기전력과 토크 리플 (정류 리플)",
         "DC 전동기 정류자와 전자식 정류 비교", "PWM 속도 제어"])
