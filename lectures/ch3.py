"""3장 BLDC 전동기: 사다리꼴 역기전력, 홀 센서 6스텝(120° 통전), 상전환 토크 리플, PWM 기법, 센서리스(ZCP).

스위칭 단위 모델: 3상 Y 결선(중성점 n 떠 있음) + 3상 인버터(스위치마다 역병렬 다이오드).
각 레그 단자 전압 vx 는 위 스위치 켜짐 → Vdc, 아래 스위치 켜짐 → 0, 둘 다 꺼짐 → 전류 방향에 따라 다이오드가
도통(ix > 0 이면 아래 다이오드 → 0, ix < 0 이면 위 다이오드 → Vdc), 전류 0 이면 '개방(floating)' 이고 그 단자
전압은 ex + vn 입니다 (센서리스에서 역기전력을 읽는 곳). 상전류 ix 는 전동기로 들어가는 방향이 +.
"""
import math

import numpy as np

RPM = 60 / (2 * math.pi)
PHASES = "abc"
SHIFT = (0.0, 2 * math.pi / 3, 4 * math.pi / 3)

DEFAULT = dict(Vdc=48.0, R=0.4, L=0.8e-3, ke=0.06, poles=8, fsw=10e3)   # ke: 상 역기전력 평탄부 = ke·ωm


def trap(x, flat_deg=120.0):
    """사다리꼴 단위 함수 (주기 2π, sin 과 같은 위상). 반주기 안에서 0 → 1 로 오르는 경사 구간 폭은 (180° − 평탄부)/2.
    평탄부 120° 이면 이상적인 BLDC (30°~150° 에서 +1), 180° 면 사각파, 0 이면 삼각파."""
    x = np.mod(np.asarray(x, dtype=float), 2 * math.pi)
    edge = max((math.pi - math.radians(flat_deg)) / 2, 1e-9)
    y = np.clip(np.minimum(x, math.pi - x) / edge, 0, 1)          # 0 ~ π 구간
    yn = -np.clip(np.minimum(x - math.pi, 2 * math.pi - x) / edge, 0, 1)
    return np.where(x < math.pi, y, yn)


def emf_shape(theta_e, kind="사다리꼴", flat_deg=120.0):
    if kind == "정현파":
        return np.sin(theta_e)
    return trap(theta_e, flat_deg)


def current_shape(theta_e, kind="120° 사각파"):
    """상전류 모양 (진폭 1): 120° 사각파 = BLDC 6스텝, 정현파 = PMSM 벡터 제어."""
    if kind == "정현파":
        return np.sin(theta_e)
    x = np.mod(theta_e, 2 * math.pi)
    return np.where((x >= math.pi / 6) & (x < 5 * math.pi / 6), 1.0, np.where((x >= 7 * math.pi / 6) & (x < 11 * math.pi / 6), -1.0, 0.0))


def torque_from_shapes(emf_kind, cur_kind, flat_deg=120.0, n=1441):
    """3상 Σ e·i (단위값). 반환 θe, 상별 e, i, 합 토크."""
    th = (np.arange(n) + 0.5) / n * 2 * math.pi          # 전환 순간(경계)을 피해 구간 가운데에서 샘플
    e = [emf_shape(th - s, emf_kind, flat_deg) for s in SHIFT]
    i = [current_shape(th - s, cur_kind) for s in SHIFT]
    T = sum(ex * ix for ex, ix in zip(e, i))
    return th, e, i, T


# ---------------------------------------------------------------- 3.2 홀 센서와 6스텝
def hall(theta_e, offset=0.0):
    """홀 센서 H1·H2·H3 (0/1). 각 센서는 해당 상 역기전력의 +반주기(0~180°)에서 1."""
    th = np.asarray(theta_e, dtype=float) - offset
    return [((np.mod(th - s, 2 * math.pi)) < math.pi).astype(int) for s in SHIFT]


def sector(theta_e, offset=0.0):
    """0~5 구간 (30°, 90°, … 경계). 구간마다 (+ 상, − 상, 개방 상) 을 정함."""
    return int(np.floor(np.mod(theta_e - offset - math.pi / 6, 2 * math.pi) / (math.pi / 3))) % 6


# 구간 k (θe = 30°+60°k ~ 90°+60°k) 에서 위 스위치 켜는 상, 아래 스위치 켜는 상
STEP_TABLE = [("a", "b"), ("a", "c"), ("b", "c"), ("b", "a"), ("c", "a"), ("c", "b")]


def step_info(k):
    hi, lo = STEP_TABLE[k]
    fl = [p for p in PHASES if p not in (hi, lo)][0]
    return hi, lo, fl


# ---------------------------------------------------------------- 스위칭 시뮬레이션
PWM_METHODS = {
    "바이폴라 (대각 스위치 동시 PWM)": "bipolar",
    "유니폴라 H_PWM-L_ON (위 스위치만 PWM)": "hpwm",
    "유니폴라 H_ON-L_PWM (아래 스위치만 PWM)": "lpwm",
    "유니폴라 PWM_ON (통전 앞 60° PWM, 뒤 60° ON)": "pwm_on",
    "유니폴라 ON_PWM (통전 앞 60° ON, 뒤 60° PWM)": "on_pwm",
}


def _gates(theta_e, pwm_on, method):
    """(위 스위치 3개, 아래 스위치 3개) 0/1."""
    k = sector(theta_e)
    hi, lo, _ = step_info(k)
    up = {p: 0 for p in PHASES}; dn = {p: 0 for p in PHASES}
    # 한 상의 120° 통전 구간 안에서 앞쪽 60° 인지
    first_half_hi = STEP_TABLE[(k - 1) % 6][0] != hi       # 직전 구간에 그 상이 위 스위치가 아니었으면 앞 60°
    first_half_lo = STEP_TABLE[(k - 1) % 6][1] != lo
    if method == "bipolar":
        if pwm_on:
            up[hi] = 1; dn[lo] = 1
        else:
            dn[hi] = 1; up[lo] = 1
    elif method == "hpwm":
        up[hi] = pwm_on; dn[lo] = 1
    elif method == "lpwm":
        up[hi] = 1; dn[lo] = pwm_on
    elif method == "pwm_on":
        up[hi] = pwm_on if first_half_hi else 1
        dn[lo] = pwm_on if first_half_lo else 1
    else:  # on_pwm
        up[hi] = 1 if first_half_hi else pwm_on
        dn[lo] = 1 if first_half_lo else pwm_on
    return up, dn


def _trap1(x, edge):
    """trap() 의 스칼라 버전 (시뮬레이션 안쪽 반복용)."""
    x = x % (2 * math.pi)
    if x < math.pi:
        return min(1.0, min(x, math.pi - x) / edge)
    return -min(1.0, min(x - math.pi, 2 * math.pi - x) / edge)


def _step(st, h, t, duty, method, P, edge, off):
    """스위칭 모델 한 걸음. st: dict(i, th, wm). 반환 기록용 값."""
    Vdc, R, L, ke, fsw = P["Vdc"], P["R"], P["L"], P["ke"], P["fsw"]
    i, th, wm = st["i"], st["th"], st["wm"]
    pwm_on = 1 if ((t * fsw) % 1.0) < duty else 0
    up, dn = _gates(th - off, pwm_on, method)
    e = [ke * wm * _trap1(th - sh, edge) for sh in SHIFT]
    v = [0.0, 0.0, 0.0]; known = [False, False, False]
    for j, p in enumerate(PHASES):
        if up[p]:
            v[j] = Vdc; known[j] = True
        elif dn[p]:
            known[j] = True
        elif i[j] > 1e-9:
            known[j] = True                    # 아래 다이오드 환류 (v = 0)
        elif i[j] < -1e-9:
            v[j] = Vdc; known[j] = True        # 위 다이오드 환류

    def vn_of():
        ks = [j for j in range(3) if known[j]]
        return sum(v[j] - R * i[j] - e[j] for j in ks) / len(ks) if len(ks) >= 2 else sum(e) / 3
    vn = vn_of()
    for j in range(3):                         # 개방 상 단자 전압이 0~Vdc 를 벗어나면 다이오드 도통
        if not known[j] and sum(known) >= 2:
            vf = e[j] + vn
            if vf > Vdc or vf < 0:
                v[j] = Vdc if vf > Vdc else 0.0; known[j] = True
                vn = vn_of()
    i_new = [i[j] + h * (v[j] - vn - R * i[j] - e[j]) / L if known[j] else 0.0 for j in range(3)]
    for j in range(3):                         # 환류 전류가 0 을 지나면 그 상은 개방
        p = PHASES[j]
        if known[j] and not (up[p] or dn[p]) and i[j] != 0.0 and i_new[j] * i[j] < 0:
            i_new[j] = 0.0; known[j] = False
    ks = [j for j in range(3) if known[j]]
    if 2 <= len(ks) < 3:
        r = sum(i_new) / len(ks)
        for j in ks:
            i_new[j] -= r                      # Σi = 0 유지
    st["i"] = i_new
    Te = (e[0] * i_new[0] + e[1] * i_new[1] + e[2] * i_new[2]) / max(wm, 1e-6) if wm > 1e-6 else \
        ke * sum(_trap1(th - sh, edge) * i_new[k] for k, sh in enumerate(SHIFT))
    if not all(known):
        vn = vn_of()                           # 개방 상태가 바뀌었을 수 있으므로 중성점 전압을 다시 계산
    for j in range(3):
        if not known[j]:
            v[j] = e[j] + vn
    return dict(pwm=pwm_on, up=up, dn=dn, e=e, v=v, vn=vn, Te=Te, known=known)


def simulate_bldc(rpm, duty, method="hpwm", P=None, cycles=3, show_cycles=1, flat_deg=120.0, hall_offset_deg=0.0,
                  steps_per_pwm=40, fixed_speed=True, J=1e-4, TL=0.0):
    """속도를 고정(기본)하거나 기계 방정식을 함께 풀어 상전류·단자 전압·토크·게이트 신호를 계산.
    마지막 show_cycles 전기 주기를 돌려줍니다."""
    P = dict(DEFAULT, **(P or {}))
    pp, fsw = P["poles"] / 2, P["fsw"]
    edge = max((math.pi - math.radians(flat_deg)) / 2, 1e-9)
    wm = rpm / RPM
    we = pp * max(wm, 1e-3)
    T_e = 2 * math.pi / we
    h = 1 / fsw / steps_per_pwm
    n = int(cycles * T_e / h)
    keep = int(show_cycles * T_e / h)
    off = math.radians(hall_offset_deg)
    st = dict(i=[0.0, 0.0, 0.0], th=0.0, wm=wm)
    rec = np.zeros((keep, 24))
    for k in range(n):
        t = k * h
        o = _step(st, h, t, duty, method, P, edge, off)
        if not fixed_speed:
            st["wm"] += h * (o["Te"] - TL) / J
        st["th"] += pp * st["wm"] * h
        if k >= n - keep:
            r = k - (n - keep)
            rec[r] = (t, st["th"], *st["i"], *o["v"], o["vn"], *o["e"], o["Te"], o["pwm"], sector(st["th"] - off),
                      *[0.0 if q else 1.0 for q in o["known"]], *[o["up"][p] for p in PHASES], *[o["dn"][p] for p in PHASES])
    tt = rec[:, 0] - rec[0, 0]
    return dict(t=tt, th=rec[:, 1], i=rec[:, 2:5].T, v=rec[:, 5:8].T, vn=rec[:, 8], e=rec[:, 9:12].T, Te=rec[:, 12],
                pwm=rec[:, 13], sector=rec[:, 14], floating=rec[:, 15:18].T > 0.5, up=rec[:, 18:21].T, dn=rec[:, 21:24].T,
                P=P, wm=st["wm"])


def simulate_bldc_drive(rpm_ref, ctrl="전류 제어", method="hpwm", P=None, J=2e-4, TL=0.05, t_end=0.12, t_load=0.08,
                        wcs=2 * math.pi * 20, Imax=10.0, steps_per_pwm=20, rec_every=4):
    """정지에서 속도 지령으로 기동 (교재 3.4: 속도 PI → 듀티, 또는 속도 PI → 직류 전류 PI → 듀티).
    부하 TL 은 t_load 에 걸림."""
    P = dict(DEFAULT, **(P or {}))
    Vdc, R, L, ke, pp, fsw = P["Vdc"], P["R"], P["L"], P["ke"], P["poles"] / 2, P["fsw"]
    edge = (math.pi - math.radians(120)) / 2
    h = 1 / fsw / steps_per_pwm
    n = int(t_end / h)
    st = dict(i=[0.0, 0.0, 0.0], th=0.0, wm=0.0)
    kt = 2 * ke                                       # Te = 2·ke·I (두 상 통전)
    Kps = J * wcs / kt; Kis = Kps * wcs / 5            # 속도 PI → 전류 [A]
    wcc = 2 * math.pi * 500; Kpc = 2 * L * wcc; Kic = 2 * R * wcc
    xw = xi = 0.0; duty = 0.0
    wr = rpm_ref / RPM
    out = []
    for k in range(n):
        t = k * h
        if k % steps_per_pwm == 0:                    # PWM 주기마다 제어 계산
            Ts = 1 / fsw
            ew = wr - st["wm"]
            if ctrl == "전류 제어":
                iu = Kps * ew + xw; istar = min(max(iu, 0.0), Imax)
                xw += Ts * Kis * (ew - (iu - istar) / Kps)
                idc = 0.5 * sum(abs(x) for x in st["i"])
                ei = istar - idc
                vu = Kpc * ei + xi + 2 * ke * st["wm"]
                vv = min(max(vu, 0.0), Vdc)
                xi += Ts * Kic * (ei - (vu - vv) / Kpc)
            else:                                     # 속도 PI 출력 = 전압 지령 (전류 제한 없음)
                Kpv = Kps * Kpc / (2 * L)               # 전류 루프가 없으므로 비슷한 크기의 전압 이득을 바로 씀
                vu = Kpv * ew + xw
                vv = min(max(vu, 0.0), Vdc)
                if vu == vv:
                    xw += Ts * Kpv * wcs / 5 * ew       # 포화 중에는 적분 멈춤
                istar = float("nan")
            duty = vv / Vdc
        o = _step(st, h, t, duty, method, P, edge, 0.0)
        TLk = TL if t >= t_load else 0.0
        st["wm"] += h * (o["Te"] - TLk - 1e-5 * st["wm"]) / J
        st["wm"] = max(st["wm"], 0.0)
        st["th"] += pp * st["wm"] * h
        if k % rec_every == 0:
            out.append((t, st["wm"] * RPM, o["Te"], *st["i"], o["e"][0], duty, istar))
    a = np.array(out)
    return dict(t=a[:, 0], rpm=a[:, 1], Te=a[:, 2], i=a[:, 3:6].T, ea=a[:, 6], duty=a[:, 7], istar=a[:, 8], P=P)


def ripple_percent(x):
    m = np.mean(x)
    return float((np.max(x) - np.min(x)) / abs(m) * 100) if abs(m) > 1e-12 else float("nan")


def zero_crossings(sim, phase=0, window=None):
    """개방 구간의 단자 전압 vx 가 Vdc/2 (가상 중성점) 를 지나는 시각 (PWM 켜진 순간에만 비교)과 실제 역기전력 영점 시각."""
    t, v, e = sim["t"], sim["v"][phase], sim["e"][phase]
    Vh = sim["P"]["Vdc"] / 2
    th = sim["th"]
    fl = sim["floating"][phase]                       # 실제로 전류가 0 인 개방 구간만
    sample = fl & (sim["pwm"] > 0)
    det = []
    idx = np.where(sample)[0]
    for a, b in zip(idx[:-1], idx[1:]):
        if not fl[a:b + 1].all():      # 그 사이에 다이오드 환류 등으로 개방이 끊겼으면 다른 구간
            continue
        if (v[a] - Vh) * (v[b] - Vh) < 0:
            det.append(t[b])
    sec_fl = np.array([step_info(int(q))[2] == PHASES[phase] for q in sim["sector"]])
    true = [t[k + 1] for k in range(len(e) - 1) if e[k] * e[k + 1] < 0 and sec_fl[k]]
    return det, true
