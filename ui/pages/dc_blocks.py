"""제어 블록 편집기 페이지: 제어 구조를 블록으로 직접 구성하고 실시간으로 돌려 본다."""
import streamlit as st

from motors import registry
from ui import realtime
from ui.compare import VARIANTS, build
from ui.params_panel import params_from_session


def _motor_cfg(m):
    u = m.default_inputs()
    keys = ["Ra", "La", "Rf", "Lf", "Laf", "Rs", "Ls", "Ms", "J", "B"]
    return {"type": m.excitation, "sigma": float(m.p.get("sigma", 1.0)),
            "p": {k: float(m.p.get(k, 0.0)) for k in keys}, "V": u.V, "Vf": u.Vf, "Rfx": u.Rfx}


def render():
    st.title("🧩 제어 블록 편집기 (DC · BLDC)")
    st.caption("블록을 끌어다 놓고 선으로 이어 제어 구조를 직접 만들고, 바로 실시간으로 돌려 봅니다. "
               "전류 제어기만, 속도 제어기만, P/PI/PID 바꾸기, 리미터·필터 추가처럼 자유롭게 바꿀 수 있습니다. "
               "DC 전동기 블록은 **DC 전동기 시뮬레이터**, BLDC 전동기 블록은 **BLDC 전동기 시뮬레이터** 페이지의 "
               "파라미터 설정 값을 씁니다. BLDC 템플릿은 위쪽 템플릿 목록에서 'BLDC:' 로 시작합니다.")
    labels = [v[0] for v in VARIANTS]
    ss = st.session_state
    last = ss.get("_keep_motor_choice", "타여자")
    default = last if last in labels else "타여자"
    if last == "복권":
        default = "차동 복권" if ss.get("_keep_p_sigma") == "차동 복권" else "가동 복권"
    c = st.columns([2, 3])
    pick = c[0].selectbox("템플릿과 새 전동기 블록의 기본 종류", labels, index=labels.index(default),
                          key="blk_motor")
    c[1].caption("전동기 블록마다 속성에서 종류를 따로 고를 수도 있습니다. 여기를 바꾸면 편집기가 다시 "
                 "로드되지만, 만든 구조는 브라우저에 저장되어 그대로 남습니다.")
    models = {lab: build(lab) for lab in labels}
    motors = {lab: _motor_cfg(m) for lab, m in models.items()}
    m = models[pick]
    p = m.p
    ia = 0.0 if m.excitation in ("separately", "shunt") else p["I_rated"]
    K = float(m.kphi(ia, m.field_ss(ia, m.default_inputs())))
    ctrl = {"Ra": p["Ra"], "La": p["La"], "J": p["J"], "B": p["B"], "V": p["V"], "K": K,
            "Ilim": 2 * p["I_rated"], "TL": p["TL"]}
    bp = params_from_session(registry.get("bldc"))
    bldc = {"p": {k: float(bp[k]) for k in ["Vdc", "R", "L", "ke", "poles", "J", "B"]},
            "TL": float(bp["TL"]), "Ilim": 2 * float(bp["I_rated"])}
    realtime.render(realtime.editor_html(motors, pick, ctrl, bldc), height=1180)
    with st.expander("블록 설명과 구성 팁", expanded=False):
        st.markdown("""
- **신호원**: 상수(실행 중 값 변경 = 계단), 계단(지정 시각), 사각파(반복 계단), 사인파. "rpm 으로 입력"을 켜면 rad/s 로 바꿔 내보냅니다.
- **합산점 Σ**: 부호 문자열로 입력 개수와 부호를 정합니다 (`+-` = 오차, `++` = 피드포워드 더하기).
- **P / PI / PID**: 속성의 '종류'로 언제든 바꿀 수 있습니다. 출력 제한과 안티와인드업은 PI 의 적분기에 작동합니다.
- **초퍼 → 전동기**: 초퍼는 전압을 ±Vdc (1상한은 0 ~ Vdc) 로 자르고, 1상한이면 전동기 전류도 한 방향만 흐릅니다.
- **BLDC 전동기**: 6스텝 인버터가 블록 안에 들어 있어 전압 지령 v* 를 바로 넣습니다. 피드백은 ω 와 토크 전류 iT (= Te/2ke),
  상전류 ia·ib·ic 는 스코프로 정류 모습을 볼 때 씁니다. 속성에서 홀 센서 오차를 바꿔 볼 수 있습니다.
- **전동기 출력**: ω [rad/s], n [rpm], Ia [A], E [V], Te [N·m]. 피드백은 여기서 끌어옵니다. TL 입력을 이으면 그 신호가 부하 토크가 됩니다.
- **적분기**로 ω 를 적분하면 회전각 θ [rad] 가 되어 **위치 제어**도 만들 수 있습니다.
- 적분 요소(전동기·적분기·필터) 없이 고리를 만들면 **대수 루프** 경고가 뜹니다.
- 만든 구조는 이 브라우저에 자동 저장되며, [내보내기/가져오기] 로 JSON 으로 옮길 수 있습니다.
""")
