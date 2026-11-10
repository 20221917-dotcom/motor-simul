"""⑤ 구조 탭: 3D 구조(돌려 보기·분해/조립·이름), 권선 전개도(분포권/집중권), 결선도, 부품 표."""
import streamlit as st

from motors.winding import make
from ui import structure3d as s3
from ui import winding_diagrams as wd
from ui.diagrams import wiring_diagram


def _parts_table(parts):
    rows, seen = [], set()
    for p in parts:
        if p.name in seen:
            continue
        seen.add(p.name)
        rows.append({"부품": p.name, "하는 일": p.desc})
    st.dataframe(rows, hide_index=True, width="stretch")


def _view_controls(prefix):
    c = st.columns(3)
    cut = c[0].checkbox("절개 보기 (앞쪽 일부를 잘라 안쪽 보기)", value=True, key=f"{prefix}_cut")
    labels = c[1].checkbox("부품 이름표 표시", value=True, key=f"{prefix}_lab")
    c[2].caption("🖱 끌기: 회전 · 휠: 확대 · 오른쪽 끌기: 이동 · 범례 클릭: 부품 숨기기 · 더블클릭: 그 부품만 보기")
    return cut, labels


def _show_3d(parts, labels, key):
    st.plotly_chart(s3.figure(parts, labels=labels), width="stretch", key=f"st3d_{key}",
                    config={"displaylogo": False, "scrollZoom": True})
    st.caption("▶ 분해 / ▶ 조립 버튼이나 아래 슬라이더로 부품이 어떤 순서로 빠지고 끼워지는지 볼 수 있습니다. "
               "마우스를 부품 위에 올리면 이름과 하는 일이 나옵니다.")


def _winding_controls(prefix, params, allow_conc=True, default_kind=None):
    P = int(round(params["poles"]))
    kinds = ["분포권", "집중권"] if allow_conc else ["분포권"]
    if default_kind is None:
        default_kind = "집중권" if float(params.get("winding", 0.0)) >= 0.5 else "분포권"
    c = st.columns(4)
    kind = c[0].radio("권선 방식", kinds, index=kinds.index(default_kind) if default_kind in kinds else 0,
                      horizontal=True, key=f"{prefix}_kind")
    q = int(round(params.get("q", 2)))
    pitch = None
    if kind == "분포권":
        q = c[1].selectbox("매극 매상 슬롯 수 q", [1, 2, 3], index=[1, 2, 3].index(q) if q in (1, 2, 3) else 1, key=f"{prefix}_q")
        tau = 3 * q
        pitch = c[2].slider("코일 피치 (단절권)", max(1, tau - 3), tau, tau, key=f"{prefix}_pitch",
                            help=f"극피치 = {tau} 슬롯. 극피치보다 짧으면 단절권 (고조파가 줄고 권선계수가 조금 작아짐)")
    else:
        c[1].caption(f"집중권: 이빨마다 코일 하나, 슬롯 수 = 3P/2 = {3 * P // 2}")
    conn = c[3].radio("결선", ["Y", "Δ"], horizontal=True, key=f"{prefix}_conn")
    w = make("concentrated" if kind == "집중권" else "distributed", P, q, pitch)
    return w, ("Y" if conn == "Y" else "D")


def _ac_diagrams(w, conn, key):
    st.markdown("#### 권선 전개도 (슬롯을 펼친 그림)")
    st.plotly_chart(wd.development(w), width="stretch", config={"displaylogo": False}, key=f"stdev_{key}")
    st.caption("세로선 = 슬롯 안 코일 변, 화살표 = 세 상 전류가 모두 + 일 때의 전류 방향, 위·아래 꺾인 선 = 코일 끝(엔드 턴). "
               "위쪽 글자는 슬롯 위층의 상대 (A+ 는 A상이 지면에서 나오는 방향). "
               + ("분포권은 한 극 아래 같은 상 코일을 여러 슬롯에 나눠 넣어 기자력이 정현파에 가까워집니다."
                  if w.kind == "distributed" else "집중권은 이빨 하나에 코일을 감아 코일 끝이 짧고 만들기 쉽지만 고조파가 많습니다."))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"#### 상 결선 ({'Y' if conn == 'Y' else 'Δ'})")
        st.plotly_chart(wd.connection(w, conn), width="stretch", config={"staticPlot": True}, key=f"stcon_{key}")
    with c2:
        st.markdown("#### 단자함 연결판")
        st.plotly_chart(wd.terminal_box(conn), width="stretch", config={"staticPlot": True}, key=f"sttb_{key}")


def render_induction(params):
    st.markdown("#### 3D 구조 — 3상 농형 유도전동기")
    cut, labels = _view_controls("st_im")
    w, conn = _winding_controls("st_im", params)
    _show_3d(s3.build_induction(w, cut), labels, "im")
    _ac_diagrams(w, conn, "im")
    st.markdown("#### 부품 이름과 역할")
    _parts_table(s3.build_induction(w, cut))


def render_pmsm(params):
    st.markdown("#### 3D 구조 — 매입형 영구자석 동기전동기 (IPM)")
    cut, labels = _view_controls("st_pm")
    w, conn = _winding_controls("st_pm", params)
    _show_3d(s3.build_pmsm(w, cut), labels, "pm")
    _ac_diagrams(w, conn, "pm")
    st.markdown("#### 부품 이름과 역할")
    _parts_table(s3.build_pmsm(w, cut))


def render_bldc(params):
    st.markdown("#### 3D 구조 — BLDC 전동기 (내전형, 표면 자석)")
    cut, labels = _view_controls("st_bl")
    w, conn = _winding_controls("st_bl", dict(params, q=1), default_kind="집중권")
    _show_3d(s3.build_bldc(w, cut), labels, "bl")
    st.markdown("#### 권선 전개도")
    st.plotly_chart(wd.development(w), width="stretch", config={"displaylogo": False}, key="stdev_bl")
    st.markdown("#### 결선 (권선 · 인버터 · 홀 센서)")
    st.plotly_chart(wd.bldc_connection(), width="stretch", config={"staticPlot": True}, key="stcon_bl")
    st.markdown("#### 부품 이름과 역할")
    _parts_table(s3.build_bldc(w, cut))


def render_dc(model, params):
    P = int(round(params.get("poles", 2)))
    st.markdown(f"#### 3D 구조 — {model.name} DC 전동기 ({P}극)")
    cut, labels = _view_controls("st_dc")
    parts = s3.build_dc(P, 24, cut, labels, model.excitation)
    _show_3d(parts, labels, "dc")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("#### 전기자 권선 전개도 (정류자 연결)")
        kinds = ["중권 (lap)", "파권 (wave)"]
        kind = st.radio("전기자 권선", kinds, horizontal=True, key="st_dc_arm")
        S = 12 if kind.startswith("중") else (13 if P == 4 else (16 if P == 6 else 12))
        if kind.startswith("파") and P == 6:
            S = 16                       # (S − 1)/(P/2) = 5 정수
        st.plotly_chart(wd.dc_armature(P, S, "lap" if kind.startswith("중") else "wave"), width="stretch",
                        config={"displaylogo": False}, key="starm_dc")
        st.caption("코일 두 변은 극피치만큼 떨어진 슬롯에 들어가 N극·S극 아래에서 같은 방향 토크를 냅니다. "
                   "중권은 코일 끝이 이웃 정류자편에 이어져 병렬 회로가 극수만큼(a = P) 생겨 대전류에 알맞고, "
                   "파권은 멀리 떨어진 정류자편으로 이어져 병렬 회로가 2개(a = 2)라 고전압에 알맞습니다.")
    with c2:
        st.markdown("#### 계자 결선")
        st.plotly_chart(wiring_diagram(model.excitation, getattr(model, "variant", "")), width="stretch",
                        config={"staticPlot": True}, key="stfield_dc")
        st.caption("단자 이름: 전기자 A1·A2, 분권/타여자 계자 F1·F2, 직권 계자 S1·S2.")
    st.markdown("#### 부품 이름과 역할")
    _parts_table(parts)
