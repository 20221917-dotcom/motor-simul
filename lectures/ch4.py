"""4장 교류 전동기의 회전 원리: 회전자계, 유도 전동기 등가회로·특성·정수 측정·속도 제어·속도 영역, 동기 전동기."""
import math

import numpy as np

# 기본 유도 전동기 (유도전동기 시뮬레이터 기본값과 같은 값, 60 Hz 리액턴스로 표시)
IM = dict(V=380.0, f=60.0, P=4, Rs=0.5, Xls=2 * math.pi * 60 * 3.2e-3, Rr=0.4, Xlr=2 * math.pi * 60 * 3.2e-3,
          Xm=2 * math.pi * 60 * 106e-3, Rc=0.0, I_rated=13.0)


# ---------------------------------------------------------------- 4.1.2 회전자계 (기자력)
def mmf(phi, t, f=60.0, poles=2, Im=1.0, N=1.0, mode="평형 3상", unbalance=0.5):
    """공극 둘레 기계각 φ 에서의 상별 기자력과 합성 기자력 (진폭 N·Im 기준).
    mode: "평형 3상", "한 상 단선 (b상 끊김)", "불평형 (c상 크기 변경)", "단상 (a상만)"."""
    w = 2 * math.pi * f
    amps = [1.0, 1.0, 1.0]
    if mode.startswith("한 상"):
        # b 상이 끊기면 a·c 상에 같은 전류가 반대로 흐름 (선간 전압으로 운전)
        ia = Im * math.cos(w * t - math.pi / 6)
        cur = [ia, 0.0, -ia]
    else:
        if mode.startswith("불평형"):
            amps[2] = unbalance
        if mode.startswith("단상"):
            amps = [1.0, 0.0, 0.0]
        cur = [Im * amps[k] * math.cos(w * t - 2 * math.pi * k / 3) for k in range(3)]
    pp = poles / 2
    F = [N * cur[k] * np.cos(pp * phi - 2 * math.pi * k / 3) for k in range(3)]
    return F, F[0] + F[1] + F[2], cur


def sync_speed_rpm(f, poles):
    return 120 * f / poles


# ---------------------------------------------------------------- 4.1.3 등가회로
def im_circuit(s, M=None, V=None, f=None):
    """상당 등가회로 (Y 결선, 철손 Rc 는 자화 리액턴스와 병렬, Rc = 0 이면 무시).
    반환: dict(I1, I2, Im, Ic, pf, Pin, Pcu1, Pcore, Pag, Pcu2, Pmech, T, eta, n)"""
    M = dict(IM, **(M or {}))
    V = M["V"] if V is None else V
    f = M["f"] if f is None else f
    k = f / M["f"]                                   # 주파수가 바뀌면 리액턴스도 비례
    Xls, Xlr, Xm = M["Xls"] * k, M["Xlr"] * k, M["Xm"] * k
    s = np.asarray(s, dtype=float)
    s = np.where(np.abs(s) < 1e-9, 1e-9, s)
    Vph = V / math.sqrt(3)
    Zs = M["Rs"] + 1j * Xls
    Zr = M["Rr"] / s + 1j * Xlr
    Ym = 1 / (1j * Xm) + (1 / M["Rc"] if M["Rc"] > 0 else 0)
    Zp = 1 / (Ym + 1 / Zr)
    I1 = Vph / (Zs + Zp)
    E1 = I1 * Zp
    I2 = E1 / Zr
    Ic = E1 / M["Rc"] if M["Rc"] > 0 else 0 * E1
    ws = 2 * math.pi * f / (M["P"] / 2)
    Pag = 3 * np.abs(I2) ** 2 * M["Rr"] / s
    Pcu2 = s * Pag
    Pmech = (1 - s) * Pag
    Pin = 3 * np.real(Vph * np.conj(I1))
    Pcu1 = 3 * np.abs(I1) ** 2 * M["Rs"]
    Pcore = 3 * np.abs(Ic) ** 2 * M["Rc"] if M["Rc"] > 0 else 0 * Pin
    T = Pag / ws
    eta = np.where((Pin > 0) & (Pmech > 0), Pmech / np.where(Pin > 0, Pin, 1), np.nan)
    n = (1 - s) * 120 * f / M["P"]
    return dict(I1=I1, I2=I2, E1=E1, pf=np.cos(np.angle(I1)), Pin=Pin, Pcu1=Pcu1, Pcore=Pcore, Pag=Pag, Pcu2=Pcu2,
                Pmech=Pmech, T=T, eta=eta, n=n, ws=ws)


def max_torque(M=None, V=None, f=None):
    """테브난 등가로 최대 토크와 그 슬립 (Rc 무시)."""
    M = dict(IM, **(M or {}))
    V = M["V"] if V is None else V
    f = M["f"] if f is None else f
    k = f / M["f"]
    Zs = M["Rs"] + 1j * M["Xls"] * k
    Zm = 1j * M["Xm"] * k
    Vth = V / math.sqrt(3) * abs(Zm / (Zs + Zm))
    Zth = Zs * Zm / (Zs + Zm)
    R, X = Zth.real, Zth.imag + M["Xlr"] * k
    ws = 2 * math.pi * f / (M["P"] / 2)
    root = math.hypot(R, X)
    return 3 * Vth ** 2 / (2 * ws * (R + root)), M["Rr"] / root


def operating_points(M, load_T_of_n, V=None, f=None, n_s=2000):
    """토크-속도 곡선과 부하 곡선의 교점들 (속도 rpm, 안정 여부). 안정: 교점에서 d(Tm − TL)/dn < 0."""
    M = dict(IM, **(M or {}))
    f = M["f"] if f is None else f
    ns = 120 * f / M["P"]
    s = np.linspace(1.0, 1e-4, n_s)
    r = im_circuit(s, M, V, f)
    n = r["n"]
    d = r["T"] - load_T_of_n(n)
    pts = []
    for k in range(len(s) - 1):
        if d[k] == 0 or d[k] * d[k + 1] < 0:
            a = d[k] / (d[k] - d[k + 1])
            nk = n[k] + a * (n[k + 1] - n[k])
            pts.append((float(nk), bool(d[k + 1] < d[k])))
    return pts, ns


# ---------------------------------------------------------------- 2중 농형 (심구형) 회전자
def double_cage_torque(s, M=None, R_out=2.0, X_out=0.6, R_in=0.25, X_in=3.0):
    """2중 농형: 바깥 도체(고저항·저리액턴스) 와 안쪽 도체(저저항·고리액턴스) 가 병렬인 회전자 가지."""
    M = dict(IM, **(M or {}))
    s = np.asarray(s, dtype=float)
    Vph = M["V"] / math.sqrt(3)
    Zs = M["Rs"] + 1j * M["Xls"]
    Z1 = R_out / s + 1j * X_out
    Z2 = R_in / s + 1j * X_in
    Zr = 1j * M["Xlr"] * 0.5 + Z1 * Z2 / (Z1 + Z2)
    Zm = 1j * M["Xm"]
    I1 = Vph / (Zs + Zm * Zr / (Zm + Zr))
    I2 = I1 * Zm / (Zm + Zr)
    ws = 2 * math.pi * M["f"] / (M["P"] / 2)
    Req = np.real(Zr - 1j * M["Xlr"] * 0.5) * s       # 회전자 가지의 유효 저항(슬립 보정 전)
    return 3 * np.abs(I2) ** 2 * Req / s / ws, np.abs(I1)


# ---------------------------------------------------------------- 4.1.7 정수 측정 (저항·무부하·구속 시험)
def run_tests(M=None, s_noload=1e-4, I_block=None):
    """기준 전동기로 가상의 시험 결과를 만들어 냄 (측정값 = 이 값들이라고 생각)."""
    M = dict(IM, **(M or {}))
    I_block = I_block or M["I_rated"]
    R_ll = 2 * M["Rs"]                                   # Y 결선 두 단자 사이 직류 저항
    nl = im_circuit(s_noload, M)
    V_nl, I_nl, P_nl = M["V"], float(abs(nl["I1"])), float(nl["Pin"])
    # 구속 시험: 정격 전류가 흐르도록 전압을 낮춤 (주파수는 정격)
    I_unit = float(abs(im_circuit(1.0, M, V=1.0)["I1"]))
    V_bl = I_block / I_unit
    bl = im_circuit(1.0, M, V=V_bl)
    return dict(R_ll=R_ll, V_nl=V_nl, I_nl=I_nl, P_nl=P_nl, V_bl=float(V_bl), I_bl=float(abs(bl["I1"])), P_bl=float(bl["Pin"]))


def estimate_params(meas, f=60.0, split=0.5):
    """교재 방법: Rs = R_ll/2, 구속 시험 → Rs + Rr', Xls + Xlr' (분배 비 split), 무부하 시험 → Xls + Xm, 철손+기계손."""
    Rs = meas["R_ll"] / 2
    Zbl = meas["V_bl"] / math.sqrt(3) / meas["I_bl"]
    Rbl = meas["P_bl"] / (3 * meas["I_bl"] ** 2)
    Xbl = math.sqrt(max(Zbl ** 2 - Rbl ** 2, 0))
    Rr = Rbl - Rs
    Xls, Xlr = split * Xbl, (1 - split) * Xbl
    Znl = meas["V_nl"] / math.sqrt(3) / meas["I_nl"]
    Rnl = meas["P_nl"] / (3 * meas["I_nl"] ** 2)
    Xnl = math.sqrt(max(Znl ** 2 - Rnl ** 2, 0))
    Xm = Xnl - Xls
    P_loss = meas["P_nl"] - 3 * meas["I_nl"] ** 2 * Rs
    return dict(Rs=Rs, Rr=Rr, Xls=Xls, Xlr=Xlr, Xm=Xm, P_core_mech=P_loss)


# ---------------------------------------------------------------- 4.1.8 속도 제어 · 4.1.9 속도 영역
def speed_regions(M=None, n_max_ratio=3.0, npts=160, I_lim=None, f_base=None):
    """각 속도에서 전류 한계 I_lim 과 전압 한계(정격 전압) 안에서 낼 수 있는 최대 토크.
    기저 주파수 이하: V/f 일정, 이상: V = 정격. 반환 dict(n, T, P, V, I, f, slip_f, region)."""
    M = dict(IM, **(M or {}))
    I_lim = I_lim or M["I_rated"]
    f_base = f_base or M["f"]
    pp = M["P"] / 2
    ns_b = 120 * f_base / M["P"]
    n = np.linspace(ns_b * 0.02, ns_b * n_max_ratio, npts)
    out = {k: np.zeros(npts) for k in ("T", "V", "I", "f", "slip_f")}
    fr = np.linspace(0.05, 30.0, 600)                     # 슬립 주파수 후보 [Hz]
    for k, nk in enumerate(n):
        f = nk * pp / 60 + fr
        V = np.minimum(M["V"] * f / f_base, M["V"])
        s = fr / f
        best = (0.0, 0, 0, 0)
        for j in range(len(fr)):
            r = im_circuit(s[j], M, V[j], f[j])
            I1 = float(abs(r["I1"]))
            if I1 <= I_lim and r["T"] > best[0]:
                best = (float(r["T"]), V[j], I1, f[j], fr[j])
        T, Vb, Ib, fb, frb = best if len(best) == 5 else (0, 0, 0, 0, 0)
        out["T"][k], out["V"][k], out["I"][k], out["f"][k], out["slip_f"][k] = T, Vb, Ib, fb, frb
    out["n"] = n
    out["P"] = out["T"] * n / 60 * 2 * math.pi
    return out


# ---------------------------------------------------------------- 4.2 동기 전동기
def sync_phasor(Vs, Ef, delta, Xd, Xq=None):
    """동기 전동기 (전동기 기준, Rs 무시). Vs 기준 0°, 여자 전압 Ef 는 δ 만큼 뒤짐 (Ef∠−δ).
    원통형 (Xq = Xd):  Vs = Ef + jXs·I → I = (Vs − Ef)/(jXs).  돌극형: d·q 축으로 나눠 계산.
    반환 dict(I, pf, P, Q) — 3상 전력."""
    Xq = Xd if Xq is None else Xq
    Efp = Ef * complex(math.cos(-delta), math.sin(-delta))
    if abs(Xd - Xq) < 1e-12:
        I = (Vs - Efp) / (1j * Xd)
    else:
        # q축 = Ef 방향, d축 = q 에서 −90°. Vs 의 d, q 성분
        q = Efp / abs(Efp) if abs(Efp) > 0 else complex(math.cos(-delta), math.sin(-delta))
        d = q * complex(0, -1)
        Vd = (Vs * d.conjugate()).real; Vq = (Vs * q.conjugate()).real
        # 전동기: Vq = Ef + Xd·Id, Vd = −Xq·Iq (Rs = 0)
        Id = (Vq - Ef) / Xd
        Iq = -Vd / Xq
        I = Id * d + Iq * q
    S = 3 * Vs * I.conjugate()
    return dict(I=I, Ef=Efp, pf=math.cos(math.atan2(I.imag, I.real)), P=S.real, Q=S.imag)


def sync_torque(delta, Vs, Ef, Xd, Xq, ws):
    """T = (3/ωs)[Vs·Ef/Xd · sinδ + Vs²(Xd − Xq)/(2XdXq) · sin2δ]: 여자 토크 Tf, 릴럭턴스 토크 Tr."""
    delta = np.asarray(delta, dtype=float)
    Tf = 3 / ws * Vs * Ef / Xd * np.sin(delta)
    Tr = 3 / ws * Vs * Vs * (Xd - Xq) / (2 * Xd * Xq) * np.sin(2 * delta)
    return Tf, Tr


def v_curve(Vs, Xs, P_load, Ef_range):
    """원통형 동기 전동기의 V 곡선: 부하 P 일정에서 여자 전압(≈ 계자 전류)에 따른 전기자 전류.
    P = 3VsEf sinδ / Xs 에서 δ 를 구함. 탈조(δ > 90°) 이면 nan."""
    Ef = np.asarray(Ef_range, dtype=float)
    sd = P_load * Xs / (3 * Vs * Ef)
    I = np.full_like(Ef, np.nan); pf = np.full_like(Ef, np.nan)
    ok = np.abs(sd) <= 1
    for k in np.where(ok)[0]:
        r = sync_phasor(Vs, Ef[k], math.asin(sd[k]), Xs)
        I[k] = abs(r["I"]); pf[k] = r["pf"] * (1 if r["Q"] >= 0 else -1)   # Q > 0 이면 지상(부족여자)
    return I, pf
