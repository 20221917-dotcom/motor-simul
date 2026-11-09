"""DC 전동기 공통 모델.

공통 방정식
    E  = Kφ·ω
    Te = Kφ·Ia
    V  = Ia·R + L·dIa/dt + E        (R, L 은 전기자 회로 전체: 직권 계자·기동 저항 포함)
    J·dω/dt = Te − B·ω − TL

여자 방식(타여자/분권/직권/복권)은 다음 몇 가지만 다르다.
    - Kφ 를 만드는 방법           kphi(ia, if_)
    - 정상상태 계자 전류           field_ss(ia, u)
    - 전기자 회로 저항·인덕턴스    R_arm(u), L_arm()
    - 선전류, 입력 전력, 손실      line_current, input_power, losses
정상상태 해는 Ia 를 매개변수로 두고 근을 찾는 공통 방식으로 구하므로
하위 클래스는 위 함수만 구현하면 된다.
"""
from dataclasses import dataclass, field, replace
import numpy as np
from scipy.optimize import brentq

from core.params import ParamSpec
from core.units import to_rpm
from motors.base import MotorModel


# --------------------------------------------------------------------------
# 입력과 결과
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DCInputs:
    """시간에 따라 바꿀 수 있는 입력 (SI 단위)."""
    V: float          # 전기자(단자) 전압 [V]
    Vf: float         # 계자 전원 전압 [V] (타여자만 사용)
    Rfx: float        # 계자 조정 저항 [Ω]
    TL: float         # 부하 토크 [N·m]
    Rst: float = 0.0  # 기동 저항 [Ω] (전기자와 직렬)


@dataclass
class OperatingPoint:
    omega: float
    ia: float
    if_: float
    il: float
    kphi: float
    E: float
    Te: float
    TL: float
    V: float
    P_in: float
    P_out: float
    losses: dict = field(default_factory=dict)
    stable: bool = True

    @property
    def rpm(self):
        return to_rpm(self.omega)

    @property
    def eta(self):
        return self.P_out / self.P_in if self.P_in > 0 else float("nan")


# --------------------------------------------------------------------------
# 파라미터 묶음 (여러 여자 방식이 재사용)
# --------------------------------------------------------------------------
G_SUP, G_ARM, G_FLD, G_SER, G_MEC, G_LOAD = (
    "전원", "전기자", "분권/타여자 계자", "직권 계자", "기계", "부하")

SPEC_V = ParamSpec("V", "V", "전기자 전압", "V", 220.0, G_SUP, step=10.0)
SPEC_VF = ParamSpec("Vf", "Vf", "계자 전원 전압", "V", 220.0, G_SUP, step=10.0,
                    help="타여자 전동기의 계자 회로에 거는 별도 전원")
SPECS_ARM = [
    ParamSpec("Ra", "Ra", "전기자 저항", "Ω", 0.5, G_ARM, step=0.05),
    ParamSpec("La", "La", "전기자 인덕턴스", "mH", 10.0, G_ARM, scale=1e-3, step=1.0),
]
SPECS_SHUNT_FIELD = [
    ParamSpec("Rf", "Rf", "계자 권선 저항", "Ω", 220.0, G_FLD, step=10.0),
    ParamSpec("Rfx", "Rfx", "계자 조정 저항", "Ω", 0.0, G_FLD, allow_zero=True, step=10.0,
              help="키우면 계자 전류가 줄어 계자 약화(속도 상승)"),
    ParamSpec("Lf", "Lf", "계자 인덕턴스", "H", 20.0, G_FLD, step=1.0),
    ParamSpec("Laf", "Laf", "계자-전기자 결합계수", "H", 1.8, G_FLD, step=0.1,
              help="Kφ = Laf·If"),
]
SPECS_SERIES_FIELD = [
    ParamSpec("Rs", "Rs", "직권 계자 저항", "Ω", 0.3, G_SER, step=0.05),
    ParamSpec("Ls", "Ls", "직권 계자 인덕턴스", "mH", 5.0, G_SER, scale=1e-3, step=1.0),
    ParamSpec("Ms", "Ms", "직권 결합계수", "H", 0.08, G_SER, step=0.01, help="Kφ = Ms·Ia"),
]
SPECS_MECH = [
    ParamSpec("J", "J", "관성 모멘트", "kg·m²", 0.1, G_MEC, step=0.01),
    ParamSpec("B", "B", "점성 마찰 계수", "N·m·s/rad", 0.005, G_MEC, allow_zero=True,
              step=0.001),
]
SPECS_LOAD = [
    ParamSpec("TL", "TL", "부하 토크", "N·m", 30.0, G_LOAD, positive=False, step=5.0),
    ParamSpec("I_rated", "I정격", "정격 전류 (기준값)", "A", 20.0, G_LOAD, step=1.0,
              help="돌입 전류 배수, 과전류 경고의 기준"),
]


# --------------------------------------------------------------------------
# DC 전동기 기반 클래스
# --------------------------------------------------------------------------
class DCMotor(MotorModel):
    family = "DC"
    state_names = ["ia", "if", "omega"]
    excitation = ""            # "separately" | "shunt" | "series" | "compound"
    field_control_input = "Vf"  # 동특성 탭의 '계자 변경'이 바꾸는 입력
    summary_md = ""

    # ---- 하위 클래스가 구현 ---------------------------------------------
    def kphi(self, ia, if_):
        raise NotImplementedError

    def field_ss(self, ia, u):
        """정상상태 계자 전류."""
        raise NotImplementedError

    def R_arm(self, u):
        return self.p["Ra"] + u.Rst

    def L_arm(self):
        return self.p["La"]

    def line_current(self, ia, if_):
        return ia

    def input_power(self, ia, if_, u):
        raise NotImplementedError

    def losses(self, ia, if_, omega, u) -> dict:
        raise NotImplementedError

    # ---- 공통 ------------------------------------------------------------
    def default_inputs(self) -> DCInputs:
        p = self.p
        return DCInputs(V=p["V"], Vf=p.get("Vf", p["V"]), Rfx=p.get("Rfx", 0.0),
                        TL=p["TL"], Rst=0.0)

    def with_field_ratio(self, u, ratio):
        """계자 전류를 기준값의 ratio 배로 바꾼 입력 (계자 세기 슬라이더용)."""
        if self.field_control_input == "Vf":
            return replace(u, Vf=u.Vf * ratio)
        if self.field_control_input == "Rfx":
            r_total = (self.p["Rf"] + u.Rfx) / max(ratio, 1e-6)
            return replace(u, Rfx=max(r_total - self.p["Rf"], 0.0))
        return u

    def rated_torque(self):
        """정격 전류, 정격 계자에서의 토크 (그래프 범위 기준용)."""
        u = self.default_inputs()
        ia = self.p["I_rated"]
        return float(self.kphi(ia, self.field_ss(ia, u)) * ia)

    def outputs(self, X, u) -> dict:
        ia, if_, w = X[0], X[1], X[2]
        k = self.kphi(ia, if_)
        E = k * w
        R = self.R_arm(u)
        n = len(ia)
        v_R = ia * R
        return {
            "ia": ia, "if": if_, "omega": w, "rpm": to_rpm(w),
            "kphi": k, "E": E, "Te": k * ia,
            "il": self.line_current(ia, if_),
            "TL": np.full(n, u.TL), "V": np.full(n, u.V), "Vf": np.full(n, u.Vf),
            "Rst": np.full(n, u.Rst),
            "v_R": v_R, "v_L": u.V - v_R - E,   # L·dIa/dt = V − Ia·R − E
        }

    # ---- 정상상태 --------------------------------------------------------
    def _ss_curve(self, ia, u):
        """Ia → (If, Kφ, ω, Te) : 정상상태 속도–토크 관계를 Ia 로 매개화."""
        if_ = self.field_ss(ia, u)
        k = self.kphi(ia, if_)
        with np.errstate(divide="ignore", invalid="ignore"):
            w = (u.V - self.R_arm(u) * ia) / k
        return if_, k, w, k * ia

    def _residual(self, ia, u):
        _, _, w, te = self._ss_curve(ia, u)
        return te - self.p["B"] * w - u.TL

    def _ia_max(self, u):
        """정지(ω=0) 전류 V/R."""
        return u.V / self.R_arm(u)

    def steady_state(self, u=None) -> OperatingPoint | None:
        u = u or self.default_inputs()
        i_stall = self._ia_max(u)
        if i_stall <= 0:
            return None
        # 발전기 영역(음의 TL)까지 포함해 Ia 를 훑어서 부호가 바뀌는 곳을 찾는다
        grid = np.linspace(-i_stall, i_stall, 4001)
        grid = grid[np.abs(grid) > 1e-9 * i_stall]
        with np.errstate(divide="ignore", invalid="ignore"):
            f = self._residual(grid, u)
            _, k, w, _ = self._ss_curve(grid, u)
        ok = np.isfinite(f) & np.isfinite(w) & (np.abs(k) > 1e-9)
        roots = []
        for j in range(len(grid) - 1):
            if ok[j] and ok[j + 1] and np.sign(f[j]) != np.sign(f[j + 1]):
                r = brentq(lambda i: float(self._residual(i, u)), grid[j], grid[j + 1],
                           xtol=1e-12)
                roots.append(r)
            elif ok[j] and f[j] == 0.0:
                roots.append(grid[j])
        cands = []
        for ia in roots:
            op = self._make_op(ia, u)
            if op.omega >= 0:
                cands.append(op)
        if not cands:
            return None
        # 안정한 해를 우선, 그 중 속도가 가장 높은 해
        cands.sort(key=lambda o: (not o.stable, -o.omega))
        return cands[0]

    def _make_op(self, ia, u) -> OperatingPoint:
        if_, k, w, te = (float(v) for v in self._ss_curve(ia, u))
        # 안정 판별: 속도–토크 곡선 기울기 dTe/dω < B 이면 안정
        d = 1e-6 * max(abs(ia), 1.0)
        _, _, w1, t1 = self._ss_curve(ia - d, u)
        _, _, w2, t2 = self._ss_curve(ia + d, u)
        slope = (t2 - t1) / (w2 - w1) if w2 != w1 else -np.inf
        stable = bool(slope - self.p["B"] < 0)
        losses = {k_: float(v) for k_, v in self.losses(ia, if_, w, u).items()}
        return OperatingPoint(
            omega=w, ia=float(ia), if_=if_, il=float(self.line_current(ia, if_)),
            kphi=k, E=k * w, Te=te, TL=u.TL, V=u.V,
            P_in=float(self.input_power(ia, if_, u)), P_out=u.TL * w,
            losses=losses, stable=stable)

    def no_load(self, u=None) -> OperatingPoint | None:
        u = u or self.default_inputs()
        return self.steady_state(replace(u, TL=0.0))

    def speed_torque_curve(self, u=None, ia_max=None, n=400):
        """(Te, ω) 배열. ω ≥ 0 인 전동기 영역만."""
        u = u or self.default_inputs()
        ia_max = min(ia_max or np.inf, self._ia_max(u))
        ia = np.linspace(1e-4 * ia_max, ia_max, n)
        _, _, w, te = self._ss_curve(ia, u)
        m = np.isfinite(w) & (w >= 0)
        return te[m], w[m], ia[m]
