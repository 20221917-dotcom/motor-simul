"""브라우저에서 실시간으로 도는 시뮬레이터 위젯.

계산(미분방정식 적분, 제어기)이 모두 브라우저(JavaScript)에서 돌기 때문에
슬라이더를 움직이면 서버 왕복 없이 바로 반영되고, 현재 상태에서 이어서 반응한다.
JS 엔진(engine.js)은 파이썬 모델과 같은 식이며 tests/test_js_engine.py 로 비교 검증한다.
"""
import json
import pathlib

import streamlit.components.v1 as components

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
    components.html(html, height=height, scrolling=False)


def editor_html(motors, default_motor, ctrl):
    """제어 블록 편집기. motors: {이름: {type, sigma, p, V, Vf, Rfx}}, ctrl: 템플릿 게인 계산용."""
    cfg = {"motors": motors, "defaultMotor": default_motor, "ctrl": ctrl}
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
