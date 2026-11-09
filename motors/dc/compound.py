"""복권 DC 전동기 (장분권 결선): 분권 계자는 전원 V 양단, 직권 계자는 전기자와 직렬."""
import numpy as np
from motors.registry import register
from motors.dc.base_dc import (DCMotor, SPEC_V, SPECS_ARM, SPECS_SHUNT_FIELD,
                               SPECS_SERIES_FIELD_COMPOUND, SPEC_COMPOUND_SIGN, SPECS_MECH,
                               SPECS_LOAD)


@register
class CompoundDC(DCMotor):
    key = "dc_compound"
    name = "복권"
    excitation = "compound"
    field_control_input = "Rfx"
    summary_md = """
**복권 전동기**는 분권 계자와 직권 계자를 **둘 다** 가진다. 여기서는 **장분권** 결선이다
(분권 계자가 전원 V 양단에 연결되고, 직권 계자는 전기자와 직렬).

- Kφ = Laf·If **± Ms·Ia**
- **가동 복권 (+)**: 부하가 늘면 자속도 늘어 분권보다 **기동 토크가 크고**, 직권처럼
  폭주하지 않는다 (무부하 속도가 정해져 있음). 프레스, 압연기, 엘리베이터 등.
- **차동 복권 (−)**: 부하가 늘면 자속이 줄어 속도가 거의 일정하거나 오히려 올라간다.
  과부하나 기동 때 직권 자속이 분권 자속을 넘으면 **Kφ 가 음수가 되어 역회전**할 수 있어
  **불안정**하다. 실제로는 거의 쓰지 않는다.
- 두 계자 사이의 상호 인덕턴스는 무시했다.
"""

    steady_latex = [
        r"I_f = \frac{V}{R_f + R_{fx}},\quad K\phi = L_{af} I_f \pm M_s I_a"
        r"\quad(+ \text{가동},\; - \text{차동})",
        r"\omega = \frac{V - I_a (R_a + R_s)}{L_{af} I_f \pm M_s I_a}",
        r"K\phi\, I_a = T_L + B\omega,\qquad I_L = I_a + I_f,\quad P_{in} = V I_L",
    ]

    @classmethod
    def param_specs(cls):
        return [SPEC_V, *SPECS_ARM, *SPECS_SHUNT_FIELD, *SPECS_SERIES_FIELD_COMPOUND,
                SPEC_COMPOUND_SIGN, *SPECS_MECH, *SPECS_LOAD]

    @property
    def sigma(self):
        return 1.0 if self.p.get("sigma", 1.0) >= 0 else -1.0

    @property
    def variant(self):
        return "가동 복권" if self.sigma > 0 else "차동 복권"

    def kphi(self, ia, if_):
        return self.p["Laf"] * if_ + self.sigma * self.p["Ms"] * ia

    def R_field(self, u):
        return self.p["Rf"] + u.Rfx

    def field_ss(self, ia, u):
        return np.zeros_like(np.asarray(ia, dtype=float)) + u.V / self.R_field(u)

    def R_arm(self, u):
        return self.p["Ra"] + self.p["Rs"] + u.Rst

    def L_arm(self):
        return self.p["La"] + self.p["Ls"]

    def line_current(self, ia, if_):
        return ia + if_

    def input_power(self, ia, if_, u):
        return u.V * (ia + if_)

    def losses(self, ia, if_, omega, u):
        return {
            "전기자 동손": ia ** 2 * self.p["Ra"],
            "직권 계자 동손": ia ** 2 * self.p["Rs"],
            "기동 저항 손실": ia ** 2 * u.Rst,
            "계자 동손": if_ ** 2 * self.R_field(u),
            "기계손 (Bω²)": self.p["B"] * omega ** 2,
        }

    def derivatives(self, t, x, u):
        ia, if_, w = x
        p = self.p
        k = self.kphi(ia, if_)
        dia = (u.V - self.R_arm(u) * ia - k * w) / self.L_arm()
        dif = (u.V - self.R_field(u) * if_) / p["Lf"]
        dw = (k * ia - p["B"] * w - u.TL) / p["J"]
        return np.array([dia, dif, dw])
