"""ParamSpec 목록으로 사이드바 입력 위젯을 자동 생성."""
import streamlit as st


def _key(spec):
    return f"p_{spec.key}"


def reset_defaults(specs):
    for s in specs:
        st.session_state[_key(s)] = float(s.default)


def render_sidebar(model_cls):
    """사이드바를 그리고 (SI 파라미터 dict, 오류 목록) 을 돌려준다."""
    specs = model_cls.param_specs()
    sb = st.sidebar
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
                k = _key(s)
                if k not in st.session_state:
                    st.session_state[k] = float(s.default)
                val = st.number_input(f"{s.symbol} · {s.label} [{s.unit}]", key=k,
                                      step=s.step, format="%.4g", help=s.help or None)
                params[s.key] = s.to_si(val)

    model = model_cls(params)
    errors = model.validate()
    for e in errors:
        sb.error(e)
    return params, errors
