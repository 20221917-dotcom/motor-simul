"""타여자 DC 전동기 속도 제어 (이중 루프) 시뮬레이션.

    ω* ─▶[속도 PI]─▶[전류 제한]─▶ Ia* ─▶[전류 PI (+E 피드포워드)]─▶[초퍼]─▶ va ─▶[전동기]
          ▲ ω                              ▲ Ia

제어기는 샘플 주기 Ts 로 동작하는 디지털 제어기(영차 유지)이고,
전동기는 매 샘플 RK4 로 적분한다. 계자 전류는 정격으로 일정하다고 본다.
"""
from dataclasses import dataclass, field
import math
import numpy as np

from control.pi import PI
from control.chopper import Chopper


@dataclass
class ControlConfig:
    t_end: float = 4.0
    Ts: float = 1e-4
    refs: list = field(default_factory=lambda: [(0.0, 104.7)])  # [(시각 s, ω* rad/s)]
    t_load: float = 0.8
    TL: float = 30.0
    friction_load: bool = True   # True: 부하가 회전 반대 방향 / False: 방향 무관 일정 토크
    quadrants: int = 4
    I_lim: float = 40.0
    Kp_w: float = 2.8
    Ki_w: float = 35.0
    Kp_i: float = 10.0
    Ki_i: float = 500.0
    anti_windup: bool = True
    emf_ff: bool = True
    n_out: int = 3000            # 그래프용 출력 점 수


def _ref_at(refs, t):
    w = refs[0][1]
    for tk, wk in refs:
        if t >= tk:
            w = wk
    return w


class _Plant:
    """타여자 전동기 (Kφ 일정) 2상태 모델: ia, ω"""

    def __init__(self, Ra, La, J, B, kphi, friction_load, w_eps=1.0):
        self.Ra, self.La, self.J, self.B, self.K = Ra, La, J, B, kphi
        self.friction = friction_load
        self.w_eps = w_eps

    def load(self, TL, w):
        return TL * math.tanh(w / self.w_eps) if self.friction else TL

    def f(self, ia, w, va, TL):
        dia = (va - self.Ra * ia - self.K * w) / self.La
        dw = (self.K * ia - self.B * w - self.load(TL, w)) / self.J
        return dia, dw

    def rk4(self, ia, w, va, TL, h):
        k1 = self.f(ia, w, va, TL)
        k2 = self.f(ia + h / 2 * k1[0], w + h / 2 * k1[1], va, TL)
        k3 = self.f(ia + h / 2 * k2[0], w + h / 2 * k2[1], va, TL)
        k4 = self.f(ia + h * k3[0], w + h * k3[1], va, TL)
        ia += h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        w += h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        return ia, w


def run_cascade(motor_params: dict, kphi: float, cfg: ControlConfig, open_loop=False):
    """폐루프(또는 개루프) 시뮬레이션 결과를 dict 로 돌려준다 (SI 단위)."""
    p = motor_params
    plant = _Plant(p["Ra"], p["La"], p["J"], p["B"], kphi, cfg.friction_load)
    chop = Chopper(p["V"], cfg.quadrants)
    i_lo = 0.0 if cfg.quadrants == 1 else -cfg.I_lim
    spd = PI(cfg.Kp_w, cfg.Ki_w, i_lo, cfg.I_lim, cfg.anti_windup)
    cur = PI(cfg.Kp_i, cfg.Ki_i, chop.v_min, chop.v_max, cfg.anti_windup)

    n = int(round(cfg.t_end / cfg.Ts))
    every = max(n // cfg.n_out, 1)
    keys = ["t", "w_ref", "omega", "ia_ref", "ia_ref_unsat", "ia", "va", "va_cmd", "Te", "TL",
            "E"]
    out = {k: [] for k in keys}

    ia, w = 0.0, 0.0
    h = cfg.Ts
    for k in range(n + 1):
        t = k * h
        w_ref = _ref_at(cfg.refs, t)
        TL = cfg.TL if t >= cfg.t_load else 0.0
        E = kphi * w

        if open_loop:
            # 개루프: 지령 속도에 해당하는 역기전력만큼 전압을 건다 (피드백 없음)
            ia_ref = ia_ref_u = float("nan")
            va_cmd = kphi * w_ref
        else:
            ia_ref, ia_ref_u = spd.step(w_ref - w, h)
            ff = E if cfg.emf_ff else 0.0
            va_cmd, _ = cur.step(ia_ref - ia, h, ff=ff)
        va = chop.limit(va_cmd)

        if k % every == 0:
            # 1상한에서 전류가 0 이고 va < E 이면 단자 전압은 역기전력과 같다
            va_term = E if (chop.current_unidirectional and ia <= 0 and va < E) else va
            for key, val in zip(keys, (t, w_ref, w, ia_ref, ia_ref_u, ia, va_term, va_cmd,
                                       kphi * ia, plant.load(TL, w), E)):
                out[key].append(val)

        ia, w = plant.rk4(ia, w, va, TL, h)
        if chop.current_unidirectional and ia < 0:
            ia = 0.0   # 1상한: 환류 다이오드 때문에 전류가 음으로 가지 못함 (불연속 전류)

    return {k: np.asarray(v) for k, v in out.items()}
