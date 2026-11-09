"""제어 블록 편집기 엔진(ui/realtime/blocks.js) 검증. Node.js 가 없으면 건너뛴다."""
import json
import pathlib
import shutil
import subprocess

import pytest

RT = pathlib.Path(__file__).resolve().parents[1] / "ui" / "realtime"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="Node.js 없음")

PRELUDE = f"""
global.DCEngine = require({json.dumps(str(RT / 'engine.js'))});
const B = require({json.dumps(str(RT / 'blocks.js'))});
const p = {{Ra:0.5, La:0.01, Rf:220, Lf:20, Laf:1.8, Rs:0, Ls:0, Ms:0, J:0.1, B:0.005}};
const env = {{ motors: {{ "타여자": {{ type: "separately", sigma: 1, p, V: 220, Vf: 220, Rfx: 0 }} }},
  defaultMotor: "타여자", ctrl: {{ Ra: 0.5, La: 0.01, J: 0.1, B: 0.005, V: 220, K: 1.8, Ilim: 40, TL: 30 }} }};
function run(dg, T) {{
  const r = new B.Runner(dg, env); const mo = dg.blocks.find(b => b.type === 'motor');
  let imax = 0;
  for (let k = 0; k < Math.round(T / 0.01); k++) {{ r.advance(0.01, 1e-4); imax = Math.max(imax, Math.abs(r.out[mo.id][2])); }}
  const o = r.out[mo.id];
  return {{ rpm: o[1], ia: o[2], imax, msgs: r.check() }};
}}
"""


def js(body):
    out = subprocess.run([node, "-e", PRELUDE + body], capture_output=True, text=True,
                         check=True, timeout=120)
    return json.loads(out.stdout)


def template(name, T=2.5):
    return js(f"""
const dg = new B.Diagram(); B.templates(env)[{json.dumps(name)}](dg);
console.log(JSON.stringify(run(dg, {T})));""")


def test_double_loop_template_tracks_speed_with_load_and_limits_current():
    r = template("속도·전류 이중 루프 (PI-PI) + E 피드포워드")
    assert r["rpm"] == pytest.approx(1000.0, abs=1.0)        # 1 초에 30 N·m 부하가 걸려도
    assert r["ia"] == pytest.approx((30 + 0.005 * 104.72) / 1.8, rel=0.02)
    assert r["imax"] < 40 * 1.03
    assert r["msgs"] == []


def test_p_only_speed_loop_leaves_steady_state_error():
    r = template("P 제어 속도 루프 (정상상태 오차 확인)")
    assert 900 < r["rpm"] < 990      # 적분기가 없어 부하 토크만큼 오차가 남음


def test_speed_loop_without_current_loop_has_large_inrush():
    r = template("속도 제어만 (속도 PI → 전압 직접)")
    assert r["imax"] > 3 * 40


def test_all_templates_run_without_warnings():
    names = js("console.log(JSON.stringify(Object.keys(B.templates(env))));")
    for n in names:
        if n == "빈 화면":
            continue
        r = template(n, T=1.0)
        assert r["msgs"] == [], (n, r["msgs"])


def test_algebraic_loop_detected():
    r = js("""
const dg = new B.Diagram();
const a = dg.add('gain', 0, 0), b = dg.add('gain', 200, 0);
dg.connect(a.id, 0, b.id, 0); dg.connect(b.id, 0, a.id, 0);
const r = new B.Runner(dg, env); r.step(1e-4);
console.log(JSON.stringify(r.check()));""")
    assert any("대수 루프" in m for m in r)


def test_pid_mode_switch_and_json_roundtrip():
    r = js("""
const dg = new B.Diagram(); B.templates(env)["P 제어 속도 루프 (정상상태 오차 확인)"](dg);
const pid = dg.blocks.find(b => b.type === 'pid' && b.p.mode === 'P');
pid.p.mode = 'PI'; pid.p.Ki = 40;                   // P → PI 로 바꾸면 오차가 사라져야 함
const dg2 = new B.Diagram(); dg2.load(JSON.parse(JSON.stringify(dg.toJSON())));
console.log(JSON.stringify(run(dg2, 3.0)));""")
    assert r["rpm"] == pytest.approx(1000.0, abs=2.0)
