"""1장 전동기의 기본 원리: 자기회로, 릴럭턴스 토크, 이중 여자 기기, 부하 시스템, 4상한 운전."""
import math

import numpy as np

MU0 = 4e-7 * math.pi
_trapz = getattr(np, "trapezoid", None) or np.trapz   # numpy 1.x / 2.x
G = 9.81


# ---------------------------------------------------------------- 1.2.1 자기회로 (λ-i 특성)
def flux_density(F, g, lc=0.3, mur=4000.0, Bs=1.6):
    """기자력 F = N·i [A] 일 때 철심 + 공극 자기회로의 자속 밀도 B [T].
    철심 B–H: B = Bs·tanh(μr μ0 H / Bs) (포화), 공극: H = B/μ0.  N·i = Hc·lc + B·g/μ0 를 이분법으로 풉니다."""
    F = np.asarray(F, dtype=float)
    lo, hi = np.full(F.shape, -Bs * (1 - 1e-12)), np.full(F.shape, Bs * (1 - 1e-12))
    for _ in range(80):
        B = 0.5 * (lo + hi)
        Hc = Bs / (mur * MU0) * np.arctanh(B / Bs)
        f = Hc * lc + B * g / MU0 - F
        hi = np.where(f > 0, B, hi)
        lo = np.where(f > 0, lo, B)
    return 0.5 * (lo + hi)


def lambda_i(i, N=200, A=4e-4, g=1e-3, lc=0.3, mur=4000.0, Bs=1.6):
    """쇄교 자속 λ = N·B·A [Wb·turn]."""
    return N * A * flux_density(N * np.asarray(i, dtype=float), g, lc, mur, Bs)


def energy_coenergy(i_max, n=400, **kw):
    """0 → i_max 까지 전류를 올릴 때 자기 에너지 W = ∫ i dλ, 코에너지 W' = ∫ λ di [J]."""
    i = np.linspace(0, i_max, n)
    lam = lambda_i(i, **kw)
    Wc = float(_trapz(lam, i))
    W = float(i[-1] * lam[-1] - Wc)
    return W, Wc, i, lam


def gap_force(i, g, N=200, A=4e-4, lc=0.3, mur=4000.0, Bs=1.6, dg=1e-6):
    """직선 운동 기계(단일 여자)에서 운동자에 걸리는 힘 F = ∂W'(i, g)/∂g [N] (전류 일정).
    음수 = 공극을 줄이는 쪽(고정자 쪽)으로 당김. 인덕턴스가 커지는 방향으로 힘이 작용."""
    kw = dict(N=N, A=A, lc=lc, mur=mur, Bs=Bs)
    W1 = energy_coenergy(i, g=g + dg, **kw)[1]
    W0 = energy_coenergy(i, g=max(g - dg, 1e-7), **kw)[1]
    return (W1 - W0) / (2 * dg)


def gap_force_linear(i, g, N=200, A=4e-4, lc=0.3, mur=4000.0):
    """선형(포화 없음)일 때의 해석해: L(g) = N²μ0A/(g + lc/μr),  F = ½ i² dL/dg."""
    ge = g + lc / mur
    return -0.5 * i * i * N * N * MU0 * A / (ge * ge)


def linear_machine_paths(i0, x1, x2, n=200, **kw):
    """직선 운동 기계: 공극 x1 → x2 (감소) 이동 시 λ-i 평면의 두 경로와 기계적 에너지.
    매우 빠르게(λ 일정): A(i0, x1) → C(같은 λ, x2) → B(i0, x2).  매우 느리게(i 일정): A → B.
    반환 dict(i, lam1, lam2, A, B, C, W_fast, W_slow)."""
    i = np.linspace(0, max(i0 * 1.6, 1e-6), n)
    lam1, lam2 = lambda_i(i, g=x1, **kw), lambda_i(i, g=x2, **kw)
    lA, lB = float(lambda_i(i0, g=x1, **kw)), float(lambda_i(i0, g=x2, **kw))
    iC = float(np.interp(lA, lam2, i))
    # 빠른 이동: 기계적 에너지 = 이동 전후 자기 에너지 감소 (λ 일정) = 면적 OAC
    WA = energy_coenergy(i0, g=x1, **kw)[0]
    WC = energy_coenergy(iC, g=x2, **kw)[0] if iC > 0 else 0.0
    # 느린 이동: 기계적 에너지 = 코에너지 증가 (i 일정) = 면적 OAB
    Wc1 = energy_coenergy(i0, g=x1, **kw)[1]; Wc2 = energy_coenergy(i0, g=x2, **kw)[1]
    return dict(i=i, lam1=lam1, lam2=lam2, A=(i0, lA), B=(i0, lB), C=(iC, lA), W_fast=WA - WC, W_slow=Wc2 - Wc1)


def magnet_torque(theta, kind):
    """두 자석 (sinθ) 또는 자석 + 자성체 (sin2θ, 릴럭턴스) 의 토크–각도 특성 (단위값, θ = 회전자가 고정자 자계에서 뒤진 각)."""
    th = np.asarray(theta, dtype=float)
    return np.sin(th) if kind == "자석–자석" else 0.5 * np.sin(2 * th)


def cylinder_inertia(m, r, hollow=False, r_in=0.0):
    """원통(원판) J = ½ m r², 속이 빈 원통 J = ½ m (r² + r_in²), 얇은 링 J = m r²."""
    return 0.5 * m * (r * r + (r_in * r_in if hollow else 0.0))


# ---------------------------------------------------------------- 1.2.3 릴럭턴스 토크 (단일 여자 회전 기기)
def reluctance_torque(t, Im, ws, wm, delta, L2):
    """L(θ) = L0 + L2·cos2θ, i = Im·cos(ωs t), θ = ωm t − δ 일 때 순시 토크 T = ½ i² dL/dθ = −i² L2 sin2θ."""
    i = Im * np.cos(ws * t)
    th = wm * t - delta
    return -(i ** 2) * L2 * np.sin(2 * th)


def reluctance_avg(Im, ws, wm, delta, L2, cycles=200):
    T = 2 * math.pi / ws * cycles
    t = np.linspace(0, T, 40000 * max(1, cycles // 50), endpoint=False)
    return float(np.mean(reluctance_torque(t, Im, ws, wm, delta, L2)))


def reluctance_avg_sync(Im, L2, delta):
    """ωm = ωs 일 때 평균 토크 해석해: (Im² L2 / 4)·sin2δ  (i² = Im²(1 + cos2ωt)/2 와 sin(2ωt − 2δ) 의 곱의 평균)."""
    return 0.25 * Im * Im * L2 * math.sin(2 * delta)


# ---------------------------------------------------------------- 1.2.3 이중 여자 (원통형) 기기
def double_excited_torque(t, Is, Ir, M, ws, wr, wm, theta0=0.0, phi=0.0):
    """원통형 기기: T = −is·ir·M·sinθ,  is = Is cos(ωs t), ir = Ir cos(ωr t + φ), θ = ωm t + θ0."""
    return -(Is * np.cos(ws * t)) * (Ir * np.cos(wr * t + phi)) * M * np.sin(wm * t + theta0)


def double_excited_avg(Is, Ir, M, ws, wr, wm, theta0=0.0, phi=0.0, T=20.0, n=200000):
    t = np.linspace(0, T, n, endpoint=False)
    return float(np.mean(double_excited_torque(t, Is, Ir, M, ws, wr, wm, theta0, phi)))


MACHINES = {
    "직류 전동기": "고정자 직류(ωs = 0), 회전자 교류: 정류자가 회전자 전류 주파수를 ωr = ωm 으로 맞춰 줌",
    "동기 전동기": "고정자 교류 ωs, 회전자 직류(ωr = 0): 회전자가 ωm = ωs (동기 속도)로 돌아야 함",
    "유도 전동기": "고정자 교류 ωs, 회전자 교류 ωr = ωs − ωm (슬립 주파수): 저절로 만족됨",
}


# ---------------------------------------------------------------- 1.3 부하 시스템
LOADS = ("일정 토크 부하 (크레인·컨베이어)", "일정 출력 부하 (압연기·권취기)", "속도 제곱 부하 (팬·펌프·송풍기)")


def load_torque(kind, w, T0, w_ref):
    """부하 토크 [N·m]. T0 = 기준 속도 w_ref 에서의 토크. 일정 출력 부하는 저속에서 T0·3 으로 제한."""
    w = np.asarray(w, dtype=float)
    wa = np.abs(w)
    if kind.startswith("일정 토크"):
        T = np.full_like(wa, T0)
    elif kind.startswith("일정 출력"):
        T = np.minimum(T0 * w_ref / np.maximum(wa, 1e-9), 3 * T0)
    else:
        T = T0 * (wa / w_ref) ** 2
    return T * np.sign(np.where(w == 0, 1, w))


def dc_motor_torque(w, V, K, Ra):
    """타여자 DC 전동기 정상상태 토크: T = K(V − Kω)/Ra."""
    return K * (V - K * np.asarray(w, dtype=float)) / Ra


def operating_point(kind, V, K, Ra, T0, w_ref, B=0.0):
    """전동기 곡선과 부하 곡선의 교점 ω [rad/s] (이분법)."""
    f = lambda w: dc_motor_torque(w, V, K, Ra) - load_torque(kind, w, T0, w_ref) - B * w
    lo, hi = 1e-6, V / K
    if f(lo) < 0:
        return 0.0
    for _ in range(100):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if f(m) > 0 else (lo, m)
    return 0.5 * (lo + hi)


def startup(kind, V, K, Ra, T0, w_ref, J, B=0.0, t_end=None, n=4000):
    """정지에서 기동: J dω/dt = Tm(ω) − TL(ω) − Bω (전기 시정수 무시). (t, ω, Tm, TL) 반환."""
    w_op = operating_point(kind, V, K, Ra, T0, w_ref, B)
    tau = J * Ra / (K * K)
    t_end = t_end or max(6 * tau, 1e-3)
    t = np.linspace(0, t_end, n)
    h = t[1] - t[0]
    w = np.zeros(n)
    for k in range(n - 1):
        def acc(x):
            TL = 0.0 if abs(x) < 1e-9 and kind.startswith("일정 토크") and dc_motor_torque(0, V, K, Ra) < T0 else load_torque(kind, x, T0, w_ref)
            return (dc_motor_torque(x, V, K, Ra) - TL - B * x) / J
        k1 = acc(w[k]); k2 = acc(w[k] + h / 2 * k1); k3 = acc(w[k] + h / 2 * k2); k4 = acc(w[k] + h * k3)
        w[k + 1] = max(0.0, w[k] + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4))
    return t, w, dc_motor_torque(w, V, K, Ra), load_torque(kind, w, T0, w_ref), w_op


def reflect_gear(Jm, JL, Bm, BL, TL, n_ratio, eff=1.0):
    """기어비 n = ωm/ωL (감속) 일 때 전동기 축에서 본 등가 값: J = Jm + JL/n², B = Bm + BL/n², TL' = TL/(n·η)."""
    return Jm + JL / n_ratio ** 2, Bm + BL / n_ratio ** 2, TL / (n_ratio * eff)


def reflect_linear(m, r):
    """반지름 r 의 드럼·바퀴로 직선 운동하는 질량 m 의 등가 관성 J = m r²."""
    return m * r * r


# ---------------------------------------------------------------- 1.3.3 4상한 운전 (엘리베이터)
def elevator(m_car, m_load, m_cw, v, r, gear=1.0):
    """엘리베이터: 카(빈 카 + 승객) 와 균형추. v > 0 = 상승. 마찰·가속 무시.
    반환: 전동기 토크 T [N·m], 각속도 ω [rad/s], 전력 P [W], 상한 번호 1~4."""
    F = (m_car + m_load - m_cw) * G          # 카 쪽이 무거우면 > 0 (전동기가 끌어올리는 방향)
    T = F * r / gear
    w = v / r * gear
    P = T * w
    if w >= 0:
        q = 1 if T >= 0 else 2
    else:
        q = 3 if T <= 0 else 4
    return T, w, P, q
