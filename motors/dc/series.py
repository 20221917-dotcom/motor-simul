"""직권 DC 전동기: 계자 권선을 전기자와 직렬 연결 → 계자 전류 = 전기자 전류."""
import numpy as np
from motors.registry import register
from motors.dc.base_dc import (DCMotor, SPEC_V, SPECS_ARM, SPECS_SERIES_FIELD, SPECS_MECH,
                               SPECS_LOAD, SPEC_POLES_DC)


@register
class SeriesDC(DCMotor):
    key = "dc_series"
    name = "직권"
    excitation = "series"
    field_control_input = ""      # 이 모델에서는 계자만 따로 조정하지 않음
    state_names = ["ia", "omega"]
    summary_md = """
**직권 전동기**는 계자 권선을 전기자와 **직렬**로 연결한다. 그래서 계자 전류 = 전기자 전류다.

- Kφ = Ms·Ia → **T = Ms·Ia²** (선형 자기회로 가정). 전류가 커지면 토크가 제곱으로 커져
  **기동 토크가 매우 크다**.
- 속도: ω = (V − Ia·(Ra+Rs)) / (Ms·Ia). 부하가 줄면 Ia 가 줄고 자속도 줄어 **속도가 급상승**한다.
  속도–토크 특성은 쌍곡선 모양이다.
- ⚠️ **무부하 운전 금지**: 부하가 빠지면 속도가 마찰과 균형을 이룰 때까지 올라간다
  (B = 0 이면 이론상 무한대). 벨트 구동을 쓰지 않는다.
- 전동차, 크레인, 시동 전동기처럼 큰 기동 토크가 필요한 곳에 쓴다.
"""

    steady_latex = [
        r"K\phi = M_s I_a \;\Rightarrow\; T_e = M_s I_a^2",
        r"\omega = \frac{V - I_a (R_a + R_s)}{M_s I_a}"
        r" = \frac{V}{\sqrt{M_s T_e}} - \frac{R_a + R_s}{M_s}",
        r"M_s I_a^2 = T_L + B\omega,\qquad P_{in} = V I_a",
    ]

    @classmethod
    def param_specs(cls):
        return [SPEC_V, *SPECS_ARM, *SPECS_SERIES_FIELD, *SPECS_MECH, *SPECS_LOAD, SPEC_POLES_DC]

    def kphi(self, ia, if_):
        return self.p["Ms"] * if_

    def field_ss(self, ia, u):
        return np.asarray(ia, dtype=float)

    def R_arm(self, u):
        return self.p["Ra"] + self.p["Rs"] + u.Rst

    def L_arm(self):
        return self.p["La"] + self.p["Ls"]

    def input_power(self, ia, if_, u):
        return u.V * ia

    def losses(self, ia, if_, omega, u):
        return {
            "전기자 동손": ia ** 2 * self.p["Ra"],
            "직권 계자 동손": ia ** 2 * self.p["Rs"],
            "기동 저항 손실": ia ** 2 * u.Rst,
            "기계손 (Bω²)": self.p["B"] * omega ** 2,
        }

    def state_vector(self, ia, if_, w):
        return np.array([ia, w], dtype=float)

    def _unpack(self, X):
        return X[0], X[0], X[1]

    def initial_state(self, u, field_preexcited=True):
        return np.array([0.0, 0.0])

    def derivatives(self, t, x, u):
        ia, w = x
        p = self.p
        k = p["Ms"] * ia
        dia = (u.V - self.R_arm(u) * ia - k * w) / self.L_arm()
        dw = (k * ia - p["B"] * w - u.TL) / p["J"]
        return np.array([dia, dw])
