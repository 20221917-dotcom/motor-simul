"""해석해와 시뮬레이션 비교 (타여자)."""
from dataclasses import replace
import numpy as np
import pytest

from core.simulate import simulate, Event
from motors import registry
from concepts.commutation import torque_waveforms


@pytest.fixture
def sep():
    M = registry.get("dc_separately")
    return M(M.default_params())


def kphi_of(m):
    u = m.default_inputs()
    return m.p["Laf"] * u.Vf / (m.p["Rf"] + u.Rfx)


def test_no_load_speed_equals_V_over_kphi(sep):
    sep.p["B"] = 0.0
    u = replace(sep.default_inputs(), TL=0.0)
    K = kphi_of(sep)
    op = sep.steady_state(u)
    assert op.omega == pytest.approx(u.V / K, rel=1e-6)
    res = simulate(sep, u, 1.5)
    assert res["omega"][-1] == pytest.approx(u.V / K, rel=1e-3)


def test_stall_current_equals_V_over_Ra(sep):
    # La 를 작게 하면 기동 직후(속도 ≈ 0) 전류가 V/Ra 에 도달
    sep.p["La"] = 1e-5
    u = sep.default_inputs()
    res = simulate(sep, u, 2e-4, n_points=400, max_step=1e-6)
    assert np.max(res["ia"]) == pytest.approx(u.V / sep.p["Ra"], rel=0.02)


def test_steady_current_equals_TL_over_kphi(sep):
    sep.p["B"] = 0.0
    u = sep.default_inputs()
    K = kphi_of(sep)
    op = sep.steady_state(u)
    assert op.ia == pytest.approx(u.TL / K, rel=1e-6)
    res = simulate(sep, replace(u, TL=0.0), 2.0, events=[Event(0.5, {"TL": u.TL})])
    assert res["ia"][-1] == pytest.approx(u.TL / K, rel=1e-3)


def test_steady_state_matches_simulation_with_friction(sep):
    u = sep.default_inputs()
    op = sep.steady_state(u)
    res = simulate(sep, u, 2.0)
    assert res["omega"][-1] == pytest.approx(op.omega, rel=1e-3)
    assert res["ia"][-1] == pytest.approx(op.ia, rel=1e-3)


def test_power_balance(sep):
    op = sep.steady_state()
    assert op.P_in == pytest.approx(op.P_out + sum(op.losses.values()), rel=1e-9)


def test_speed_torque_line_slope(sep):
    # 타여자: ω = V/Kφ − Ra/Kφ² · T
    u = sep.default_inputs()
    K = kphi_of(sep)
    te, w, _ = sep.speed_torque_curve(u, ia_max=40)
    np.testing.assert_allclose(w, u.V / K - sep.p["Ra"] / K ** 2 * te, rtol=1e-9)


def test_starting_resistor_limits_inrush(sep):
    u = sep.default_inputs()
    direct = simulate(sep, replace(u, TL=0.0), 0.3)
    rst = simulate(sep, replace(u, TL=0.0, Rst=5.0), 0.3)
    assert np.max(rst["ia"]) < 0.25 * np.max(direct["ia"])
    assert np.max(rst["ia"]) < u.V / (sep.p["Ra"] + 5.0)


def test_no_operating_point_when_load_exceeds_starting_torque(sep):
    u = sep.default_inputs()
    K = kphi_of(sep)
    T_start = K * u.V / sep.p["Ra"]
    assert sep.steady_state(replace(u, TL=1.1 * T_start)) is None


def test_field_weakening_raises_speed(sep):
    u = sep.default_inputs()
    w0 = sep.steady_state(u).omega
    w1 = sep.steady_state(sep.with_field_ratio(u, 0.7)).omega
    assert w1 > w0


def test_commutator_waveforms():
    th = np.linspace(0, 2 * np.pi, 20001)
    w = torque_waveforms(th, 8)
    assert abs(np.mean(w["no_comm"])) < 1e-3
    assert np.mean(w["single"]) == pytest.approx(2 / np.pi, rel=1e-3)
    assert np.mean(w["multi"]) == pytest.approx(2 / np.pi, rel=1e-3)
    assert np.ptp(w["multi"]) < 0.05 * np.ptp(w["single"])
