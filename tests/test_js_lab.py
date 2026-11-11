"""강의 실습 브라우저 계산(ui/realtime/lab_ch*.js)이 파이썬 기준(lectures/ch*.py)과 같은 값을 내는지 확인."""
import json
import math
import pathlib
import shutil
import subprocess

import numpy as np
import pytest

from lectures import ch1, ch2, ch3, ch4

RT = pathlib.Path(__file__).resolve().parents[1] / "ui" / "realtime"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="Node.js 없음")

PRELUDE = "require({lab});\n".format(lab=json.dumps(str(RT / "lab.js"))) + "".join(
    f"const L{n} = require({json.dumps(str(RT / f'lab_ch{n}.js'))})._calc;\n" for n in (1, 2, 3, 4))


def js(expr):
    out = subprocess.run([node, "-e", PRELUDE + f"console.log(JSON.stringify({expr}));"],
                         capture_output=True, text=True, check=True, timeout=120)
    return json.loads(out.stdout)


def test_ch1_magnetics_and_operating_point():
    r = js("[L1.lambdaI(3, {g: 1e-3}), L1.opPoint('일정 토크', 100, 0.5, 1, 20, 150), L1.relAvg(5, 314.16, 314.16, 0.4, 0.02)]")
    assert r[0] == pytest.approx(ch1.lambda_i(3), rel=1e-6)
    assert r[1] == pytest.approx(ch1.operating_point("일정 토크", 100, 0.5, 1, 20, 150), rel=1e-6)
    assert r[2] == pytest.approx(ch1.reluctance_avg_sync(5, 0.02, 0.4), rel=0.02)


def test_ch2_textbook_motor_and_gains():
    P = dict(ch2.TEXTBOOK)
    r = js("(() => { const P = Object.assign({}, L2.TEXTBOOK); if (!P.K) P.K = P.P / (P.n * Math.PI / 30) / P.I; const v = L2.vToSpeed(P);"
           " return [v.zeta, v.wn, v.Tm, L2.currentGains(P, 2000), L2.speedGains(P, 200)]; })()")
    _, _, _, zeta, wn, Tm, _ = ch2.voltage_to_speed(P)
    assert r[0] == pytest.approx(zeta, rel=1e-6) and r[1] == pytest.approx(wn, rel=1e-6) and r[2] == pytest.approx(Tm, rel=1e-6)
    assert r[3] == pytest.approx(list(ch2.current_gains(P, 2000)), rel=1e-9)
    assert r[4] == pytest.approx(list(ch2.speed_gains(P, 200)), rel=1e-9)


def test_ch3_shapes_and_hall():
    th = np.linspace(0, 2 * math.pi, 37)[:-1] + 0.013
    r = js(f"(() => {{ const th = {json.dumps(th.tolist())}; return [th.map((x) => L3.trap(x, 100)), th.map((x) => L3.sector(x))]; }})()")
    assert r[0] == pytest.approx(ch3.trap(th, 100).tolist(), abs=1e-9)
    assert r[1] == [int(ch3.sector(x)) for x in th]


def test_ch4_induction_motor_matches_python():
    r = js("(() => { const c = L4.circuit(0.03), [Tm, sm] = L4.maxTorque(), e = L4.estimate(L4.runTests(), 0.4);"
           " return [c.T, c.I1.abs(), c.pf, c.eta, Tm, sm, L4.doubleCage(0.5, L4.IM, 2, 0.6, 0.3, 3), e, L4.deepBar(60, 25),"
           " L4.opPoints(L4.IM, () => 50).map((p) => p[0])]; })()")
    py = ch4.im_circuit(0.03)
    assert r[0] == pytest.approx(py["T"], rel=1e-9) and r[1] == pytest.approx(abs(py["I1"]), rel=1e-9)
    assert r[2] == pytest.approx(py["pf"], rel=1e-9) and r[3] == pytest.approx(float(py["eta"]), rel=1e-9)
    assert [r[4], r[5]] == pytest.approx(list(ch4.max_torque()), rel=1e-9)
    assert r[6] == pytest.approx([float(x) for x in ch4.double_cage_torque(0.5, ch4.IM, 2, 0.6, 0.3, 3)], rel=1e-9)
    est = ch4.estimate_params(ch4.run_tests(), split=0.4)
    for k in ("Rs", "Rr", "Xls", "Xlr", "Xm"):
        assert r[7][k] == pytest.approx(est[k], rel=1e-9), k
    assert r[8] == pytest.approx(ch4.deep_bar_ratio(60, 25), rel=1e-9)
    py_pts, _ = ch4.operating_points(ch4.IM, lambda n: 50.0 + 0 * n)
    assert sorted(r[9]) == pytest.approx(sorted(p[0] for p in py_pts), abs=3)


def test_ch4_synchronous_and_winding():
    r = js("(() => { const p = L4.syncPhasor(220, 260, 0.5, 6, 4), th = Array.from({length: 1440}, (_, k) => k / 1440 * 2 * Math.PI),"
           " w = L4.windingMMF(th, 3, '3상'); return [p.I.re, p.I.im, p.P, p.Q, w.kd, L4.syncTorque(0.7, 220, 260, 6, 4, 60 * Math.PI)]; })()")
    py = ch4.sync_phasor(220, 260, 0.5, 6, 4)
    I = py["I"] if isinstance(py, dict) else py[0]
    assert [r[0], r[1]] == pytest.approx([complex(I).real, complex(I).imag], rel=1e-9)
    th = np.arange(1440) / 1440 * 2 * math.pi
    w = ch4.winding_mmf(th, 3, "3상")
    kd = w["kd"] if isinstance(w, dict) else w[2]
    assert r[4] == pytest.approx(kd, rel=1e-9)
    tf, tr = ch4.sync_torque(0.7, 220, 260, 6, 4, 60 * math.pi)
    assert r[5] == pytest.approx([float(tf), float(tr)], rel=1e-9)
