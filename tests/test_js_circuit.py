"""회로 시뮬레이터 엔진(circuit_engine.js) 검증: 해석해와 비교."""
import json
import math
import pathlib
import shutil
import subprocess

import pytest

RT = pathlib.Path(__file__).resolve().parents[1] / "ui" / "realtime"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="Node.js 없음")

PRELUDE = f"""
const C = require({json.dumps(str(RT / 'circuit_engine.js'))});
const by = (sc, t) => sc.elems.filter((e) => e.type === t);
function tpl(name, f) {{ const sc = new C.Schematic(); C.TEMPLATES[name](sc); if (f) f(sc); return [sc, new C.Sim(sc)]; }}
function run(s, T, h) {{ const n = Math.round(T / h); for (let k = 0; k < n; k++) s.step(h); }}
"""


def js(body):
    out = subprocess.run([node, "-e", PRELUDE + body], capture_output=True, text=True, check=True, timeout=180)
    return json.loads(out.stdout)


def test_all_templates_solve_without_error():
    r = js("""const res = {};
for (const name of Object.keys(C.TEMPLATES)) {
  const [sc, s] = tpl(name, (sc) => by(sc, "switch").forEach((e) => (e.p.on = true)));
  run(s, 0.02, 1e-5);
  res[name] = { err: s.err, finite: Object.values(s.I).every(Number.isFinite) };
}
console.log(JSON.stringify(res));""")
    for name, v in r.items():
        assert v["err"] == "" and v["finite"], name


def test_rl_rise_matches_exponential_and_freewheel_diode_takes_over():
    r = js("""const [sc, s] = tpl("RL 회로: 스위치를 닫으면 전류가 서서히 오름"); by(sc, "switch")[0].p.on = true;
run(s, 0.05, 1e-5); const i1 = s.I[by(sc, "ammeter")[0].id];
by(sc, "switch")[0].p.on = false; run(s, 0.01, 1e-5);
console.log(JSON.stringify({ i1, d: s.I[by(sc, "diode")[0].id], L: s.I[by(sc, "inductor")[0].id], a: s.I[by(sc, "ammeter")[0].id] }));""")
    assert r["i1"] == pytest.approx(1.2 * (1 - math.exp(-1)), rel=2e-3)      # τ = L/R = 0.05 s
    assert r["d"] == pytest.approx(r["L"], rel=1e-6) and r["d"] > 0.6          # 인덕터 전류가 다이오드로 돎
    assert abs(r["a"]) < 1e-6                                                  # 열린 스위치 쪽은 0


def test_rc_charge_and_divider_and_parallel_lamps():
    r = js("""let [sc, s] = tpl("RC 회로: 충전과 방전"); run(s, 0.1, 1e-5); const vc = s.volt(by(sc, "capacitor")[0].id);
[sc, s] = tpl("직렬 회로: 전압이 나뉨 (전압 분배)"); run(s, 1e-3, 1e-4);
const div = { I: s.I[by(sc, "ammeter")[0].id], V: s.volt(by(sc, "voltmeter")[0].id) };
[sc, s] = tpl("병렬 회로: 전구마다 전류가 나뉨"); run(s, 1e-3, 1e-4);
const par = { I: s.I[by(sc, "ammeter")[0].id], lamps: by(sc, "lamp").map((e) => s.I[e.id]), src: s.I[by(sc, "vdc")[0].id], vs: s.volt(by(sc, "vdc")[0].id) };
console.log(JSON.stringify({ vc, div, par }));""")
    assert r["vc"] == pytest.approx(10 * (1 - math.exp(-1)), rel=2e-3)        # τ = RC = 0.1 s
    assert r["div"]["I"] == pytest.approx(12 / 600, rel=1e-6) and r["div"]["V"] == pytest.approx(4, rel=1e-6)
    lamps = [5 / 12, 10 / 12, 12 / (12 ** 2 / 20 + 0.001)]                    # 세 번째 전구는 닫힌 스위치(1 mΩ)와 직렬
    assert r["par"]["lamps"] == pytest.approx(lamps, rel=1e-6)
    assert r["par"]["I"] == pytest.approx(sum(lamps), rel=1e-6)
    assert r["par"]["src"] == pytest.approx(sum(lamps), rel=1e-6) and r["par"]["vs"] == pytest.approx(12)   # 전원은 내보내는 쪽이 +


def test_rlc_resonance_current_amplitude():
    r = js("""const [sc, s] = tpl("RLC 직렬 공진 (교류)"); const ac = by(sc, "vac")[0];
ac.p.f = 1 / (2 * Math.PI * Math.sqrt(0.01 * 100e-6)); run(s, 0.3, 2e-6);
let mx = 0; for (let k = 0; k < 5000; k++) { s.step(2e-6); mx = Math.max(mx, Math.abs(s.I[by(sc, "ammeter")[0].id])); }
console.log(JSON.stringify({ mx }));""")
    assert r["mx"] == pytest.approx(10 / 10, rel=0.02)                         # 공진: |Z| = R


def test_half_wave_rectifier_peak():
    r = js("""const [sc, s] = tpl("반파 정류: 다이오드 1개"); let mx = 0, mn = 1e9;
for (let k = 0; k < 4000; k++) { s.step(1e-5); const v = s.volt(by(sc, "voltmeter")[0].id); mx = Math.max(mx, v); mn = Math.min(mn, v); }
console.log(JSON.stringify({ mx, mn }));""")
    assert r["mx"] == pytest.approx((10 - 0.7) * 100 / 100.01, rel=5e-3)
    assert r["mn"] > -1e-3                                                     # 역방향은 막힘


def test_dc_motor_steady_state_matches_equations():
    r = js("""const [sc, s] = tpl("DC 전동기 기동: 기동 저항으로 돌입 전류 줄이기", (sc) => by(sc, "switch")[0].p.on = true);
let peak = 0; for (let k = 0; k < 2000; k++) { s.step(1e-4); peak = Math.max(peak, s.I[by(sc, "ammeter")[0].id]); }
run(s, 20, 1e-4); const m = by(sc, "motor")[0];
console.log(JSON.stringify({ peak, w: s.st[m.id].w, i: s.I[m.id] }));""")
    K, Ra, Rst, B, TL, V = 1.8, 0.5, 5, 0.005, 30, 220
    w = (K * V - (Ra + Rst) * TL) / ((Ra + Rst) * B + K * K)
    assert r["w"] == pytest.approx(w, rel=1e-3)
    assert r["i"] == pytest.approx((B * w + TL) / K, rel=1e-3)
    assert r["peak"] < V / (Ra + Rst)                                          # 기동 저항이 돌입 전류를 제한


def test_buck_chopper_average_voltage_sets_speed():
    r = js("""const [sc, s] = tpl("강압 초퍼: PWM 으로 DC 전동기 속도 바꾸기"); run(s, 15, 1e-5);
const m = by(sc, "motor")[0]; console.log(JSON.stringify({ w: s.st[m.id].w }));""")
    K, Ra, B, TL, V, D = 1.8, 0.5, 0.005, 20, 220, 0.5
    w = (K * (D * V - 0.7 * (1 - D)) - Ra * TL) / (Ra * B + K * K)           # 평균 전압 D·V (다이오드 강하 보정)
    assert r["w"] == pytest.approx(w, rel=0.02)


def test_wire_currents_follow_kcl_at_tee_and_parallel_wires():
    r = js("""const sc = new C.Schematic();
sc.add("vdc", 0, 4, 3, { V: 10 }); sc.wire(0, 0, 8, 0);
sc.add("resistor", 4, 0, 1, { R: 10 }); sc.add("resistor", 8, 0, 1, { R: 10 });
sc.wire(0, 4, 8, 4); sc.wire(0, 4, 8, 4);     // 같은 자리에 겹친 전선 두 가닥 (병렬)
sc.add("ground", 0, 4);
const s = new C.Sim(sc); s.step(1e-4); const wc = s.wireCurrents();
const seg = s.net.segs.map((g, k) => ({ a: s.net.P[g.a], b: s.net.P[g.b], i: wc[k] }));
console.log(JSON.stringify(seg));""")
    top = {(tuple(x["a"]), tuple(x["b"])): x["i"] for x in r if x["a"][1] == 0}
    assert top[((0, 0), (4, 0))] == pytest.approx(2.0, rel=1e-6)              # 전원 → 첫 갈래 앞: 두 저항 전류 합
    assert top[((4, 0), (8, 0))] == pytest.approx(1.0, rel=1e-6)
    bottom = [x["i"] for x in r if x["a"][1] == 4 and x["a"][0] == 0 and x["b"][0] == 4]
    assert len(bottom) == 2 and sum(bottom) == pytest.approx(-2.0, rel=1e-6)  # 귀로 전류가 두 가닥에 나뉨


def test_short_circuit_reports_error():
    r = js("""const sc = new C.Schematic(); sc.add("vdc", 0, 4, 3); sc.wire(0, 0, 0, 4);
const s = new C.Sim(sc); s.step(1e-4); console.log(JSON.stringify({ err: s.err }));""")
    assert "단락" in r["err"]


def _three_phase_peaks(name, h, T=0.2, t0=0.15):
    return js(f"""const [sc, s] = tpl({json.dumps(name)}, (sc) => by(sc, "switch").forEach((e) => (e.p.on = true)));
const src = sc.elems.find((e) => e.type === "vac3" || e.type === "inv3"); const mx = [0, 0, 0]; let vmx = 0, isum = 0, nsum = 0;
for (let k = 0; k < Math.round({T} / {h}); k++) {{ s.step({h}); if (s.t > {t0}) {{
  const I = s.phaseI(src.id); I.forEach((v, j) => (mx[j] = Math.max(mx[j], Math.abs(v)))); vmx = Math.max(vmx, Math.abs(s.lineV(src.id)[0]));
  isum = Math.max(isum, Math.abs(I[0] + I[1] + I[2])); const am = by(sc, "ammeter")[0]; if (am) nsum = Math.max(nsum, Math.abs(s.I[am.id])); }} }}
console.log(JSON.stringify({{ mx, vmx, isum, nsum, err: s.err }}));""")


def test_three_phase_source_balanced_rl_load():
    r = _three_phase_peaks("3상 교류 전원 + Y 결선 RL 부하 (중성선 스위치)", 1e-5)
    Z = abs(complex(10, 2 * math.pi * 60 * 0.02))
    Ip = 220 * math.sqrt(2) / math.sqrt(3) / Z
    assert r["err"] == ""
    assert r["mx"] == pytest.approx([Ip] * 3, rel=5e-3)
    assert r["vmx"] == pytest.approx(220 * math.sqrt(2), rel=1e-3)            # 선간 전압 최댓값
    assert r["isum"] < 1e-6 and r["nsum"] < 1e-3                               # 평형: 상전류 합 = 중성선 전류 = 0


def test_three_phase_inverter_spwm_fundamental_current():
    r = _three_phase_peaks("3상 인버터: 직류 → 3상 교류 (RL 부하)", 5e-6)
    Z = abs(complex(10, 2 * math.pi * 60 * 0.02))
    Ip = 0.8 * 300 / 2 / Z                                                     # 상전압 기본파 최댓값 = m·Vdc/2
    assert r["err"] == ""
    assert r["mx"] == pytest.approx([Ip] * 3, rel=0.06)                       # PWM 리플만큼 여유
    assert r["vmx"] == pytest.approx(300, rel=1e-3)                            # 선간 전압은 ±Vdc 로 스위칭
    assert r["isum"] < 1e-6


def test_six_step_inverter_line_voltage_levels():
    r = js("""const [sc, s] = tpl("3상 인버터: 직류 → 3상 교류 (RL 부하)"); const inv = by(sc, "inv3")[0]; inv.p.mode = "6스텝 (180° 통전)";
const lv = new Set(); for (let k = 0; k < 20000; k++) { s.step(5e-6); lv.add(Math.round(s.lineV(inv.id)[0])); }
inv.p.mode = "정지 (모든 스위치 꺼짐)"; for (let k = 0; k < 20000; k++) s.step(5e-6);
console.log(JSON.stringify({ lv: [...lv].sort((a, b) => a - b), off: s.phaseI(inv.id) }));""")
    assert set(r["lv"]) <= {-300, 0, 300} and {-300, 300} <= set(r["lv"])    # 6스텝 선간 전압: +Vdc, 0, −Vdc
    assert all(abs(i) < 1e-3 for i in r["off"])                                # 정지하면 전류 0 (RL 부하 에너지 소멸 후)


def test_h_bridge_unipolar_bipolar_average_and_reverse():
    r = js("""const out = {};
for (const mode of ["유니폴라", "바이폴라"]) for (const m of [0.5, -0.5]) {
  const [sc, s] = tpl("H-브리지 4상한 초퍼: DC 전동기 정·역회전"); const hb = by(sc, "hbr")[0]; hb.p.mode = mode; hb.p.m = m;
  let vs = 0, n = 0, lo = 1e9, hi = -1e9;
  for (let k = 0; k < 600000; k++) { s.step(2e-6); if (s.t > 1.1) { const i = s.phaseI(hb.id)[0]; vs += s.lineV(hb.id)[0]; n++; lo = Math.min(lo, i); hi = Math.max(hi, i); } }
  out[mode + m] = { v: vs / n, w: s.st[by(sc, "motor")[0].id].w, rip: hi - lo, err: s.err };
}
console.log(JSON.stringify(out));""")
    for k, v in r.items():
        assert v["err"] == ""
        assert abs(v["v"]) == pytest.approx(70, rel=0.01)
    assert r["유니폴라0.5"]["w"] > 0 > r["유니폴라-0.5"]["w"]
    assert r["유니폴라0.5"]["rip"] < 0.5 * r["바이폴라0.5"]["rip"]
