"""속도 제어 시뮬레이션 검증."""
import numpy as np
import pytest

from control.cascade import ControlConfig, run_cascade
from control.pi import PI
from control.tuning import current_gains, speed_gains
from motors import registry

P = registry.get("dc_separately").default_params()
K = P["Laf"] * P["Vf"] / P["Rf"]


def cfg(**kw):
    kpi, kii = current_gains(P["La"], P["Ra"], 1000)
    kpw, kiw = speed_gains(P["J"], K, 50)
    base = dict(t_end=2.0, refs=[(0.0, 100.0)], t_load=1.0, TL=30.0, I_lim=40.0,
                Kp_w=kpw, Ki_w=kiw, Kp_i=kpi, Ki_i=kii)
    base.update(kw)
    return ControlConfig(**base)


def test_speed_tracks_reference_under_load():
    r = run_cascade(P, K, cfg())
    assert r["omega"][-1] == pytest.approx(100.0, abs=0.05)
    assert r["ia"][-1] == pytest.approx((30.0 + P["B"] * 100) / K, rel=1e-2)


def test_current_limit_respected():
    r = run_cascade(P, K, cfg())
    assert np.max(np.abs(r["ia"])) < 40.0 * 1.03


def test_reverse_in_4q_but_not_in_1q():
    c4 = cfg(refs=[(0.0, 100.0), (1.0, -80.0)], t_end=3.0, TL=10.0, t_load=0.5)
    r4 = run_cascade(P, K, c4)
    assert r4["omega"][-1] == pytest.approx(-80.0, abs=0.2)
    c1 = cfg(refs=[(0.0, 100.0), (1.0, -80.0)], t_end=3.0, TL=10.0, t_load=0.5,
             quadrants=1)
    r1 = run_cascade(P, K, c1)
    assert r1["omega"][-1] > -1.0          # 역회전 불가
    assert np.min(r1["ia"]) >= 0.0          # 전류 단방향


def test_open_loop_has_large_inrush_and_droop():
    r = run_cascade(P, K, cfg(), open_loop=True)
    assert np.max(r["ia"]) > 3 * 40.0
    assert r["omega"][-1] < 100.0 - 1.0     # 부하 시 속도 처짐


def test_anti_windup_reduces_overshoot():
    c_on = cfg(refs=[(0.0, 110.0)], TL=0.0, anti_windup=True)
    c_off = cfg(refs=[(0.0, 110.0)], TL=0.0, anti_windup=False)
    os_on = np.max(run_cascade(P, K, c_on)["omega"]) - 110.0
    os_off = np.max(run_cascade(P, K, c_off)["omega"]) - 110.0
    assert os_off > os_on + 1.0


def test_pi_clamping():
    pi = PI(1.0, 100.0, -1.0, 1.0, anti_windup=True)
    for _ in range(1000):
        u, _ = pi.step(10.0, 1e-3)
    assert u == 1.0 and pi.xi < 1.0
