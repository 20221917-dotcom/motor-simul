"""직류 전동기 시뮬레이터 페이지."""
import streamlit as st

from motors import registry
from ui.params_panel import render_params
from ui.tabs.dc import tab_principle, tab_steady, tab_dynamic, tab_control

ASSUMPTIONS = ("**모델 가정** · 선형 자기회로 (Kφ = Laf·If, Ms·Ia), 자기포화·전기자 반작용·철손·"
               "브러시 전압강하 무시. 정류는 이상적이며 초퍼는 평균값 모델 (스위칭 리플 무시). "
               "원리·정상상태·동특성 탭의 부하 토크는 회전 방향과 무관한 일정 토크입니다. "
               "계산은 SI 단위, 속도는 rpm 으로 표시합니다.")


def render():
    st.title("⚙️ 직류(DC) 전동기 시뮬레이터")
    models = registry.all_models("DC")
    names = [m.name for m in models]
    choice = st.segmented_control("전동기 종류", names, default=names[0], key="motor_choice")
    model_cls = models[names.index(choice or names[0])]
    st.caption("종류를 바꾸면 파라미터와 4개 탭이 모두 그 전동기 기준으로 바뀝니다. "
               "공통 파라미터(V, Ra, J 등)와 종류별로 입력해 둔 값은 그대로 유지됩니다.")

    params, errors = render_params(model_cls)
    if errors:
        st.error("파라미터에 물리적으로 맞지 않는 값이 있습니다. 고친 뒤 다시 시도하세요.\n\n"
                 + "\n".join(f"- {e}" for e in errors))
        st.stop()
    model = model_cls(params)

    tabs = st.tabs(["① 원리 이해", "② 정상상태 특성", "③ 동특성 (시간 응답)", "④ 제어"])
    with tabs[0]:
        tab_principle.render(model, params)
    with tabs[1]:
        tab_steady.render(model, params)
    with tabs[2]:
        tab_dynamic.render(model, params)
    with tabs[3]:
        tab_control.render(model, params)

    st.divider()
    st.caption(ASSUMPTIONS)
