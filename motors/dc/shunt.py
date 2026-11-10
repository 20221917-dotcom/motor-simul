"""분권 DC 전동기: 계자 권선을 전기자와 병렬로 같은 전원 V 에 연결."""
import numpy as np
from motors.registry import register
from motors.dc.base_dc import (DCMotor, SPEC_V, SPECS_ARM, SPECS_SHUNT_FIELD, SPECS_MECH,
                               SPECS_LOAD, SPEC_POLES_DC)


@register
class ShuntDC(DCMotor):
    key = "dc_shunt"
    name = "분권"
    excitation = "shunt"
    field_control_input = "Rfx"
    summary_md = """
**분권 전동기**는 계자 권선을 전기자와 **병렬**로 같은 전원 V 에 연결한다.

- If = V / (Rf + Rfx). 전원 전압이 일정하면 Kφ 가 일정해서 특성이 **타여자와 거의 같다**
  (거의 일정한 속도, 직선 속도–토크 특성).
- 선전류 IL = Ia + If. 계자 동손도 같은 전원이 공급한다.
- **속도 조정**: 계자 조정 저항 Rfx 를 키우면 If 가 줄어 속도가 올라간다 (계자 제어).
- 주의: 전원 전압을 낮추면 **계자 전류도 같이 줄어든다**. 그래서 전압만 바꿔서는 속도가
  타여자처럼 크게 변하지 않는다. 동특성 탭의 '전압 제어'로 직접 비교해 보자.
- 공작기계, 팬, 펌프처럼 일정 속도가 필요한 곳에 쓴다.
"""

    steady_latex = [
        r"I_f = \frac{V}{R_f + R_{fx}},\quad K\phi = L_{af} I_f,\quad I_L = I_a + I_f",
        r"\omega = \frac{V - I_a R_a}{K\phi} = \frac{V}{K\phi} - \frac{R_a}{(K\phi)^2}T_e",
        r"K\phi I_a = T_L + B\omega,\qquad P_{in} = V I_L",
    ]

    @classmethod
    def param_specs(cls):
        return [SPEC_V, *SPECS_ARM, *SPECS_SHUNT_FIELD, *SPECS_MECH, *SPECS_LOAD, SPEC_POLES_DC]

    def kphi(self, ia, if_):
        return self.p["Laf"] * if_

    def R_field(self, u):
        return self.p["Rf"] + u.Rfx

    def field_ss(self, ia, u):
        return np.zeros_like(np.asarray(ia, dtype=float)) + u.V / self.R_field(u)

    def line_current(self, ia, if_):
        return ia + if_

    def input_power(self, ia, if_, u):
        return u.V * (ia + if_)

    def losses(self, ia, if_, omega, u):
        return {
            "전기자 동손": ia ** 2 * self.p["Ra"],
            "기동 저항 손실": ia ** 2 * u.Rst,
            "계자 동손": if_ ** 2 * self.R_field(u),
            "기계손 (Bω²)": self.p["B"] * omega ** 2,
        }

    def derivatives(self, t, x, u):
        ia, if_, w = x
        p = self.p
        k = p["Laf"] * if_
        dia = (u.V - (p["Ra"] + u.Rst) * ia - k * w) / p["La"]
        dif = (u.V - self.R_field(u) * if_) / p["Lf"]   # 계자도 전원 V 에 연결
        dw = (k * ia - p["B"] * w - u.TL) / p["J"]
        return np.array([dia, dif, dw])
