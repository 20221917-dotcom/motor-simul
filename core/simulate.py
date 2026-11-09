"""시간 응답 시뮬레이션 엔진 (모든 전동기 공용).

입력이 계단처럼 바뀌는 시각(이벤트)마다 적분을 끊어서 구간별로 solve_ivp를 돌린다.
이렇게 하면 불연속 입력에서도 적분기가 불연속점을 정확히 지난다.
"""
from dataclasses import dataclass, replace, field
import numpy as np
from scipy.integrate import solve_ivp


@dataclass
class Event:
    t: float
    changes: dict          # 입력 dataclass 의 필드 이름 → 새 값
    label: str = ""


@dataclass
class SimResult:
    t: np.ndarray
    x: np.ndarray                       # (상태 수, 시간 수)
    signals: dict = field(default_factory=dict)  # 이름 → 배열 (상태 + 파생 신호 + 입력)
    events: list = field(default_factory=list)

    def __getitem__(self, name):
        return self.signals[name]


def simulate(model, u0, t_end, x0=None, events=(), n_points=2000, max_step=None,
             method="LSODA", rtol=1e-6, atol=1e-8):
    """model: MotorModel, u0: 초기 입력(dataclass), events: Event 목록."""
    x0 = model.initial_state(u0) if x0 is None else np.asarray(x0, dtype=float)
    evs = sorted([e for e in events if 0.0 < e.t < t_end], key=lambda e: e.t)
    bounds = [0.0] + [e.t for e in evs] + [t_end]
    if max_step is None:
        max_step = t_end / 400.0

    u = u0
    ts, xs, sigs = [], [], []
    x = x0
    for k in range(len(bounds) - 1):
        if k > 0:
            u = replace(u, **evs[k - 1].changes)
        t0, t1 = bounds[k], bounds[k + 1]
        if t1 <= t0:
            continue
        n = max(int(n_points * (t1 - t0) / t_end), 10)
        t_eval = np.linspace(t0, t1, n)
        sol = solve_ivp(lambda t, y, uu=u: model.derivatives(t, y, uu),
                        (t0, t1), x, t_eval=t_eval, method=method,
                        max_step=max_step, rtol=rtol, atol=atol)
        if not sol.success:
            raise RuntimeError(f"적분 실패: {sol.message}")
        ts.append(sol.t)
        xs.append(sol.y)
        sigs.append(model.outputs(sol.y, u))
        x = sol.y[:, -1]

    t = np.concatenate(ts)
    X = np.concatenate(xs, axis=1)
    signals = {name: np.concatenate([s[name] for s in sigs]) for name in sigs[0]}
    return SimResult(t=t, x=X, signals=signals, events=evs)
