"""ParamSpec 목록으로 파라미터 입력 위젯을 자동 생성 (메인 화면 위쪽).

Streamlit 은 화면에 그려지지 않은 위젯의 값을 지우므로, 입력값을 별도 키(_keep_*)에
보관해 둔다. 그래서 전동기 종류를 바꿨다가 돌아와도 값이 유지되고, 비교 기능에서
다른 종류의 파라미터도 읽을 수 있다.
"""
import streamlit as st


def _keep(k):
    return f"_keep_{k}"


def _default_widget_value(s):
    return s.default_label() if s.choices else float(s.default)


def stored_widget_value(s):
    """보관된 화면값 (없으면 기본값)."""
    ss = st.session_state
    return ss.get(s.widget_key, ss.get(_keep(s.widget_key), _default_widget_value(s)))


def params_from_session(model_cls, overrides=None) -> dict:
    """지금 화면에 안 보이는 종류라도, 사용자가 입력해 둔 값으로 SI 파라미터를 만든다."""
    params = {}
    for s in model_cls.param_specs():
        v = stored_widget_value(s)
        params[s.key] = dict(s.choices)[v] if s.choices else s.to_si(float(v))
    params.update(overrides or {})
    return params


def reset_defaults(specs):
    for s in specs:
        st.session_state[s.widget_key] = _default_widget_value(s)
        st.session_state[_keep(s.widget_key)] = _default_widget_value(s)


def render_params(model_cls):
    """메인 화면 위쪽에 파라미터 입력 영역을 그리고 (SI 파라미터 dict, 오류 목록) 을 돌려준다."""
    specs = model_cls.param_specs()
    ss = st.session_state
    groups = []
    for s in specs:
        if s.group not in groups:
            groups.append(s.group)

    with st.expander(f"⚙️ 파라미터 설정 · {model_cls.name}", expanded=True):
        top = st.columns([4, 1])
        top[0].caption("모든 값은 SI 단위로 계산되며 단위는 각 입력칸에 표시되어 있습니다. "
                       "선택한 종류에 해당하지 않는 파라미터는 숨겨집니다.")
        top[1].button("기본값으로 초기화", on_click=reset_defaults, args=(specs,),
                      use_container_width=True)
        params = {}
        # 모든 그룹을 한 줄에 (넓은 화면 기준, 좁은 화면에서는 Streamlit 이 자동으로 세로 배치)
        per_row = len(groups)
        for r0 in range(0, len(groups), per_row):
            cols = st.columns(per_row, gap="small")
            for col, g in zip(cols, groups[r0:r0 + per_row]):
                with col:
                    st.markdown(f"**{g}**")
                    for s in (x for x in specs if x.group == g):
                        k = s.widget_key
                        if k not in ss:
                            ss[k] = ss.get(_keep(k), _default_widget_value(s))
                        if s.choices:
                            labels = [c[0] for c in s.choices]
                            sel = st.radio(s.label, labels, key=k, horizontal=True,
                                           help=s.help or None)
                            ss[_keep(k)] = sel
                            params[s.key] = dict(s.choices)[sel]
                            continue
                        val = st.number_input(f"{s.symbol} · {s.label} [{s.unit}]", key=k,
                                              step=s.step, format="%.4g", help=s.help or None)
                        ss[_keep(k)] = val
                        params[s.key] = s.to_si(val)

        errors = model_cls(params).validate()
        for e in errors:
            st.error(e)
    return params, errors
