"""2장 직류 전동기의 토크 제어: 정상상태·과도 특성, PI 전류·속도 제어기, IP 제어기, 초퍼(H-브리지) PWM."""
import math

import numpy as np

RPM = 60 / (2 * math.pi)

# 교재 2.9 절 시뮬레이션 대상 (m-file 값): 140 V, 25 A, 3000 r/min, 3336 W, Ra = 0.26 Ω, La = 1.7 mH, J = 0.00252, B = 0
TEXTBOOK = dict(V=140.0, I=25.0, n=3000.0, P=3336.0, Ra=0.26, La=1.7e-3, J=0.00252, B=0.0)
TEXTBOOK["K"] = TEXTBOOK["P"] / (TEXTBOOK["n"] / RPM) / TEXTBOOK["I"]      # K = Te_rated / Ia_rated
# 교재 예제 2 (2.4 절): 5 kW, 125 V, 1800 r/min, Ra = 0.256 Ω, La = 1.7 mH, J = 0.00252, kφ = 0.6034
EXAMPLE2 = dict(V=125.0, I=43.96, n=1800.0, Ra=0.256, La=1.7e-3, J=0.00252, B=0.0, K=0.6034)


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
    """전기자 전압 계단 [(t, V), ...] 에 대한 ia, ω. 선형 시스템이므로 상태공간 해(lsim)로 한 번에 계산."""
    from scipy import signal
    La = P["La"] if La is None else La
    K, Ra, J, B = P["K"], P["Ra"], P["J"], P["B"]
    n = 4001
    t = np.linspace(0, t_end, n)
    Vt = np.zeros(n)
    for (ts, V) in steps:
        Vt[t >= ts] = V
    if La > 0:
        A = [[-Ra / La, -K / La], [K / J, -B / J]]
        sys = signal.StateSpace(A, [[1 / La], [0]], np.eye(2), [[0], [0]])
        _, _, x = signal.lsim(sys, Vt, t)
        ia, w = x[:, 0], x[:, 1]
    else:                                   # 1차 근사: ia = (V − Kω)/Ra
        sys = signal.StateSpace([[-(K * K / Ra + B) / J]], [[K / (Ra * J)]], [[1]], [[0]])
        _, w, _ = signal.lsim(sys, Vt, t)
        w = np.asarray(w).ravel()
        ia = (Vt - K * w) / Ra
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
    rec = np.zeros((n, 7))          # ia, ω, i*, v*, v (제한 후), ω*, 전류 적분기 값
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
        rec[k] = (ia, w, istar, vu, v, wr, xi)
        # 플랜트 (전기 RK2, 기계 오일러로 충분: h ≪ 시정수)
        TLk = TL(tk) if TL else 0.0
        di = (v - Ra * ia - K * w) / La
        ia_mid = ia + 0.5 * h * di
        ia += h * (v - Ra * ia_mid - K * w) / La
        if fixed_speed is None:
            w += h * (K * ia - B * w - TLk) / J
    return dict(t=t, ia=rec[:, 0], w=rec[:, 1], istar=rec[:, 2], vstar=rec[:, 3], v=rec[:, 4], wref=rec[:, 5], xi=rec[:, 6],
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


# ---------------------------------------------------------------- 2차 시스템·주파수 응답·안정도 (2.4, 2.5.2)
def second_order_step(sigma, wd, t):
    """극점 s = −σ ± jωd 인 2차 시스템 (DC 이득 1) 의 계단 응답. σ < 0 이면 불안정 (발산)."""
    from scipy import signal
    wn2 = sigma * sigma + wd * wd
    if wn2 < 1e-12:
        return np.zeros_like(t)
    sys = signal.lti([wn2], [1, 2 * sigma, wn2])
    _, y = signal.step(sys, T=t)
    return y


def zeta_step(zeta, wn, t):
    from scipy import signal
    _, y = signal.step(signal.lti([wn * wn], [1, 2 * zeta * wn, wn * wn]), T=t)
    return y


def generic_loop(K, a, b, w):
    """개루프 L(s) = K / (s (s/a + 1)(s/b + 1)) 의 보드 선도와 이득·위상 여유, 폐루프 계단 응답용 분모."""
    s = 1j * np.asarray(w)
    L = K / (s * (s / a + 1) * (s / b + 1))
    mag = 20 * np.log10(np.abs(L)); ph = np.degrees(np.unwrap(np.angle(L)))
    k = np.where(np.diff(np.sign(mag)) < 0)[0]
    wc = float(w[k[0]]) if len(k) else float("nan")
    pm = float(180 + np.interp(wc, w, ph)) if len(k) else float("nan")
    k2 = np.where(np.diff(np.sign(ph + 180)) < 0)[0]
    w180 = float(w[k2[0]]) if len(k2) else float("nan")
    gm = float(-np.interp(w180, w, mag)) if len(k2) else float("inf")
    num = [K]
    den = np.polyadd(np.polymul([1 / a, 1], np.polymul([1 / b, 1], [1, 0])), [K])
    return mag, ph, wc, pm, w180, gm, num, den


def closed_loop_step(num, den, t):
    from scipy import signal
    try:
        _, y = signal.step(signal.lti(num, den), T=t)
    except Exception:
        y = np.full_like(t, np.nan)
    return np.clip(y, -1e3, 1e3)


def pi_closed_bode(P, wcc, w):
    """전류 제어 폐루프 (극점-영점 상쇄) = ωcc / (s + ωcc): 크기 [dB], 위상 [°]."""
    G = wcc / (1j * np.asarray(w) + wcc)
    return 20 * np.log10(np.abs(G)), np.degrees(np.angle(G))


def speed_open_bode(P, wcs, wcc, w):
    """속도 제어 개루프 (Kp + Ki/s)·ωcc/(s + ωcc)·K/(Js)."""
    Kp, Ki = speed_gains(P, wcs)
    s = 1j * np.asarray(w)
    L = (Kp + Ki / s) * wcc / (s + wcc) * P["K"] / (P["J"] * s)
    return 20 * np.log10(np.abs(L)), np.degrees(np.unwrap(np.angle(L)))


def pi_speed_decomposition(P, wcs, t):
    """PI 속도 폐루프 (전류 제어 이상적) = ωn²/(s²+2ζωn s+ωn²) + 2ζωn s/(…) 로 나눈 두 성분의 계단 응답."""
    from scipy import signal
    Kp, Ki = speed_gains(P, wcs)
    a1, a0 = P["K"] * Kp / P["J"], P["K"] * Ki / P["J"]
    den = [1, a1, a0]
    _, y1 = signal.step(signal.lti([a0], den), T=t)          # ωn² 항
    _, y2 = signal.step(signal.lti([a1, 0], den), T=t)       # 영점 항 (오버슈트의 근원)
    wn = math.sqrt(a0); zeta = a1 / (2 * wn)
    return y1, y2, zeta, wn


# ---------------------------------------------------------------- 2.9.4 초퍼를 포함한 전체 구동 시스템
def simulate_chopper_drive(P, t_end=0.2, fsw=5000.0, mode="유니폴라", rpm_ref=2500.0, t_step=0.05,
                           wcs=2 * math.pi * 50, wcc=2 * math.pi * 500, TL=0.0, steps_per=100, rec_every=5):
    """속도 PI → 전류 PI (역기전력 보상, 누적 방지) → 초퍼 PWM (스위칭 그대로) → 직류 전동기."""
    K, Ra, La, J, B, V = P["K"], P["Ra"], P["La"], P["J"], P["B"], P["V"]
    Kpc, Kic = current_gains(P, wcc); Kps, Kis = speed_gains(P, wcs)
    Ilim = P["I"]
    h = 1 / fsw / steps_per
    n = int(t_end / h)
    ia = w = xi = xw = 0.0
    keep = []
    for k in range(n):
        t = k * h
        wr = rpm_ref / RPM if t >= t_step else 0.0
        iu = Kps * (wr - w) + xw; istar = min(max(iu, -Ilim), Ilim)
        xw += h * Kis * ((wr - w) - (iu - istar) / Kps)
        e = istar - ia
        vu = Kpc * e + xi + K * w; vref = min(max(vu, -V), V)
        xi += h * Kic * (e - (vu - vref) / Kpc)
        ph = (t * fsw) % 1.0; tri = 4 * ph - 1 if ph < 0.5 else 3 - 4 * ph
        m = vref / V
        if mode == "유니폴라":
            Sa = 1.0 if m > tri else 0.0; Sb = 1.0 if -m > tri else 0.0; va = V * (Sa - Sb)
        else:
            Sa = 1.0 if m > tri else 0.0; Sb = 1.0 - Sa; va = V if Sa else -V
        ia += h * (va - Ra * ia - K * w) / La
        w += h * (K * ia - B * w - TL) / J
        if k % rec_every == 0:
            keep.append((t, w, ia, K * ia, va, vref, Sa, Sb, tri, istar))
    a = np.array(keep)
    return dict(t=a[:, 0], w=a[:, 1], ia=a[:, 2], Te=a[:, 3], va=a[:, 4], vref=a[:, 5], Sa=a[:, 6], Sb=a[:, 7],
                tri=a[:, 8], istar=a[:, 9])


def chopper_ramp(mode, Vdc, fsw, periods=40, pts=200):
    """지령 Va* 를 +Vdc 에서 −Vdc 로 천천히 바꿀 때의 출력 전압 펄스 (교재 그림 2.60·2.61 아래쪽)."""
    T = 1 / fsw; h = T / pts
    n = periods * pts
    t = np.arange(n) * h
    m = 0.95 - 1.9 * t / t[-1]
    ph = (t / T) % 1.0
    tri = np.where(ph < 0.5, 4 * ph - 1, 3 - 4 * ph)
    if mode == "바이폴라":
        v = np.where(m > tri, Vdc, -Vdc)
    else:
        v = Vdc * ((m > tri).astype(float) - (-m > tri).astype(float))
    return t, m * Vdc, v
