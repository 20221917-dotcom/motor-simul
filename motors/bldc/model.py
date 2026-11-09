"""BLDC 전동기 (3상 Y결선, 사다리꼴 역기전력, 홀 센서 6스텝 120° 통전).

상 방정식 (x = a, b, c, 중성점 전압 vn)
    L·dix/dt = vx − vn − R·ix − ex,        ia + ib + ic = 0
    ex = ke·ωm·f(θe − φx)                  f: 평탄 구간 120° 의 사다리꼴 (진폭 1)
    Te = ke·(fa·ia + fb·ib + fc·ic),       J·dωm/dt = Te − B·ωm − TL,   θe = (P/2)·θm

인버터 (평균값 PWM, 듀티 d)
    홀 센서 코드로 '+ 쪽 상 H' 와 '− 쪽 상 L' 을 고른다. vH = |d|·Vdc, vL = 0 (d < 0 이면 H, L 을 바꿈).
    나머지 상 F 는 스위치가 꺼져 있다. 그 상에 전류가 남아 있으면 환류 다이오드로 흐른다
    (iF > 0 → vF = 0, iF < 0 → vF = Vdc). 전류가 0 이 되면 F 는 끊기고 두 상만 도통한다.
    정류 때마다 이 과정 때문에 토크 리플(정류 리플)이 생긴다.

평균 모델 (정상상태 탭): 평탄 구간에서 선간 역기전력 = 2·ke·ω, 토크 = 2·ke·I 이므로
    d·Vdc = 2R·I + 2·ke·ω,  Te = 2·ke·I     (DC 전동기와 같은 꼴, Kφ ↔ 2·ke)
"""
from dataclasses import dataclass, field, replace
import math
import numpy as np

from core.params import ParamSpec
from core.units import to_rpm
from motors.base import MotorModel
from motors.registry import register

TWO_PI = 2 * math.pi
PHASES = "abc"
SHIFT = (0.0, TWO_PI / 3, -TWO_PI / 3)       # φa, φb, φc

# 홀 코드 (Ha Hb Hc 를 2진수로) → (+ 쪽 상, − 쪽 상)
COMMUTATION = {4: (0, 1), 6: (0, 2), 2: (1, 2), 3: (1, 0), 1: (2, 0), 5: (2, 1)}


def trap(theta):
    """평탄 구간 120°, 경사 60° 인 사다리꼴 (주기 2π, 진폭 1). θ = 30°~150° 에서 +1."""
    x = theta % TWO_PI
    if x < math.pi / 6:
        return x / (math.pi / 6)
    if x < 5 * math.pi / 6:
        return 1.0
    if x < 7 * math.pi / 6:
        return 1.0 - (x - 5 * math.pi / 6) / (math.pi / 6)
    if x < 11 * math.pi / 6:
        return -1.0
    return -1.0 + (x - 11 * math.pi / 6) / (math.pi / 6)


def hall_code(theta_e, offset=0.0):
    """홀 센서 3개 (전기각 120° 간격). 전환점이 정류 시점(30° + k·60°)과 맞게 배치."""
    code = 0
    for k, sh in enumerate(SHIFT):
        h = ((theta_e + offset + math.pi / 6 - sh) % TWO_PI) < math.pi
        code |= (1 if h else 0) << (2 - k)
    return code


G_SUP, G_STA, G_ROT, G_MEC, G_LOAD = "전원", "고정자 (상당)", "회전자 · 역기전력", "기계", "부하"


@dataclass(frozen=True)
class BLDCInputs:
    duty: float = 1.0          # PWM 듀티 −1 ~ 1 (음수: 역방향)
    TL: float = 0.0
    hall_offset: float = 0.0   # 홀 센서 위치 오차 [rad, 전기각]
    friction: bool = False


@dataclass
class BLDCOperatingPoint:
    omega: float
    I: float
    Te: float
    TL: float
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
class BLDCMotor(MotorModel):
    family = "BLDC"
    key = "bldc"
    name = "BLDC"
    state_names = ["ia", "ib", "ic", "omega", "theta_m"]

    @classmethod
    def param_specs(cls):
        k = lambda s: "bl_" + s     # DC 전동기와 화면 키가 겹치지 않게
        return [
            ParamSpec("Vdc", "Vdc", "직류 전원 전압", "V", 48.0, G_SUP, step=1.0, ui_key=k("Vdc")),
            ParamSpec("R", "R", "상 저항", "Ω", 0.5, G_STA, step=0.05, ui_key=k("R")),
            ParamSpec("L", "L", "상 인덕턴스 (L − M)", "mH", 0.2, G_STA, scale=1e-3, step=0.05,
                      ui_key=k("L")),
            ParamSpec("ke", "ke", "상 역기전력 상수 (평탄부)", "V·s/rad", 0.05, G_ROT, step=0.005,
                      ui_key=k("ke"), help="상 역기전력 평탄부 = ke·ωm. 토크 = 2·ke·I (두 상 도통)"),
            ParamSpec("poles", "P", "극수", "극", 8.0, G_ROT, step=2.0, ui_key=k("P"),
                      help="전기각 θe = (P/2)·θm"),
            ParamSpec("J", "J", "관성 모멘트", "kg·m²", 1e-4, G_MEC, step=1e-5, ui_key=k("J")),
            ParamSpec("B", "B", "점성 마찰 계수", "N·m·s/rad", 1e-5, G_MEC, allow_zero=True,
                      step=1e-6, ui_key=k("B")),
            ParamSpec("TL", "TL", "부하 토크", "N·m", 0.3, G_LOAD, positive=False, step=0.05,
                      ui_key=k("TL")),
            ParamSpec("I_rated", "I정격", "정격 전류 (기준값)", "A", 10.0, G_LOAD, step=1.0,
                      ui_key=k("Ir")),
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

    # ---- 입력 ------------------------------------------------------------
    def default_inputs(self):
        return BLDCInputs(duty=1.0, TL=self.p["TL"])

    def initial_state(self, u=None):
        return np.zeros(5)

    # ---- 인버터 ----------------------------------------------------------
    def phase_voltages(self, x, u):
        """(vx 3개, 모드, H, L, F). 모드: 'three' (F 가 다이오드로 도통) / 'two'."""
        ia, ib, ic, w, th = x
        i = (ia, ib, ic)
        code = hall_code(self.pp * th, u.hall_offset)
        H, L = COMMUTATION[code]
        if u.duty < 0:
            H, L = L, H
        F = 3 - H - L
        Vdc = self.p["Vdc"]
        v = [0.0, 0.0, 0.0]
        v[H] = min(abs(u.duty), 1.0) * Vdc
        v[L] = 0.0
        if abs(i[F]) > 1e-9:
            v[F] = 0.0 if i[F] > 0 else Vdc
            return v, "three", H, L, F
        return v, "two", H, L, F

    def emf_shape(self, theta_e):
        return [trap(theta_e - s) for s in SHIFT]

    def derivatives(self, t, x, u, mode_info=None):
        p = self.p
        ia, ib, ic, w, th = x
        i = [ia, ib, ic]
        v, mode, H, L, F = mode_info or self.phase_voltages(x, u)
        f = self.emf_shape(self.pp * th)
        e = [p["ke"] * w * fx for fx in f]
        di = [0.0, 0.0, 0.0]
        if mode == "three":
            vn = (sum(v) - sum(e)) / 3.0
            for k in range(3):
                di[k] = (v[k] - vn - p["R"] * i[k] - e[k]) / p["L"]
        else:
            dH = (v[H] - v[L] - p["R"] * (i[H] - i[L]) - (e[H] - e[L])) / (2 * p["L"])
            di[H], di[L], di[F] = dH, -dH, 0.0
        Te = p["ke"] * (f[0] * ia + f[1] * ib + f[2] * ic)
        TL = u.TL * math.tanh(w / 1.0) if u.friction else u.TL
        dw = (Te - p["B"] * w - TL) / p["J"]
        return np.array([di[0], di[1], di[2], dw, w])

    def step(self, x, u, h):
        """모드를 고정한 RK4 한 스텝 + 떠 있는 상 전류가 0 을 지나면 끊음."""
        info = self.phase_voltages(x, u)
        f = lambda y: self.derivatives(0.0, y, u, info)
        k1 = f(x); k2 = f(x + h / 2 * k1); k3 = f(x + h / 2 * k2); k4 = f(x + h * k3)
        xn = x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        _, mode, H, L, F = info
        if mode == "three" and np.sign(xn[F]) != np.sign(x[F]):
            xn[F] = 0.0                       # 환류 다이오드 전류가 0 → 그 상은 끊김
            m = (xn[H] - xn[L]) / 2           # 남은 두 상은 크기 같고 방향 반대
            xn[H], xn[L] = m, -m
        if mode == "two":
            xn[F] = 0.0
            xn[L] = -xn[H]
        return xn

    def outputs_at(self, x, u):
        p = self.p
        ia, ib, ic, w, th = x
        f = self.emf_shape(self.pp * th)
        v, mode, H, L, F = self.phase_voltages(x, u)
        return {"Te": p["ke"] * (f[0] * ia + f[1] * ib + f[2] * ic),
                "ea": p["ke"] * w * f[0], "eb": p["ke"] * w * f[1], "ec": p["ke"] * w * f[2],
                "idc": abs(x[H]) if mode else 0.0, "code": hall_code(self.pp * th, u.hall_offset),
                "H": H, "L": L}

    def outputs(self, X, u):
        raise NotImplementedError("BLDC 는 simulate_fixed 로 계산합니다.")

    # ---- 시간 응답 (고정 스텝) -------------------------------------------
    def simulate_fixed(self, u0, t_end, h=1e-5, events=(), record_dt=None, x0=None):
        """events: [(시각, {필드: 값})]. 반환: 이름 → 배열 dict."""
        x = self.initial_state() if x0 is None else np.array(x0, dtype=float)
        u = u0
        evs = sorted(events, key=lambda e: e[0])
        n = int(round(t_end / h))
        every = max(1, int(round((record_dt or h) / h)))
        rec = {k: [] for k in ["t", "ia", "ib", "ic", "omega", "theta_e", "Te", "ea", "eb", "ec",
                               "idc", "code", "TL", "duty"]}
        j = 0
        for k in range(n + 1):
            t = k * h
            while j < len(evs) and t >= evs[j][0]:
                u = replace(u, **evs[j][1]); j += 1
            if k % every == 0:
                o = self.outputs_at(x, u)
                for name, val in (("t", t), ("ia", x[0]), ("ib", x[1]), ("ic", x[2]),
                                  ("omega", x[3]), ("theta_e", (self.pp * x[4]) % TWO_PI),
                                  ("Te", o["Te"]), ("ea", o["ea"]), ("eb", o["eb"]), ("ec", o["ec"]),
                                  ("idc", o["idc"]), ("code", o["code"]), ("TL", u.TL),
                                  ("duty", u.duty)):
                    rec[name].append(val)
            x = self.step(x, u, h)
        out = {k: np.asarray(v) for k, v in rec.items()}
        out["rpm"] = to_rpm(out["omega"])
        return out

    # ---- 평균 모델 (정상상태) --------------------------------------------
    @property
    def K(self):
        """등가 토크 상수 = 선간 역기전력 상수 = 2·ke."""
        return 2 * self.p["ke"]

    def steady_state(self, u=None):
        u = u or self.default_inputs()
        p, K, R2 = self.p, self.K, 2 * self.p["R"]
        V = u.duty * p["Vdc"]
        # V = R2·I + K·ω,  K·I = TL + B·ω
        w = (V - R2 * u.TL / K) / (K + R2 * p["B"] / K)
        if w < 0:
            return None
        I = (u.TL + p["B"] * w) / K
        P_in = V * I
        losses = {"동손 (2·R·I²)": R2 * I ** 2, "기계손 (Bω²)": p["B"] * w ** 2}
        return BLDCOperatingPoint(omega=w, I=I, Te=K * I, TL=u.TL, P_in=P_in, P_out=u.TL * w,
                                  losses=losses)

    def no_load(self, u=None):
        u = u or self.default_inputs()
        return self.steady_state(replace(u, TL=0.0))

    def speed_torque_curve(self, u=None, I_max=None, n=200):
        u = u or self.default_inputs()
        p, K = self.p, self.K
        V = u.duty * p["Vdc"]
        I_stall = V / (2 * p["R"])
        I = np.linspace(0, min(I_max or I_stall, I_stall), n)
        return K * I, (V - 2 * p["R"] * I) / K, I

    def rated_torque(self):
        return self.K * self.p["I_rated"]
