"""BLDC 모델 검증: 평균 모델 해석해, 3상 시뮬레이션, 홀 센서 정류 순서, JS 엔진 일치."""
import json
import math
import pathlib
import shutil
import subprocess
from dataclasses import replace

import numpy as np
import pytest

from motors import registry
from motors.bldc.model import BLDCInputs, COMMUTATION, hall_code, trap

M = registry.get("bldc")


def make(**over):
    p = M.default_params()
    p.update(over)
    return M(p)


def test_trapezoid_shape():
    deg = np.deg2rad
    assert trap(deg(90)) == 1.0 and trap(deg(270)) == -1.0
    assert trap(deg(0)) == pytest.approx(0) and trap(deg(15)) == pytest.approx(0.5)
    assert trap(deg(150)) == pytest.approx(1.0) and trap(deg(180)) == pytest.approx(0.0)


def test_hall_sequence_and_commutation_table():
    codes = [hall_code(np.deg2rad(60 + 60 * k)) for k in range(6)]
    assert codes == [4, 6, 2, 3, 1, 5]            # 전기각이 늘면 6스텝 순서대로
    for c in codes:                                 # 각 단계에서 + 상은 역기전력 평탄부 +1, − 상은 −1
        H, L = COMMUTATION[c]
        th = np.deg2rad(60 + 60 * codes.index(c))
        shift = [0, 2 * np.pi / 3, -2 * np.pi / 3]
        assert trap(th - shift[H]) == pytest.approx(1.0)
        assert trap(th - shift[L]) == pytest.approx(-1.0)


def test_average_model_analytic():
    m = make(B=0.0)
    op = m.steady_state()
    K, R, V, TL = 2 * m.p["ke"], m.p["R"], m.p["Vdc"], m.p["TL"]
    assert op.I == pytest.approx(TL / K)
    assert op.omega == pytest.approx((V - 2 * R * TL / K) / K)
    assert op.P_in == pytest.approx(op.P_out + sum(op.losses.values()))


def test_three_phase_sim_matches_average_model_and_load():
    m = make()
    u = m.default_inputs()
    r = m.simulate_fixed(u, 0.25, record_dt=2e-5)
    k = r["t"] > 0.2
    assert np.max(np.abs(r["ia"] + r["ib"] + r["ic"])) < 1e-9
    assert np.mean(r["Te"][k]) == pytest.approx(u.TL + m.p["B"] * np.mean(r["omega"][k]), rel=0.03)
    assert np.mean(r["omega"][k]) == pytest.approx(m.steady_state(u).omega, rel=0.05)


def test_larger_inductance_lowers_speed_below_average_model():
    small = make(L=0.2e-3).simulate_fixed(make().default_inputs(), 0.2, record_dt=1e-4)["omega"][-1]
    big = make(L=1.0e-3).simulate_fixed(make().default_inputs(), 0.2, record_dt=1e-4)["omega"][-1]
    assert big < small < make().steady_state().omega


def test_starting_current_is_vdc_over_2r():
    m = make(L=2e-6, J=10.0)       # 인덕턴스 아주 작게, 관성 아주 크게 → 정지 전류
    r = m.simulate_fixed(m.default_inputs(), 2e-4, h=2e-7, record_dt=2e-7)
    # θ = 0 에서 출발하면 홀 코드 101 → C 상 (+), B 상 (−) 통전
    ipk = np.max(np.abs([r["ia"], r["ib"], r["ic"]]))
    assert ipk == pytest.approx(m.p["Vdc"] / (2 * m.p["R"]), rel=0.02)
    assert np.max(np.abs(r["ia"])) < 1e-9


def test_negative_duty_reverses():
    m = make()
    r = m.simulate_fixed(BLDCInputs(duty=-0.8, TL=0.1, friction=True), 0.2, record_dt=1e-4)
    assert r["omega"][-1] < -100


JS = pathlib.Path(__file__).resolve().parents[1] / "ui" / "realtime" / "bldc_engine.js"
node = shutil.which("node")


@pytest.mark.skipif(node is None, reason="Node.js 없음")
def test_js_engine_matches_python():
    m = make()
    p = {k: m.p[k] for k in ["Vdc", "R", "L", "ke", "poles", "J", "B"]}
    script = f"""
const E = require({json.dumps(str(JS))});
const s = new E.BLDCSim({json.dumps(p)}); s.set({{duty: 0.9, TL: 0.2}});
const rec = []; for (let i = 0; i < 100; i++) {{ s.advance(1e-3, 1e-5); rec.push([s.t, s.x[3], s.x[0]]); }}
console.log(JSON.stringify(rec));"""
    rec = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True,
                                    check=True, timeout=60).stdout)
    r = m.simulate_fixed(BLDCInputs(duty=0.9, TL=0.2), 0.1, record_dt=1e-5)
    for t, w, ia in rec[9::10]:
        j = int(round(t / 1e-5))
        assert w == pytest.approx(r["omega"][j], rel=1e-6, abs=1e-6)
        assert ia == pytest.approx(r["ia"][j], rel=1e-6, abs=1e-6)


@pytest.mark.skipif(node is None, reason="Node.js 없음")
def test_js_cascade_tracks_speed_and_limits_current():
    m = make()
    p = {k: m.p[k] for k in ["Vdc", "R", "L", "ke", "poles", "J", "B"]}
    script = f"""
const E = require({json.dumps(str(JS))});
const g = E.recommendedGains({json.dumps(p)}, 3000, 150);
const c = new E.BLDCCascade({json.dumps(p)}, Object.assign({{Ts: 1e-4, h: 1e-5, wRef: 300, TL: 0.3, friction: true,
  Ilim: 20, aw: true, ff: true, openLoop: false}}, g));
let imax = 0; for (let i = 0; i < 300; i++) {{ c.advance(1e-3); imax = Math.max(imax, Math.abs(c.out().iT)); }}
console.log(JSON.stringify({{w: c.out().w, imax}}));"""
    o = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True,
                                  check=True, timeout=60).stdout)
    assert o["w"] == pytest.approx(300, abs=3)
    assert o["imax"] < 20 * 1.3       # 토크 전류는 정류 리플 때문에 제한값 근처에서 조금 출렁임
