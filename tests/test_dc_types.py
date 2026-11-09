"""분권·직권·복권 전동기 해석해 비교."""
from dataclasses import replace
import numpy as np
import pytest

from core.simulate import simulate, Event
from motors import registry


def make(key, **over):
    M = registry.get(key)
    p = M.default_params()
    p.update(over)
    return M(p)


ALL = ["dc_separately", "dc_shunt", "dc_series", "dc_compound"]


# ---- 분권 ----------------------------------------------------------------
def test_shunt_no_load_speed_and_line_current():
    m = make("dc_shunt", B=0.0)
    u = replace(m.default_inputs(), TL=0.0)
    K = m.p["Laf"] * u.V / m.p["Rf"]
    assert m.steady_state(u).omega == pytest.approx(u.V / K, rel=1e-6)
    op = m.steady_state()
    assert op.il == pytest.approx(op.ia + u.V / m.p["Rf"], rel=1e-9)
    assert op.ia == pytest.approx(m.p["TL"] / K, rel=1e-6)


def test_shunt_voltage_change_moves_field_too():
    # 분권은 전압을 낮추면 계자도 약해져서 속도 변화가 타여자보다 훨씬 작다
    sh, se = make("dc_shunt"), make("dc_separately")
    u_sh, u_se = sh.default_inputs(), se.default_inputs()
    d_sh = sh.steady_state(u_sh).omega - sh.steady_state(replace(u_sh, V=0.7 * u_sh.V)).omega
    d_se = se.steady_state(u_se).omega - se.steady_state(replace(u_se, V=0.7 * u_se.V)).omega
    assert abs(d_sh) < 0.2 * abs(d_se)


def test_shunt_field_resistor_raises_speed():
    m = make("dc_shunt")
    u = m.default_inputs()
    assert m.steady_state(replace(u, Rfx=60.0)).omega > m.steady_state(u).omega


# ---- 직권 ----------------------------------------------------------------
def test_series_torque_proportional_to_current_squared():
    m = make("dc_series")
    te, w, ia = m.speed_torque_curve(ia_max=60)
    np.testing.assert_allclose(te / ia ** 2, m.p["Ms"], rtol=1e-12)


def test_series_torque_square_law_in_simulation():
    m = make("dc_series")
    res = simulate(m, m.default_inputs(), 1.0)
    np.testing.assert_allclose(res["Te"], m.p["Ms"] * res["ia"] ** 2, rtol=1e-9)


def test_series_steady_state_matches_simulation():
    m = make("dc_series")
    u = m.default_inputs()
    op = m.steady_state(u)
    res = simulate(m, u, 3.0)
    assert res["omega"][-1] == pytest.approx(op.omega, rel=1e-3)
    assert res["ia"][-1] == pytest.approx(np.sqrt((u.TL + m.p["B"] * op.omega) / m.p["Ms"]),
                                          rel=1e-3)


def test_series_no_load_runaway():
    m = make("dc_series", B=0.0)
    assert m.no_load() is None                  # B = 0 이면 무부하 속도 무한대
    m2 = make("dc_series")
    assert m2.no_load().omega > 3 * m2.steady_state().omega
    # B > 0 일 때 무부하 해석해: Ms·Ia² = B·ω, ω = (V − R·Ia)/(Ms·Ia)
    nl = m2.no_load()
    assert m2.p["Ms"] * nl.ia ** 2 == pytest.approx(m2.p["B"] * nl.omega, rel=1e-6)


def test_series_stall_current():
    # 직권은 기동 토크가 매우 커서 금방 돌기 시작하므로 관성을 크게 해 회전자를 사실상 고정
    m = make("dc_series", La=1e-6, Ls=1e-6, J=1e4)
    u = m.default_inputs()
    res = simulate(m, u, 2e-4, n_points=400, max_step=1e-7)
    assert np.max(res["ia"]) == pytest.approx(u.V / (m.p["Ra"] + m.p["Rs"]), rel=0.02)


# ---- 복권 ----------------------------------------------------------------
def test_compound_kphi_sign():
    cum, dif = make("dc_compound", sigma=1.0), make("dc_compound", sigma=-1.0)
    u = cum.default_inputs()
    If = u.V / cum.p["Rf"]
    assert cum.kphi(10.0, If) == pytest.approx(cum.p["Laf"] * If + cum.p["Ms"] * 10)
    assert dif.kphi(10.0, If) == pytest.approx(dif.p["Laf"] * If - dif.p["Ms"] * 10)


def test_cumulative_compound_droops_more_than_shunt():
    cum, sh = make("dc_compound"), make("dc_shunt")
    drop = lambda m: m.no_load().omega - m.steady_state().omega
    assert drop(cum) > drop(sh)
    assert cum.steady_state().stable


def test_differential_compound_stability_condition():
    # Ms·ω > Ra + Rs 이면 전기적으로 불안정, 작으면 안정
    assert not make("dc_compound", sigma=-1.0, Ms=0.015).steady_state().stable
    assert make("dc_compound", sigma=-1.0, Ms=0.003).steady_state().stable


def test_compound_steady_state_matches_simulation():
    for sigma, Ms in ((1.0, 0.015), (-1.0, 0.003)):
        m = make("dc_compound", sigma=sigma, Ms=Ms)
        u = m.default_inputs()
        op = m.steady_state(u)
        res = simulate(m, replace(u, TL=0.0), 3.0, events=[Event(0.8, {"TL": u.TL})])
        assert res["omega"][-1] == pytest.approx(op.omega, rel=2e-3)


def test_differential_compound_starts_in_reverse():
    m = make("dc_compound", sigma=-1.0, Ms=0.015)
    res = simulate(m, replace(m.default_inputs(), TL=0.0), 0.3)
    assert np.min(res["omega"]) < 0


# ---- 공통 ----------------------------------------------------------------
@pytest.mark.parametrize("key", ALL)
def test_power_balance_all(key):
    op = make(key).steady_state()
    assert op.P_in == pytest.approx(op.P_out + sum(op.losses.values()), rel=1e-9)


@pytest.mark.parametrize("key", ALL)
def test_steady_state_matches_simulation_all(key):
    m = make(key)
    u = m.default_inputs()
    op = m.steady_state(u)
    res = simulate(m, u, 3.0)
    assert res["omega"][-1] == pytest.approx(op.omega, rel=2e-3)
