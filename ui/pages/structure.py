"""전동기 구조 보기 페이지 (메뉴의 '전동기 구조'). 시뮬레이션과 따로, 구조만 살펴본다."""
import streamlit as st

from ui import structure_tab
from ui.compare import VARIANTS, build

INTRO = ("3D 모델을 마우스로 돌려 보고, 부품 위에 마우스를 올려 이름과 하는 일을 확인하세요. "
         "▶ 분해 / ▶ 조립으로 어떻게 조립되는지, 아래 전개도·결선도로 권선이 어떻게 감기고 연결되는지 볼 수 있습니다.")


def _poles(label, options, default, key):
    return st.select_slider(label, options=options, value=default, key=key,
                            format_func=lambda p: f"{p}극")


def dc():
    st.title("🔩 DC 전동기 구조")
    st.caption(INTRO)
    c = st.columns([1, 2, 3])
    with c[0]:
        P = _poles("극수", [2, 4, 6], 4, "sp_dc_P")
    with c[1]:
        labels = [v[0] for v in VARIANTS]
        exc = st.selectbox("여자 방식 (계자 결선)", labels, index=0, key="sp_dc_exc")
    with c[2]:
        st.caption("극수는 주극·브러시 개수와 전기자 권선 연결에, 여자 방식은 계자 코일 이름과 계자 결선도에 반영됩니다.")
    model = build(exc)
    structure_tab.render_dc(model, dict(model.p, poles=P))


def _ac_header(title, key, poles_opts, poles_def, allow_q=True):
    st.title(title)
    st.caption(INTRO)
    c = st.columns([1, 3])
    with c[0]:
        P = _poles("극수", poles_opts, poles_def, key)
    with c[1]:
        st.caption("권선 방식(분포권·집중권), 매극 매상 슬롯 수 q, 단절권 피치, Y·Δ 결선은 바로 아래에서 고릅니다. "
                   "고른 대로 3D 모델·전개도·결선도가 함께 바뀝니다.")
    return P


def bldc():
    P = _ac_header("🔩 BLDC 전동기 구조", "sp_bl_P", [2, 4, 6, 8, 10, 12], 8)
    structure_tab.render_bldc({"poles": float(P), "winding": 1.0, "q": 1.0})


def induction():
    P = _ac_header("🔩 유도전동기 구조", "sp_im_P", [2, 4, 6, 8], 4)
    structure_tab.render_induction({"poles": float(P), "winding": 0.0, "q": 2.0})


def pmsm():
    P = _ac_header("🔩 PMSM 구조", "sp_pm_P", [4, 6, 8, 10, 12], 8)
    structure_tab.render_pmsm({"poles": float(P), "winding": 0.0, "q": 1.0})

