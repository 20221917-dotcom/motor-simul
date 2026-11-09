"""유도전동기·PMSM 검증: 해석해/등가회로와 시뮬레이션 비교, JS 엔진 일치."""
import json
import math
import pathlib
import shutil
import subprocess
from dataclasses import replace

import numpy as np
import pytest

from core.simulate import simulate, Event
from motors import registry
from motors.ac.induction import IMInputs
from motors.ac.pmsm import GridInputs

IM = registry.get("induction")
PM = registry.get("pmsm")


def im(**over):
    p = IM.default_params(); p.update(over); return IM(p)


def pm(**over):
    p = PM.default_params(); p.update(over); return PM(p)


# ---------------- 유도전동기 ----------------
def test_im_dynamic_steady_state_matches_equivalent_circuit():
    m = im(); u = m.default_inputs()
    op = m.steady_state(u)
    r = simulate(m, replace(u, TL=0.0), 1.5, events=[Event(0.7, {"TL": u.TL})], n_points=3000, max_step=2e-4)
    assert r["rpm"][-1] == pytest.approx(op.rpm, rel=1e-4)
    assert r["Is"][-1] == pytest.approx(op.I1, rel=1e-3)
    assert r["Te"][-1] == pytest.approx(op.T, rel=1e-3)


def test_im_max_torque_formula_matches_numeric_maximum():
    m = im(); u = m.default_inputs()
    Tmax, smax = m.max_torque(u)
    s = np.linspace(1e-3, 1, 20001)
    T = m.torque(s, u)
    assert np.max(T) == pytest.approx(Tmax, rel=1e-4)
    assert s[np.argmax(T)] == pytest.approx(smax, rel=1e-3)


def test_im_power_balance_and_slip_relation():
    m = im(); op = m.steady_state()
    assert op.P_in == pytest.approx(op.P_out + sum(op.losses.values()), rel=1e-6)
    Pag = op.T * m.ws(m.default_inputs())
    assert op.losses["회전자 동손 (s·Pag)"] == pytest.approx(op.s * Pag)


def test_im_no_torque_at_synchronous_speed():
    m = im(); u = m.default_inputs()
    assert abs(float(m.torque(1e-9, u))) < 1e-3


def test_im_star_delta_start_reduces_starting_current_to_one_third():
    m = im(); u = m.default_inputs()
    I_d = abs(m._circuit(1.0, u)[2]) * math.sqrt(3)          # Δ 결선 선전류 (상전류의 √3 배)
    I_y = abs(m._circuit(1.0, replace(u, V=u.V / math.sqrt(3)))[2]) * math.sqrt(3)
    # 화면 모델은 상당 값으로 계산하므로 같은 결선에서 전압 1/√3 → 전류 1/√3, 토크 1/3
    assert I_y / I_d == pytest.approx(1 / math.sqrt(3), rel=1e-9)
    assert float(m.torque(1.0, replace(u, V=u.V / math.sqrt(3)))) == pytest.approx(float(m.torque(1.0, u)) / 3, rel=1e-9)


def test_im_rotor_resistance_shifts_slip_not_max_torque():
    u = im().default_inputs()
    T1, s1 = im().max_torque(u)
    T2, s2 = im(Rr=0.8).max_torque(u)
    assert T2 == pytest.approx(T1, rel=1e-9) and s2 == pytest.approx(2 * s1, rel=1e-9)


# ---------------- PMSM ----------------
def test_pmsm_mtpa_matches_brute_force():
    m = pm()
    for I in (5.0, 10.0, 15.0):
        b = np.linspace(0, math.pi / 2, 20001)
        T = m.torque(-I * np.sin(b), I * np.cos(b))
        j = int(np.argmax(T))
        id_, iq = m.mtpa(I)
        assert float(id_) == pytest.approx(-I * math.sin(b[j]), abs=2e-3)
        assert m.torque(id_, iq) == pytest.approx(T[j], rel=1e-6)


def test_pmsm_spm_mtpa_is_id_zero():
    m = pm(Lq=5e-3)        # Ld = Lq → 릴럭턴스 토크 없음
    id_, iq = m.mtpa(10.0)
    assert float(id_) == pytest.approx(0.0, abs=1e-9) and float(iq) == pytest.approx(10.0)


def test_pmsm_base_speed_touches_voltage_limit():
    m = pm()
    id_, iq = m.mtpa(m.p["Imax"])
    assert m.voltage_mag(id_, iq, m.base_speed()) == pytest.approx(m.Vmax, rel=1e-6)


def test_pmsm_field_weakening_extends_torque_beyond_base_speed():
    m = pm(); wb = m.base_speed()
    T_hi = m.max_torque_at_speed(1.5 * wb)
    assert T_hi[0] > 0 and T_hi[1] < m.mtpa(m.p["Imax"])[0]      # id 가 MTPA 보다 더 음수


def test_pmsm_grid_start_from_standstill_fails():
    m = pm(); u = m.default_inputs()
    r = simulate(m, replace(u, TL=0.0), 0.5, n_points=4000, max_step=2e-4)
    ns = 120 * u.f / m.p["poles"]
    assert abs(np.mean(r["rpm"][r.t > 0.3])) < 0.2 * ns


def _sync_x0(m, u):
    we = 2 * math.pi * u.f
    id0 = (math.sqrt(2 / 3) * u.V / we - m.p["lam"]) / m.p["Ld"]
    return (id0, 0.0, we / m.pp, -math.pi / 2 / m.pp, 0.0)


def test_pmsm_without_damper_hunts_and_with_damper_line_starts():
    m = pm(); u = m.default_inputs()
    ns = 120 * u.f / m.p["poles"]
    r0 = simulate(m, replace(u, TL=0.0, Kd=0.0), 1.0, x0=_sync_x0(m, u), n_points=3000, max_step=2e-4)
    assert np.ptp(r0["rpm"][r0.t > 0.8]) > 3 * np.ptp(r0["rpm"][r0.t < 0.2])        # 흔들림이 커짐 (난조)
    r1 = simulate(m, replace(u, TL=0.0, Kd=0.2), 2.0, n_points=4000, max_step=2e-4)  # 정지에서 라인 기동
    assert np.mean(r1["rpm"][r1.t > 1.6]) == pytest.approx(ns, rel=1e-3)


def test_pmsm_pullout_static_value_matches_simulation():
    m = pm(B=0.0); u = m.default_inputs()
    Tpo, dpo = m.pullout_torque(u)
    # 정상상태 운전점: 부하를 아주 천천히 올리면 탈조 토크 직전까지 동기 유지
    from motors.ac.pmsm import GridInputs  # noqa: F401
    ns = 120 * u.f / m.p["poles"]
    for ratio, keep in ((0.9, True), (1.1, False)):
        evs = [Event(0.1 + 0.1 * k, {"TL": ratio * Tpo * (k + 1) / 20}) for k in range(20)]
        r = simulate(m, replace(u, TL=0.0, Kd=0.2), 3.5, x0=_sync_x0(m, u), events=evs, n_points=8000, max_step=2e-4)
        synced = abs(np.mean(r["rpm"][r.t > 3.0]) - ns) < 0.01 * ns
        assert synced == keep, (ratio, np.mean(r["rpm"][r.t > 3.0]))


# ---------------- JS 엔진 ----------------
JS = pathlib.Path(__file__).resolve().parents[1] / "ui" / "realtime" / "ac_engine.js"
node = shutil.which("node")


def js(script):
    return json.loads(subprocess.run([node, "-e", f"const E = require({json.dumps(str(JS))});\n" + script],
                                     capture_output=True, text=True, check=True, timeout=120).stdout)


@pytest.mark.skipif(node is None, reason="Node.js 없음")
def test_js_im_grid_matches_python():
    m = im(); u = m.default_inputs()
    p = {k: m.p[k] for k in ["V", "f", "Rs", "Rr", "Lls", "Llr", "Lm", "poles", "J", "B"]}
    o = js(f"""const s = new E.IMSim({json.dumps(p)}); s.set({{TL: 0}});
for (let i = 0; i < 15000; i++) {{ s.step(1e-4); if (i === 7000) s.set({{TL: {u.TL}}}); }}
console.log(JSON.stringify(s.out()));""")
    op = m.steady_state(u)
    assert o["w"] == pytest.approx(op.omega, rel=1e-4)
    assert o["Is"] == pytest.approx(op.I1, rel=1e-3)


@pytest.mark.skipif(node is None, reason="Node.js 없음")
@pytest.mark.parametrize("mode,slip", [("vf", True), ("foc", False)])
def test_js_im_drives_reach_speed_under_load(mode, slip):
    m = im()
    p = {k: m.p[k] for k in ["V", "f", "Rs", "Rr", "Lls", "Llr", "Lm", "poles", "J", "B"]}
    o = js(f"""const P = {json.dumps(p)}, idr = E.imIdRated(P), g = E.imGains(P, 1500, 30, idr);
const d = new E.IMDrive(P, Object.assign({{ mode: "{mode}", slipComp: {str(slip).lower()}, Ts: 1e-4, h: 5e-5, wRef: 1500 / 9.5493,
  TL: 0, friction: true, ramp: 60, boost: 10, idRated: idr, Ilim: 40, aw: true, ff: true, fieldWeak: true }}, g));
for (let i = 0; i < 800; i++) {{ d.advance(0.005); if (i === 300) d.set({{ TL: 30 }}); }}
console.log(JSON.stringify(d.out()));""")
    assert o["w"] * 9.5493 == pytest.approx(1500, abs=3)
    assert o["Te"] == pytest.approx(30 + 0.002 * o["w"], rel=0.02)


@pytest.mark.skipif(node is None, reason="Node.js 없음")
@pytest.mark.parametrize("mode,reach", [("id0", False), ("fw", True)])
def test_js_pmsm_field_weakening_needed_above_base_speed(mode, reach):
    m = pm()
    p = {k: m.p[k] for k in ["Vdc", "Rs", "Ld", "Lq", "lam", "poles", "J", "B"]}
    n_ref = 1.5 * m.base_speed() * 9.5493
    o = js(f"""const P = {json.dumps(p)}, g = E.pmsmGains(P, 2000, 100);
const d = new E.PMSMDrive(P, Object.assign({{ mode: "{mode}", Ts: 1e-4, h: 2e-5, wRef: {n_ref} / 9.5493, TL: 1, friction: true,
  Imax: 15, aw: true, ff: true, Kfw: 200 }}, g));
for (let i = 0; i < 300; i++) d.advance(0.005);
console.log(JSON.stringify(d.out()));""")
    reached = abs(o["w"] * 9.5493 - n_ref) < 0.01 * n_ref
    assert reached == reach
    assert o["vmag"] <= o["Vmax"] * 1.0001
