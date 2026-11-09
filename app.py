"""전동기 학습용 시뮬레이터 — 실행: streamlit run app.py

왼쪽 사이드바는 메뉴(직류 전동기 / BLDC 전동기 / 교류 전동기(유도·PMSM) / 제어 실습 / 관련 개념)이고,
각 페이지의 파라미터 설정은 메인 화면 위쪽에 있다.
새 전동기 페이지를 추가할 때는 ui/pages/ 에 render 함수를 만들고 아래 목록에 넣으면 된다.
"""
import streamlit as st

from ui.pages import bldc, concepts, dc_blocks, dc_sim, induction, pmsm

st.set_page_config(page_title="전동기 학습 시뮬레이터", page_icon="⚙️", layout="wide")

pages = {
    "직류 전동기": [
        st.Page(dc_sim.render, title="DC 전동기 시뮬레이터", icon="⚙️", default=True),
    ],
    "BLDC 전동기": [
        st.Page(bldc.render, title="BLDC 전동기 시뮬레이터", icon="⚡", url_path="bldc"),
    ],
    "교류 전동기": [
        st.Page(induction.render, title="유도전동기 시뮬레이터", icon="🌀", url_path="induction"),
        st.Page(pmsm.render, title="PMSM 시뮬레이터 (동기)", icon="🧲", url_path="pmsm"),
    ],
    "제어 실습": [
        st.Page(dc_blocks.render, title="제어 블록 편집기 (DC · BLDC)", icon="🧩", url_path="blocks"),
    ],
    "관련 개념": [
        st.Page(concepts.em_basics, title="전자기 기초 (힘·기전력)", icon="🧭", url_path="em-basics"),
        st.Page(concepts.commutation, title="정류 원리", icon="🔁", url_path="commutation"),
        st.Page(concepts.magnetic, title="자기회로와 Kφ", icon="🧲", url_path="magnetic"),
        st.Page(concepts.control_basics, title="제어 기초 (PI·대역폭)", icon="🎛️", url_path="control-basics"),
        st.Page(concepts.symbols, title="기호와 단위", icon="📘", url_path="symbols"),
    ],
}
st.navigation(pages, position="sidebar", expanded=True).run()
