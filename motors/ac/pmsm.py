"""영구자석 동기전동기 (PMSM, 매입형 IPM 기본값: Ld < Lq).

회전자 좌표 dq (진폭 불변), ωe = (P/2)·ωm
    vd = Rs·id + Ld·did/dt − ωe·Lq·iq
    vq = Rs·iq + Lq·diq/dt + ωe·(Ld·id + λf)
    Te = (3/2)·(P/2)·[λf·iq + (Ld − Lq)·id·iq]
전압 한계 (SVPWM 선형 영역): |v| ≤ Vdc/√3,  전류 한계: |i| ≤ I_max

계통 직결 운전: 상전압 진폭 Vm, 전원 각 θs → vd = Vm·cos(θs − θe), vq = Vm·sin(θs − θe)
    제동 권선(댐퍼)은 동기속도와의 속도 차에 비례하는 비동기 토크 Kd·(ωs − ωm) 로 단순화
"""
from dataclasses import dataclass
import math
import numpy as np

from core.params import ParamSpec
from core.units import to_rpm
from motors.base import MotorModel
from motors.registry import register

G_SUP, G_ST, G_RT, G_MEC, G_LOAD = "전원 (인버터)", "고정자", "회전자 (자석)", "기계", "부하 · 한계"


@dataclass(frozen=True)
class GridInputs:
    """계통 직결 운전 입력."""
    V: float          # 선간 전압 실효값
    f: float          # 주파수
    TL: float
    Kd: float = 0.0   # 제동 권선(댐퍼) 계수 [N·m·s/rad]: 비동기 토크 = Kd·(ωs − ωm)


@register
class PMSMMotor(MotorModel):
    family = "PMSM"
    key = "pmsm"
    name = "PMSM"
    state_names = ["id", "iq", "omega", "theta_m", "theta_s"]

    @classmethod
    def param_specs(cls):
        k = lambda s: "pm_" + s
        return [
            ParamSpec("Vdc", "Vdc", "인버터 직류 전압", "V", 300.0, G_SUP, step=10.0, ui_key=k("Vdc"),
                      help="상전압 진폭 한계 Vmax = Vdc/√3 (SVPWM)"),
            ParamSpec("Rs", "Rs", "고정자 저항", "Ω", 0.5, G_ST, step=0.05, ui_key=k("Rs")),
            ParamSpec("Ld", "Ld", "d축 인덕턴스", "mH", 5.0, G_ST, scale=1e-3, step=0.5, ui_key=k("Ld")),
            ParamSpec("Lq", "Lq", "q축 인덕턴스", "mH", 8.0, G_ST, scale=1e-3, step=0.5, ui_key=k("Lq"),
                      help="Ld = Lq 이면 표면 부착형(SPM), Lq > Ld 이면 매입형(IPM, 릴럭턴스 토크)"),
            ParamSpec("lam", "λf", "자석 쇄교 자속", "Wb", 0.15, G_RT, step=0.01, ui_key=k("lam")),
            ParamSpec("poles", "P", "극수", "극", 8.0, G_RT, step=2.0, ui_key=k("P")),
            ParamSpec("J", "J", "관성 모멘트", "kg·m²", 2e-3, G_MEC, step=1e-4, ui_key=k("J")),
            ParamSpec("B", "B", "점성 마찰 계수", "N·m·s/rad", 1e-4, G_MEC, allow_zero=True, step=1e-5, ui_key=k("B")),
            ParamSpec("TL", "TL", "부하 토크", "N·m", 5.0, G_LOAD, positive=False, step=0.5, ui_key=k("TL")),
            ParamSpec("Imax", "I_max", "최대 전류 (진폭)", "A", 15.0, G_LOAD, step=1.0, ui_key=k("Imax")),
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

    @property
    def Vmax(self):
        return self.p["Vdc"] / math.sqrt(3)

    def torque(self, id_, iq):
        p = self.p
        return 1.5 * self.pp * (p["lam"] * iq + (p["Ld"] - p["Lq"]) * id_ * iq)

    # ---- 정상상태 (dq 평면) ---------------------------------------------
    def voltage_mag(self, id_, iq, w_m):
        """정상상태 전압 크기 |v| (저항 강하 포함)."""
        p, we = self.p, self.pp * w_m
        vd = p["Rs"] * id_ - we * p["Lq"] * iq
        vq = p["Rs"] * iq + we * (p["Ld"] * id_ + p["lam"])
        return np.hypot(vd, vq)

    def mtpa(self, I):
        """전류 크기 I 에서 토크 최대가 되는 (id, iq). IPM 해석해."""
        p = self.p
        dL = p["Lq"] - p["Ld"]          # 매입형이면 > 0
        if abs(dL) < 1e-12:
            return 0.0 * I, I
        id_ = (p["lam"] - np.sqrt(p["lam"] ** 2 + 8 * dL ** 2 * I ** 2)) / (4 * dL)
        iq = np.sqrt(np.maximum(I ** 2 - id_ ** 2, 0.0))
        return id_, iq

    def max_torque_at_speed(self, w_m, n=361):
        """전류·전압 한계 안에서 낼 수 있는 최대 토크와 그때의 (id, iq)."""
        Imax = self.p["Imax"]
        best = (0.0, 0.0, 0.0)
        for I in np.linspace(Imax / 30, Imax, 30):
            beta = np.linspace(0, math.pi, n)               # 전류 벡터 각 (q축에서 −d 쪽으로)
            id_, iq = -I * np.sin(beta), I * np.cos(beta)
            ok = (self.voltage_mag(id_, iq, w_m) <= self.Vmax) & (iq >= 0)
            if not ok.any():
                continue
            T = np.where(ok, self.torque(id_, iq), -np.inf)
            j = int(np.argmax(T))
            if T[j] > best[0]:
                best = (float(T[j]), float(id_[j]), float(iq[j]))
        return best

    def base_speed(self):
        """MTPA, 최대 전류에서 전압 한계에 닿는 속도 [rad/s]."""
        id_, iq = self.mtpa(self.p["Imax"])
        lo, hi = 0.0, 1e5
        for _ in range(80):
            mid = (lo + hi) / 2
            if self.voltage_mag(id_, iq, mid) > self.Vmax:
                hi = mid
            else:
                lo = mid
        return lo

    def default_inputs(self):
        """계통 직결 기본값: 60 Hz, 상전압 진폭이 무부하 역기전력의 1.05 배."""
        we = 2 * math.pi * 60.0
        return GridInputs(V=round(1.05 * we * self.p["lam"] * math.sqrt(1.5), 1), f=60.0, TL=self.p["TL"])

    def steady_state(self, u=None):
        """속도 지령 없이 쓰지 않음 (PMSM 은 인버터로 운전). 대신 max_torque_at_speed 사용."""
        return None

    # ---- 계통 직결 운전 (동기 운전·탈조) ----------------------------------
    def initial_state(self, u=None):
        return np.zeros(5)

    def derivatives(self, t, x, u):
        p = self.p
        id_, iq, w, thm, ths = x
        the = self.pp * thm
        Vm = math.sqrt(2.0 / 3.0) * u.V
        vd, vq = Vm * math.cos(ths - the), Vm * math.sin(ths - the)
        we = self.pp * w
        did = (vd - p["Rs"] * id_ + we * p["Lq"] * iq) / p["Ld"]
        diq = (vq - p["Rs"] * iq - we * (p["Ld"] * id_ + p["lam"])) / p["Lq"]
        Te = self.torque(id_, iq)
        Tdamp = u.Kd * (2 * math.pi * u.f / self.pp - w)      # 제동 권선이 만드는 비동기 토크 (단순 모델)
        return np.array([did, diq, (Te + Tdamp - p["B"] * w - u.TL) / p["J"], w, 2 * math.pi * u.f])

    def outputs(self, X, u):
        id_, iq, w, thm, ths = X
        the = self.pp * thm
        ia = id_ * np.cos(the) - iq * np.sin(the)
        n = len(id_)
        return {"id": id_, "iq": iq, "omega": w, "rpm": to_rpm(w), "Te": self.torque(id_, iq), "ia": ia,
                # 부하각: 전원 전압 벡터가 q축(무부하 역기전력 방향)보다 앞선 각
                "delta_deg": np.rad2deg(np.angle(np.exp(1j * (ths - the - math.pi / 2)))),
                "TL": np.full(n, u.TL), "f": np.full(n, u.f), "V": np.full(n, u.V)}

    def pullout_torque(self, u):
        """계통 직결 정상 동기 운전의 최대(탈조) 토크와 그때의 부하각 [°] (고정자 저항 포함).
        (vd, vq) = Vm·(−sin δ, cos δ),  [vd; vq] = [[Rs, −ωe·Lq], [ωe·Ld, Rs]]·[id; iq] + [0; ωe·λf]"""
        p, we = self.p, 2 * math.pi * u.f
        Vm = math.sqrt(2.0 / 3.0) * u.V
        A = np.array([[p["Rs"], -we * p["Lq"]], [we * p["Ld"], p["Rs"]]])
        d = np.linspace(-math.pi / 2, math.pi, 3001)
        rhs = np.vstack([-Vm * np.sin(d), Vm * np.cos(d) - we * p["lam"]])
        id_, iq = np.linalg.solve(A, rhs)
        T = self.torque(id_, iq)
        j = int(np.argmax(T))
        return float(T[j]), float(np.rad2deg(d[j]))
