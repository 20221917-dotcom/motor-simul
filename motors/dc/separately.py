"""타여자 DC 전동기: 계자를 별도 전원 Vf 로 여자한다."""
import numpy as np
from motors.registry import register
from motors.dc.base_dc import (DCMotor, SPEC_V, SPEC_VF, SPECS_ARM, SPECS_SHUNT_FIELD,
                               SPECS_MECH, SPECS_LOAD)


@register
class SeparatelyExcitedDC(DCMotor):
    key = "dc_separately"
    name = "타여자"
    excitation = "separately"
    field_control_input = "Vf"
    summary_md = """
**타여자 전동기**는 계자 권선을 전기자와 **별개의 전원 Vf** 로 여자한다.

- 계자 전류 If = Vf / (Rf + Rfx) 가 전기자 전압·부하와 **무관**하므로 Kφ 가 일정하다.
- 속도–토크 특성이 **직선**: ω = V/Kφ − (Ra/Kφ²)·T. 부하가 늘어도 속도가 조금만 떨어진다.
- **전기자 전압 제어**(기저속도 이하, 정토크)와 **계자 약화**(기저속도 이상, 정출력)를
  따로따로 할 수 있어서 속도 제어 교재의 기준 모델로 쓴다.
- 주의: 운전 중 계자가 끊기면 Kφ → 0 이 되어 속도가 급상승하고 전기자 전류가 커진다.
"""

    @classmethod
    def param_specs(cls):
        return [SPEC_V, SPEC_VF, *SPECS_ARM, *SPECS_SHUNT_FIELD, *SPECS_MECH, *SPECS_LOAD]

    # ---- 여자 방식 고유 부분 -------------------------------------------
    def kphi(self, ia, if_):
        return self.p["Laf"] * if_

    def R_field(self, u):
        return self.p["Rf"] + u.Rfx

    def field_ss(self, ia, u):
        return np.zeros_like(np.asarray(ia, dtype=float)) + u.Vf / self.R_field(u)

    def input_power(self, ia, if_, u):
        # 전기자 전원 + 계자 전원 입력
        return u.V * ia + u.Vf * if_

    def losses(self, ia, if_, omega, u):
        return {
            "전기자 동손": ia ** 2 * self.p["Ra"],
            "기동 저항 손실": ia ** 2 * u.Rst,
            "계자 동손": if_ ** 2 * self.R_field(u),
            "기계손 (Bω²)": self.p["B"] * omega ** 2,
        }

    # ---- 동특성 ----------------------------------------------------------
    def initial_state(self, u, field_preexcited=True):
        if_ = u.Vf / self.R_field(u) if field_preexcited else 0.0
        return np.array([0.0, if_, 0.0])

    def derivatives(self, t, x, u):
        ia, if_, w = x
        p = self.p
        k = p["Laf"] * if_
        dia = (u.V - (p["Ra"] + u.Rst) * ia - k * w) / p["La"]
        dif = (u.Vf - self.R_field(u) * if_) / p["Lf"]
        dw = (k * ia - p["B"] * w - u.TL) / p["J"]
        return np.array([dia, dif, dw])
