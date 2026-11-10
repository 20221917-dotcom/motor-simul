"""3상 농형 유도전동기.

동적 모델 (고정자 좌표 αβ, 진폭 불변 변환, 회전자 값은 고정자 쪽으로 환산)
    dψs/dt = vs − Rs·is
    dψr/dt = −Rr·ir + j·ωr·ψr               (ωr = (P/2)·ωm, 전기각속도)
    ψs = Ls·is + Lm·ir,   ψr = Lm·is + Lr·ir,  Ls = Lls + Lm, Lr = Llr + Lm
    Te = (3/2)·(P/2)·(ψsα·isβ − ψsβ·isα),   J·dωm/dt = Te − B·ωm − TL
전원: 상전압 진폭 Vm = √2·V_LL/√3, 각도 θs (상태로 적분 → 주파수를 바꿔도 위상이 이어짐)

정상상태: 상당 등가회로 (실효값)
    Z = (Rs + jXls) + jXm ∥ (Rr/s + jXlr),   Pag = 3·|I2|²·Rr/s,   T = Pag/ωs
"""
from dataclasses import dataclass, field, replace
import math
import numpy as np
from scipy.optimize import brentq

from core.params import ParamSpec
from core.units import to_rpm
from motors.base import MotorModel
from motors.registry import register

G_SUP, G_ST, G_RT, G_MAG, G_MEC, G_LOAD = ("전원", "고정자", "회전자 (고정자 환산)", "자화", "기계", "부하")


@dataclass(frozen=True)
class IMInputs:
    V: float          # 선간 전압 실효값 [V]
    f: float          # 전원 주파수 [Hz]
    TL: float         # 부하 토크 [N·m]


@dataclass
class IMOperatingPoint:
    s: float
    omega: float
    T: float
    I1: float
    I2: float
    pf: float
    P_in: float
    P_out: float
    losses: dict = field(default_factory=dict)

    @property
    def rpm(self):
        return to_rpm(self.omega)

    @property
    def eta(self):
        return self.P_out / self.P_in if self.P_in > 0 else float("nan")


@register
class InductionMotor(MotorModel):
    family = "IM"
    key = "induction"
    name = "유도전동기"
    state_names = ["psa", "psb", "pra", "prb", "omega", "theta_s"]

    @classmethod
    def param_specs(cls):
        k = lambda s: "im_" + s
        return [
            ParamSpec("V", "V_LL", "선간 전압 (실효값)", "V", 380.0, G_SUP, step=10.0, ui_key=k("V")),
            ParamSpec("f", "f", "전원 주파수", "Hz", 60.0, G_SUP, step=1.0, ui_key=k("f")),
            ParamSpec("Rs", "Rs", "고정자 저항", "Ω", 0.5, G_ST, step=0.05, ui_key=k("Rs")),
            ParamSpec("Lls", "Lls", "고정자 누설 인덕턴스", "mH", 3.2, G_ST, scale=1e-3, step=0.1, ui_key=k("Lls"),
                      help="60 Hz 에서 Xls = 2π·60·Lls ≈ 1.2 Ω"),
            ParamSpec("Rr", "Rr′", "회전자 저항 (환산)", "Ω", 0.4, G_RT, step=0.05, ui_key=k("Rr")),
            ParamSpec("Llr", "Llr′", "회전자 누설 인덕턴스 (환산)", "mH", 3.2, G_RT, scale=1e-3, step=0.1, ui_key=k("Llr")),
            ParamSpec("Lm", "Lm", "자화 인덕턴스", "mH", 106.0, G_MAG, scale=1e-3, step=1.0, ui_key=k("Lm"),
                      help="60 Hz 에서 Xm ≈ 40 Ω"),
            ParamSpec("poles", "P", "극수", "극", 4.0, G_MAG, step=2.0, ui_key=k("P")),
            ParamSpec("winding", "권선", "권선 방식", "", 0.0, "구조 (그림용)", ui_key=k("wind"),
                      choices=(("분포권", 0.0), ("집중권", 1.0)),
                      help="단면 그림·3D 구조·권선 전개도에 쓰입니다. 계산은 등가 파라미터로 하므로 결과에는 영향이 없습니다."),
            ParamSpec("q", "q", "매극 매상 슬롯 수 (분포권)", "", 2.0, "구조 (그림용)", ui_key=k("q"),
                      choices=(("1", 1.0), ("2", 2.0), ("3", 3.0)), help="슬롯 수 S = 3·P·q (집중권은 S = 3P/2)"),
            ParamSpec("J", "J", "관성 모멘트", "kg·m²", 0.1, G_MEC, step=0.01, ui_key=k("J")),
            ParamSpec("B", "B", "점성 마찰 계수", "N·m·s/rad", 0.002, G_MEC, allow_zero=True, step=0.001, ui_key=k("B")),
            ParamSpec("TL", "TL", "부하 토크", "N·m", 30.0, G_LOAD, positive=False, step=1.0, ui_key=k("TL")),
            ParamSpec("I_rated", "I정격", "정격 전류 (실효값)", "A", 13.0, G_LOAD, step=1.0, ui_key=k("Ir")),
        ]

    def validate(self):
        errs = super().validate()
        P = self.p["poles"]
        if P < 2 or abs(P / 2 - round(P / 2)) > 1e-9:
            errs.append("극수 P 는 2 이상의 짝수여야 합니다.")
        return errs

    @property
    def pp(self):
        return int(round(self.p["poles"] / 2))

    def default_inputs(self):
        return IMInputs(V=self.p["V"], f=self.p["f"], TL=self.p["TL"])

    def initial_state(self, u=None):
        return np.zeros(6)

    # ---- 동적 모델 --------------------------------------------------------
    def _L(self):
        p = self.p
        Ls, Lr, Lm = p["Lls"] + p["Lm"], p["Llr"] + p["Lm"], p["Lm"]
        return Ls, Lr, Lm, Ls * Lr - Lm ** 2

    def currents(self, X):
        Ls, Lr, Lm, D = self._L()
        psa, psb, pra, prb = X[0], X[1], X[2], X[3]
        isa, isb = (Lr * psa - Lm * pra) / D, (Lr * psb - Lm * prb) / D
        ira, irb = (Ls * pra - Lm * psa) / D, (Ls * prb - Lm * psb) / D
        return isa, isb, ira, irb

    def derivatives(self, t, x, u):
        p = self.p
        psa, psb, pra, prb, w, th = x
        isa, isb, ira, irb = self.currents(x)
        Vm = math.sqrt(2.0 / 3.0) * u.V
        va, vb = Vm * math.cos(th), Vm * math.sin(th)
        wr = self.pp * w
        Te = 1.5 * self.pp * (psa * isb - psb * isa)
        return np.array([
            va - p["Rs"] * isa, vb - p["Rs"] * isb,
            -p["Rr"] * ira - wr * prb, -p["Rr"] * irb + wr * pra,
            (Te - p["B"] * w - u.TL) / p["J"],
            2 * math.pi * u.f,
        ])

    def outputs(self, X, u):
        isa, isb, ira, irb = self.currents(X)
        Te = 1.5 * self.pp * (X[0] * isb - X[1] * isa)
        ia, ib, ic = isa, -0.5 * isa + math.sqrt(3) / 2 * isb, -0.5 * isa - math.sqrt(3) / 2 * isb
        n = len(isa)
        ws = 2 * math.pi * u.f / self.pp
        return {"ia": ia, "ib": ib, "ic": ic, "omega": X[4], "rpm": to_rpm(X[4]), "Te": Te,
                "Is": np.hypot(isa, isb) / math.sqrt(2),     # 상전류 실효값 (순시 크기 기준)
                "slip": (ws - X[4]) / ws if ws > 0 else np.zeros(n),
                "TL": np.full(n, u.TL), "V": np.full(n, u.V), "f": np.full(n, u.f),
                "psr": np.hypot(X[2], X[3])}

    # ---- 등가회로 ---------------------------------------------------------
    def _circuit(self, s, u):
        p, w_e = self.p, 2 * math.pi * u.f
        Vph = u.V / math.sqrt(3)
        Zs = p["Rs"] + 1j * w_e * p["Lls"]
        Zm = 1j * w_e * p["Lm"]
        s = np.asarray(s, dtype=float)
        Zr = p["Rr"] / s + 1j * w_e * p["Llr"]
        Z = Zs + Zm * Zr / (Zm + Zr)
        I1 = Vph / Z
        I2 = I1 * Zm / (Zm + Zr)
        return Vph, Z, I1, I2

    def ws(self, u):
        return 2 * math.pi * u.f / self.pp

    def torque(self, s, u):
        _, _, _, I2 = self._circuit(s, u)
        return 3 * np.abs(I2) ** 2 * self.p["Rr"] / np.asarray(s) / self.ws(u)

    def max_torque(self, u=None):
        """(Tmax, s_max) — 테브난 등가."""
        u = u or self.default_inputs()
        p, w_e = self.p, 2 * math.pi * u.f
        Zs = p["Rs"] + 1j * w_e * p["Lls"]
        Zm = 1j * w_e * p["Lm"]
        Vth = u.V / math.sqrt(3) * abs(Zm / (Zs + Zm))
        Zth = Zs * Zm / (Zs + Zm)
        R, X = Zth.real, Zth.imag + w_e * p["Llr"]
        root = math.hypot(R, X)
        return 3 * Vth ** 2 / (2 * self.ws(u) * (R + root)), p["Rr"] / root

    def operating_point_at(self, s, u):
        p = self.p
        Vph, Z, I1, I2 = self._circuit(s, u)
        T = float(3 * abs(I2) ** 2 * p["Rr"] / s / self.ws(u))
        w = (1 - s) * self.ws(u)
        pf = math.cos(np.angle(Z))
        P_in = 3 * Vph * abs(I1) * pf
        Pag = T * self.ws(u)
        losses = {"고정자 동손": 3 * abs(I1) ** 2 * p["Rs"], "회전자 동손 (s·Pag)": s * Pag,
                  "기계손 (Bω²)": p["B"] * w ** 2}
        return IMOperatingPoint(s=s, omega=w, T=T, I1=abs(I1), I2=abs(I2), pf=pf, P_in=P_in,
                                P_out=u.TL * w, losses=losses)

    def steady_state(self, u=None):
        """안정 운전점 (0 < s < s_max 구간)."""
        u = u or self.default_inputs()
        if u.f <= 0 or u.V <= 0:
            return None
        Tmax, smax = self.max_torque(u)
        f = lambda s: float(self.torque(s, u)) - u.TL - self.p["B"] * (1 - s) * self.ws(u)
        lo, hi = 1e-7, min(smax, 1.0)
        if f(lo) > 0 or f(hi) < 0:
            return None
        s = brentq(f, lo, hi, xtol=1e-12)
        return self.operating_point_at(s, u)

    def no_load(self, u=None):
        u = u or self.default_inputs()
        return self.steady_state(replace(u, TL=0.0))

    def rated_torque(self):
        op = self.steady_state()
        return op.T if op else self.max_torque()[0] / 3
