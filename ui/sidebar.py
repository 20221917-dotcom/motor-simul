"""ParamSpec 목록으로 사이드바 입력 위젯을 자동 생성.

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
    """사이드바에 지금 안 보이는 종류라도, 사용자가 입력해 둔 값으로 SI 파라미터를 만든다."""
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


def render_sidebar(model_cls):
    """사이드바를 그리고 (SI 파라미터 dict, 오류 목록) 을 돌려준다."""
    specs = model_cls.param_specs()
    sb = st.sidebar
    ss = st.session_state
    sb.header(f"⚙️ 파라미터 · {model_cls.name}")
    sb.button("기본값으로 초기화", on_click=reset_defaults, args=(specs,),
              use_container_width=True)

    params = {}
    groups = []
    for s in specs:
        if s.group not in groups:
            groups.append(s.group)
    for g in groups:
        with sb.expander(g, expanded=True):
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

    model = model_cls(params)
    errors = model.validate()
    for e in errors:
        sb.error(e)
    return params, errors
