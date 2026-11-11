"""2장 직류 전동기의 토크 제어: 정상상태·과도 특성, PI 전류·속도 제어기, IP 제어기, 초퍼(H-브리지) PWM."""
import math

import numpy as np

RPM = 60 / (2 * math.pi)

# 교재 2.9 절 시뮬레이션 대상: 140 V, 25 A, 3000 r/min 영구자석 직류 전동기.
# 교재의 m-file 값은 슬라이드에 없으므로, 정격과 "감쇠비 ζ = 0.37 (부족감쇠)" 를 만족하도록 정했습니다.
TEXTBOOK = dict(V=140.0, I=25.0, n=3000.0, Ra=0.5, La=5e-3, J=1.8e-3, B=1e-4)
TEXTBOOK["K"] = (TEXTBOOK["V"] - TEXTBOOK["Ra"] * TEXTBOOK["I"]) / (TEXTBOOK["n"] / RPM)


# ---------------------------------------------------------------- 2.3 정상상태
def speed_torque(T, V, K, Ra):
    """ω = V/K − Ra·T/K²  [rad/s]."""
    return V / K - Ra * np.asarray(T, dtype=float) / (K * K)


def capability(P, w_max_ratio=3.0, n=400):
    """능력 곡선: 정격 전류 한계에서 기저 속도 이하 = 일정 토크(자속 정격), 이상 = 약계자(일정 출력)."""
    K0, Ir, V, Ra = P["K"], P["I"], P["V"], P["Ra"]
    wb = (V - Ra * Ir) / K0
    w = np.linspace(1e-3, w_max_ratio * wb, n)
    K = np.where(w <= wb, K0, (V - Ra * Ir) / w)
    T = K * Ir
    Va = np.minimum(Ra * Ir + K * w, V)
    return dict(w=w, K=K, T=T, P=T * w, V=Va, I=np.full_like(w, Ir), wb=wb)


# ---------------------------------------------------------------- 2.4 과도 특성
def voltage_to_speed(P, La=None):
    """ω(s)/V(s) = K / (La J s² + (Ra J + La B) s + Ra B + K²). (분자, 분모, 극점, ζ, ωn, Tm, Ta)"""
    La = P["La"] if La is None else La
    K, Ra, J, B = P["K"], P["Ra"], P["J"], P["B"]
    den = np.array([La * J, Ra * J + La * B, Ra * B + K * K])
    if La == 0:
        den = den[1:]
    poles = np.roots(den)
    Tm, Ta = J * Ra / (K * K), La / Ra if Ra else 0.0
    if La > 0:
        wn = math.sqrt(den[2] / den[0]); zeta = den[1] / (2 * math.sqrt(den[0] * den[2]))
    else:
        wn, zeta = float("nan"), float("nan")
    return np.array([K]), den, poles, zeta, wn, Tm, Ta


def voltage_step(P, steps, t_end, La=None, h=None):
    """전기자 전압 계단 [(t, V), ...] 에 대한 ia, ω (RK4)."""
    La = P["La"] if La is None else La
    K, Ra, J, B = P["K"], P["Ra"], P["J"], P["B"]
    h = h or min(2e-5, (La / Ra if La else 1e-3) / 20)
    n = int(round(t_end / h)) + 1
    t = np.linspace(0, t_end, n); h = t[1] - t[0]
    ia, w = np.zeros(n), np.zeros(n)
    Vt = np.zeros(n)
    for k in range(n):
        Vt[k] = 0.0
        for (ts, V) in steps:
            if t[k] >= ts: Vt[k] = V
    x = np.zeros(2)
    for k in range(n - 1):
        V = Vt[k]
        if La == 0:          # 1차 근사: ia = (V − Kω)/Ra
            f = lambda s: np.array([0.0, (K * (V - K * s[1]) / Ra - B * s[1]) / J])
        else:
            f = lambda s: np.array([(V - Ra * s[0] - K * s[1]) / La, (K * s[0] - B * s[1]) / J])
        k1 = f(x); k2 = f(x + h / 2 * k1); k3 = f(x + h / 2 * k2); k4 = f(x + h * k3)
        x = x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        if La == 0: x[0] = (V - K * x[1]) / Ra
        ia[k + 1], w[k + 1] = x
    if La == 0: ia[0] = Vt[0] / Ra
    return t, Vt, ia, w


# ---------------------------------------------------------------- 2.5 제어 기초 (P / I / PI) 와 주파수 응답
def current_gains(P, wcc):
    """극점-영점 상쇄: Kp = La·ωcc, Ki = Ra·ωcc."""
    return P["La"] * wcc, P["Ra"] * wcc


def speed_gains(P, wcs, zero_ratio=5.0):
    """속도 PI: Kp = J·ωcs / K, Ki = Kp·ωcs/zero_ratio (영점을 대역폭의 1/5 에)."""
    Kp = P["J"] * wcs / P["K"]
    return Kp, Kp * wcs / zero_ratio


def rl_controller_demo(P, kind, Kp, Ki, i_ref=20.0, t_end=0.02, h=2e-6):
    """회전자 정지(E = 0) 상태의 전기자 RL 회로를 P / I / PI 로 전류 제어."""
    La, Ra = P["La"], P["Ra"]
    n = int(round(t_end / h)) + 1
    t = np.linspace(0, t_end, n); h = t[1] - t[0]
    i, xi, out = 0.0, 0.0, np.zeros((n, 2))
    for k in range(n):
        e = i_ref - i
        kp = Kp if kind in ("P", "PI") else 0.0
        ki = Ki if kind in ("I", "PI") else 0.0
        v = kp * e + xi
        out[k] = (i, v)
        xi += ki * e * h
        i += h * (v - Ra * i) / La
    return t, out[:, 0], out[:, 1]


def loop_bode(P, Kp, Ki, w):
    """전류 제어 개루프 L(jω) = (Kp + Ki/jω) / (La jω + Ra) 의 크기[dB]·위상[°], 교차 주파수, 위상 여유."""
    s = 1j * np.asarray(w)
    Lj = (Kp + Ki / s) / (P["La"] * s + P["Ra"])
    mag = 20 * np.log10(np.abs(Lj)); ph = np.degrees(np.unwrap(np.angle(Lj)))
    idx = np.where(np.diff(np.sign(mag)) < 0)[0]
    if len(idx):
        k = idx[0]; wc = float(w[k]); pm = float(180 + ph[k])
    else:
        wc, pm = float("nan"), float("nan")
    return mag, ph, wc, pm


# ---------------------------------------------------------------- 2.6 / 2.7 전류·속도 제어 시뮬레이션
def simulate(P, t_end, h=1e-5, *, i_ref=None, w_ref=None, TL=None, fixed_speed=None,
             wcc=2 * math.pi * 500, wcs=2 * math.pi * 50, ff=True, Vlim=None, antiwindup=True,
             alpha=1.0, Ilim=None):
    """직류 전동기 + PI 전류 제어기 (+ 바깥 속도 제어기).
    i_ref / w_ref / TL: 시각 t → 값 함수. fixed_speed [rad/s]: 속도를 고정(전류 제어만 볼 때).
    alpha: 속도 제어기 지령 비례 비율 (1 = PI, 0 = IP, 사이 = 혼합)."""
    K, Ra, La, J, B = P["K"], P["Ra"], P["La"], P["J"], P["B"]
    Vlim = P["V"] if Vlim is None else Vlim
    Ilim = 2 * P["I"] if Ilim is None else Ilim
    Kpc, Kic = current_gains(P, wcc)
    Kps, Kis = speed_gains(P, wcs)
    n = int(round(t_end / h)) + 1
    t = np.linspace(0, t_end, n); h = t[1] - t[0]
    rec = np.zeros((n, 6))          # ia, ω, i*, v*, v (제한 후), ω*
    ia, w = 0.0, (fixed_speed or 0.0)
    xi, xw = 0.0, 0.0
    for k in range(n):
        tk = t[k]
        if w_ref is not None:
            wr = w_ref(tk)
            ew = wr - w
            istar_u = Kps * (alpha * wr - w) + xw
            istar = min(max(istar_u, -Ilim), Ilim)
            xw += h * (Kis * ew - (Kis / Kps) * (istar_u - istar) * (1 if antiwindup else 0))
        else:
            wr = float("nan")
            istar = i_ref(tk)
        e = istar - ia
        vu = Kpc * e + xi + (K * w if ff else 0.0)
        v = min(max(vu, -Vlim), Vlim)
        xi += h * Kic * (e - (1.0 / Kpc) * (vu - v) * (1 if antiwindup else 0))
        rec[k] = (ia, w, istar, vu, v, wr)
        # 플랜트 (전기 RK2, 기계 오일러로 충분: h ≪ 시정수)
        TLk = TL(tk) if TL else 0.0
        di = (v - Ra * ia - K * w) / La
        ia_mid = ia + 0.5 * h * di
        ia += h * (v - Ra * ia_mid - K * w) / La
        if fixed_speed is None:
            w += h * (K * ia - B * w - TLk) / J
    return dict(t=t, ia=rec[:, 0], w=rec[:, 1], istar=rec[:, 2], vstar=rec[:, 3], v=rec[:, 4], wref=rec[:, 5],
                gains=dict(Kpc=Kpc, Kic=Kic, Kps=Kps, Kis=Kis))


def step_metrics(t, y, y_final, t0=0.0):
    """오버슈트 [%], 상승 시간 10→90 % [s]."""
    m = t >= t0
    tt, yy = t[m], y[m]
    y0 = yy[0]; span = y_final - y0
    if abs(span) < 1e-12:
        return 0.0, float("nan")
    os_ = max(0.0, (np.max((yy - y0) / span) - 1) * 100)
    try:
        t10 = tt[np.argmax((yy - y0) / span >= 0.1)]; t90 = tt[np.argmax((yy - y0) / span >= 0.9)]
        tr = float(t90 - t10)
    except ValueError:
        tr = float("nan")
    return float(os_), tr


# ---------------------------------------------------------------- 2.8 초퍼 (1상한 / H-브리지 바이폴라·유니폴라)
def chopper_waveforms(mode, Vdc, va_ref, fsw, R, L, E, periods=4, pts=400):
    """초퍼 출력 전압과 전류 (평균 전압 지령 va_ref [V], 역기전력 E 는 일정).
    mode: "1상한", "바이폴라", "유니폴라". 처음 수십 주기를 돌려 정상상태로 만든 뒤 마지막 periods 주기를 돌려줌."""
    T = 1 / fsw
    h = T / pts
    warm = int(max(30, 6 * L / R / T)) if R > 0 else 30
    n_tot = (warm + periods) * pts
    m = va_ref / Vdc
    a = math.exp(-h * R / L)
    i = (va_ref - E) / R if R > 0 else 0.0
    keep0 = warm * pts
    out = np.zeros((periods * pts, 6))      # t, tri, Sa(or VH), Sb(or VL), va, ia
    for k in range(n_tot):
        tt = k * h
        ph = (tt / T) % 1.0
        tri = 4 * ph - 1 if ph < 0.5 else 3 - 4 * ph          # −1 … 1
        if mode == "1상한":
            tri01 = (tri + 1) / 2
            S1 = 1.0 if m > tri01 else 0.0
            S2 = 0.0
            v = Vdc if S1 else 0.0
            if not S1 and i <= 0:          # 불연속 전류: 다이오드도 꺼짐
                v = E
        elif mode == "바이폴라":
            S1 = 1.0 if m > tri else 0.0       # T1·T4 쌍
            S2 = 1.0 - S1                      # T2·T3 쌍
            v = Vdc if S1 else -Vdc
        else:                                  # 유니폴라
            S1 = 1.0 if m > tri else 0.0       # A 상 위 스위치 (VH)
            S2 = 1.0 if -m > tri else 0.0      # B 상 위 스위치 (VL)
            v = Vdc * (S1 - S2)
        iss = (v - E) / R
        i = iss + (i - iss) * a
        if mode == "1상한" and i < 0:
            i = 0.0
        if k >= keep0:
            out[k - keep0] = (tt - keep0 * h, tri, S1, S2, v, i)
    return dict(t=out[:, 0], tri=out[:, 1], S1=out[:, 2], S2=out[:, 3], v=out[:, 4], i=out[:, 5])
