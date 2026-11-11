"""강의 실습 페이지 공통 도우미."""
import streamlit as st

from ui.plots import style


def link(label, path):
    """같은 앱의 다른 메뉴로 가는 링크 (같은 탭에서 열림)."""
    st.markdown(f'<a href="./{path}" target="_self">👉 {label}</a>', unsafe_allow_html=True)


def ref(text):
    """교재 위치와 확인할 점."""
    st.caption("📖 " + text)


def check(*items):
    """'시뮬레이션으로 확인할 것' 목록."""
    st.markdown("**확인해 보기**\n" + "\n".join(f"- {x}" for x in items))


def lstyle(fig, height=380, side_legend=False, **kw):
    """강의 페이지 그래프 스타일: 범례를 그래프 아래에 두어 소제목과 겹치지 않게."""
    if side_legend:
        return style(fig, height=height, side_legend=True, **kw)
    style(fig, height=height + 70, **kw)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.2, x=0, xanchor="left"),
                      margin=dict(l=10, r=10, t=40, b=70))
    return fig


def thin(d, n=2500):
    """그래프용으로 시계열을 솎아 냄 (브라우저로 보내는 점 수를 줄여 반응을 빠르게). 같은 길이의 배열만 처리."""
    import numpy as np
    t = d.get("t")
    if t is None or len(t) <= n:
        return d
    step = int(np.ceil(len(t) / n))
    out = {}
    for k, v in d.items():
        if isinstance(v, np.ndarray) and v.ndim >= 1 and v.shape[-1] == len(t):
            out[k] = v[..., ::step]
        else:
            out[k] = v
    return out
