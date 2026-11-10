"""브라우저에서 실시간으로 도는 시뮬레이터 위젯.

계산(미분방정식 적분, 제어기)이 모두 브라우저(JavaScript)에서 돌기 때문에
슬라이더를 움직이면 서버 왕복 없이 바로 반영되고, 현재 상태에서 이어서 반응한다.
JS 엔진(engine.js)은 파이썬 모델과 같은 식이며 tests/test_js_engine.py 로 비교 검증한다.
"""
import json
import pathlib

import streamlit as st

_DIR = pathlib.Path(__file__).parent


def _read(name):
    return (_DIR / name).read_text(encoding="utf-8")


def _build(template, config):
    html = _read(template)
    html = html.replace("/*CSS*/", _read("common.css"))
    html = html.replace("/*ENGINE*/", _read("engine.js"))
    html = html.replace("/*CHARTS*/", _read("charts.js"))
    html = html.replace("/*STRUCTURE*/", _read("structure.js"))
    html = html.replace("/*BLOCKS*/", _read("blocks.js"))
    html = html.replace("/*BLDC*/", _read("bldc_engine.js"))
    html = html.replace("/*AC*/", _read("ac_engine.js"))
    html = html.replace("/*ACDRAW*/", _read("ac_draw.js"))
    return html.replace("/*CONFIG*/", json.dumps(config))


def _motor_p(params):
    """JS 엔진용 파라미터 (없는 키는 0 으로 채움)."""
    keys = ["Ra", "La", "Rf", "Lf", "Laf", "Rs", "Ls", "Ms", "J", "B"]
    return {k: float(params.get(k, 0.0)) for k in keys}


def principle_html(model, params):
    u = model.default_inputs()
    op = model.steady_state(u) or model.no_load(u)
    I_r = params["I_rated"]
    if_nom = float(model.field_ss(I_r, u))
    cfg = {
        "type": model.excitation, "sigma": float(params.get("sigma", 1.0)),
        "p": _motor_p(params),
        "V": u.V, "Vf": u.Vf, "Rfx": u.Rfx, "TL": u.TL,
        "Trated": model.rated_torque(), "Irated": I_r,
        "wNom": op.omega if op and op.omega > 1 else 100.0,
        "ifNom": if_nom,
        "forceRef": float(model.kphi(I_r, if_nom) * I_r),
        "fieldCtrl": model.field_control_input,
    }
    return _build("principle.html", cfg)


def control_html(params, kphi, Ts=1e-4):
    cfg = {
        "p": {"Ra": params["Ra"], "La": params["La"], "J": params["J"], "B": params["B"],
              "V": params["V"]},
        "K": kphi, "Ts": Ts, "Irated": params["I_rated"],
        "Trated": kphi * params["I_rated"],
        # 기본 속도 지령: 1000 rpm, 단 낼 수 있는 최고 속도의 85 % 이하
        "wRefRpm": float(min(1000.0, round(0.85 * params["V"] / kphi * 60 / 6.283185 / 10) * 10)),
    }
    return _build("control.html", cfg)


def render(html, height):
    """HTML 위젯을 iframe 으로 표시 (같은 HTML 이면 다시 그려도 iframe 이 유지되어 시뮬레이션이 이어진다)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:   # 구버전 Streamlit
        import streamlit.components.v1 as components
        components.html(html, height=height, scrolling=False)


def editor_html(motors, default_motor, ctrl, bldc=None, im=None, pmsm=None):
    """제어 블록 편집기. motors: DC 전동기 {이름: {type, sigma, p, V, Vf, Rfx}},
    ctrl: DC 템플릿 게인 계산용, bldc / im / pmsm: 각 전동기 블록·템플릿용 파라미터."""
    cfg = {"motors": motors, "defaultMotor": default_motor, "ctrl": ctrl, "bldc": bldc, "im": im, "pmsm": pmsm}
    return _build("editor.html", cfg)


def _bldc_p(params):
    return {k: float(params[k]) for k in ["Vdc", "R", "L", "ke", "poles", "J", "B"]}


def bldc_principle_html(params):
    cfg = {"p": _bldc_p(params), "TL": params["TL"], "Irated": params["I_rated"],
           "Trated": 2 * params["ke"] * params["I_rated"]}
    return _build("bldc_principle.html", cfg)


def bldc_control_html(params):
    cfg = {"p": _bldc_p(params), "TL": params["TL"], "Irated": params["I_rated"],
           "Trated": 2 * params["ke"] * params["I_rated"]}
    return _build("bldc_control.html", cfg)


# ---------------------------------------------------------------- 교류 전동기
def _im_cfg(model):
    p = model.p
    keys = ["V", "f", "Rs", "Rr", "Lls", "Llr", "Lm", "poles", "J", "B"]
    Tmax, _ = model.max_torque()
    Ls = p["Lls"] + p["Lm"]
    psr = (2 / 3) ** 0.5 * p["V"] / (2 * 3.141592653589793 * p["f"]) * p["Lm"] / Ls
    return {"p": {k: float(p[k]) for k in keys}, "TL": p["TL"], "Irated": p["I_rated"], "Tmax": Tmax, "psrNom": psr}


def im_principle_html(model):
    return _build("im_principle.html", _im_cfg(model))


def im_control_html(model):
    return _build("im_control.html", _im_cfg(model))


def _pmsm_cfg(model):
    p = model.p
    keys = ["Vdc", "Rs", "Ld", "Lq", "lam", "poles", "J", "B"]
    T0 = model.max_torque_at_speed(1.0)[0]
    return {"p": {k: float(p[k]) for k in keys}, "TL": p["TL"], "Imax": p["Imax"], "Tmax": T0,
            "nBase": model.base_speed() * 60 / (2 * 3.141592653589793)}


def pmsm_principle_html(model):
    return _build("pmsm_principle.html", _pmsm_cfg(model))


def pmsm_control_html(model):
    return _build("pmsm_control.html", _pmsm_cfg(model))
