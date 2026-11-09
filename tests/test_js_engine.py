"""브라우저 실시간 엔진(ui/realtime/engine.js)이 파이썬 모델과 같은 결과를 내는지 검증.
Node.js 가 없으면 건너뛴다."""
import json
import pathlib
import shutil
import subprocess

import pytest

from control.cascade import ControlConfig, run_cascade
from control.tuning import current_gains, speed_gains
from motors import registry

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "ui" / "realtime" / "engine.js"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="Node.js 없음")

CASES = [("dc_separately", {}), ("dc_shunt", {}), ("dc_series", {}),
         ("dc_compound", {"sigma": 1.0}), ("dc_compound", {"sigma": -1.0, "Ms": 0.003})]


def _run_js(script):
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True,
                         timeout=60)
    return json.loads(out.stdout)


@pytest.mark.parametrize("key,over", CASES)
def test_js_motor_matches_python_steady_state(key, over):
    M = registry.get(key)
    p = M.default_params()
    p.update(over)
    m = M(p)
    u = m.default_inputs()
    op = m.steady_state(u)
    jp = {k: p.get(k, 0.0) for k in ["Ra", "La", "Rf", "Lf", "Laf", "Rs", "Ls", "Ms", "J", "B"]}
    script = f"""
const E = require({json.dumps(str(ENGINE))});
const m = new E.Motor({json.dumps(jp)}, {json.dumps(m.excitation)}, {p.get('sigma', 1.0)});
const sim = new E.MotorSim(m, {{V:{u.V}, Vf:{u.Vf}, Rfx:{u.Rfx}, TL:{u.TL}, Rst:0, friction:false}});
for (let i = 0; i < 400; i++) sim.advance(0.01);
console.log(JSON.stringify(sim.out()));
"""
    o = _run_js(script)
    assert o["w"] == pytest.approx(op.omega, rel=1e-4)
    assert o["ia"] == pytest.approx(op.ia, rel=1e-4)


def test_js_cascade_matches_python():
    P = registry.get("dc_separately").default_params()
    K = P["Laf"] * P["Vf"] / P["Rf"]
    kpi, kii = current_gains(P["La"], P["Ra"], 1000)
    kpw, kiw = speed_gains(P["J"], K, 50)
    cfg = ControlConfig(t_end=1.0, refs=[(0.0, 100.0)], t_load=10.0, TL=0.0, I_lim=40.0,
                        Kp_w=kpw, Ki_w=kiw, Kp_i=kpi, Ki_i=kii)
    py = run_cascade(P, K, cfg)
    pc = {k: P[k] for k in ["Ra", "La", "J", "B", "V"]}
    c = dict(Ts=1e-4, quadrants=4, Ilim=40, aw=True, ff=True, wRef=100, TL=0, friction=True,
             openLoop=False, Kpw=kpw, Kiw=kiw, Kpi=kpi, Kii=kii)
    script = f"""
const E = require({json.dumps(str(ENGINE))});
const s = new E.CascadeSim({json.dumps(pc)}, {K}, {json.dumps(c)});
const rec = [];
for (let i = 0; i < 100; i++) {{ s.advance(0.01); rec.push([s.out().t, s.out().w, s.out().ia]); }}
console.log(JSON.stringify(rec));
"""
    rec = _run_js(script)
    import numpy as np
    for t, w, ia in rec[::10]:
        assert w == pytest.approx(float(np.interp(t, py["t"], py["omega"])), abs=0.2)
        assert ia == pytest.approx(float(np.interp(t, py["t"], py["ia"])), abs=0.5)
