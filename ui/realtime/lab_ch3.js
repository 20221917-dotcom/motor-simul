/* 강의 실습 3장 BLDC (브라우저 계산). 스위칭 모델은 lectures/ch3.py 와 같음. */
(function (root) {
  "use strict";
  const { M, metric, table, sub, hline, vline, line, pts, draw, tx, svg } = root.Lab;
  const RPM = M.RPM, PH = ["a", "b", "c"], SHIFT = [0, 2 * Math.PI / 3, 4 * Math.PI / 3];
  const COLP = { a: "#d62828", b: "#2a9d8f", c: "#1d4ed8" };
  const DEFAULT = { Vdc: 48, R: 0.4, L: 0.8e-3, ke: 0.06, poles: 8, fsw: 10e3 };
  const STEP = [["a", "b"], ["a", "c"], ["b", "c"], ["b", "a"], ["c", "a"], ["c", "b"]];
  const METHODS = { "바이폴라 (대각 스위치 동시 PWM)": "bipolar", "유니폴라 H_PWM-L_ON (위 스위치만 PWM)": "hpwm", "유니폴라 H_ON-L_PWM (아래 스위치만 PWM)": "lpwm",
    "유니폴라 PWM_ON (통전 앞 60° PWM, 뒤 60° ON)": "pwm_on", "유니폴라 ON_PWM (통전 앞 60° ON, 뒤 60° PWM)": "on_pwm" };

  // ---------------------------------------------------------------- 계산
  const mod2pi = (x) => ((x % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
  function trap(x, flat = 120) {
    x = mod2pi(x); const edge = Math.max((Math.PI - M.rad(flat)) / 2, 1e-9);
    if (x < Math.PI) return Math.min(1, Math.max(0, Math.min(x, Math.PI - x) / edge));
    return -Math.min(1, Math.max(0, Math.min(x - Math.PI, 2 * Math.PI - x) / edge));
  }
  const emf = (th, kind, flat) => (kind === "정현파" ? Math.sin(th) : trap(th, flat));
  function curShape(th, kind) {
    if (kind === "정현파") return Math.sin(th);
    const x = mod2pi(th);
    return x >= Math.PI / 6 && x < 5 * Math.PI / 6 ? 1 : x >= 7 * Math.PI / 6 && x < 11 * Math.PI / 6 ? -1 : 0;
  }
  const hall = (th) => SHIFT.map((s) => (mod2pi(th - s) < Math.PI ? 1 : 0));
  const sector = (th) => Math.floor(mod2pi(th - Math.PI / 6) / (Math.PI / 3)) % 6;
  const stepInfo = (k) => { const [hi, lo] = STEP[k]; return [hi, lo, PH.find((p) => p !== hi && p !== lo)]; };
  const ripple = (x) => { const m = M.mean(x); return Math.abs(m) > 1e-12 ? M.ptp(x) / Math.abs(m) * 100 : NaN; };

  function gates(th, on, method) {
    const k = sector(th), [hi, lo] = STEP[k], up = { a: 0, b: 0, c: 0 }, dn = { a: 0, b: 0, c: 0 };
    const fh = STEP[(k + 5) % 6][0] !== hi, fl = STEP[(k + 5) % 6][1] !== lo;
    if (method === "bipolar") { if (on) { up[hi] = 1; dn[lo] = 1; } else { dn[hi] = 1; up[lo] = 1; } }
    else if (method === "hpwm") { up[hi] = on; dn[lo] = 1; }
    else if (method === "lpwm") { up[hi] = 1; dn[lo] = on; }
    else if (method === "pwm_on") { up[hi] = fh ? on : 1; dn[lo] = fl ? on : 1; }
    else { up[hi] = fh ? 1 : on; dn[lo] = fl ? 1 : on; }
    return [up, dn];
  }
  function stepSim(st, h, t, duty, method, P, flat, off) {
    const { Vdc, R, L, ke, fsw } = P, i = st.i, wm = st.wm, th = st.th;
    const on = ((t * fsw) % 1) < duty ? 1 : 0, [up, dn] = gates(th - off, on, method);
    const e = SHIFT.map((s) => ke * wm * trap(th - s, flat)), v = [0, 0, 0], known = [false, false, false];
    PH.forEach((p, j) => { if (up[p]) { v[j] = Vdc; known[j] = true; } else if (dn[p]) known[j] = true; else if (i[j] > 1e-9) known[j] = true; else if (i[j] < -1e-9) { v[j] = Vdc; known[j] = true; } });
    const vnOf = () => { const ks = [0, 1, 2].filter((j) => known[j]); return ks.length >= 2 ? ks.reduce((s, j) => s + v[j] - R * i[j] - e[j], 0) / ks.length : (e[0] + e[1] + e[2]) / 3; };
    let vn = vnOf();
    for (let j = 0; j < 3; j++) if (!known[j] && known.filter(Boolean).length >= 2) { const vf = e[j] + vn; if (vf > Vdc || vf < 0) { v[j] = vf > Vdc ? Vdc : 0; known[j] = true; vn = vnOf(); } }
    const inew = [0, 1, 2].map((j) => (known[j] ? i[j] + h * (v[j] - vn - R * i[j] - e[j]) / L : 0));
    for (let j = 0; j < 3; j++) { const p = PH[j]; if (known[j] && !(up[p] || dn[p]) && i[j] !== 0 && inew[j] * i[j] < 0) { inew[j] = 0; known[j] = false; } }
    const ks = [0, 1, 2].filter((j) => known[j]);
    if (ks.length >= 2 && ks.length < 3) { const r = (inew[0] + inew[1] + inew[2]) / ks.length; for (const j of ks) inew[j] -= r; }
    st.i = inew;
    const Te = wm > 1e-6 ? (e[0] * inew[0] + e[1] * inew[1] + e[2] * inew[2]) / wm : ke * SHIFT.reduce((s, sh, k) => s + trap(th - sh, flat) * inew[k], 0);
    if (!known.every(Boolean)) vn = vnOf();
    for (let j = 0; j < 3; j++) if (!known[j]) v[j] = e[j] + vn;
    return { on, up, dn, e, v, vn, Te, known };
  }
  function simulate(rpm, duty, method, o = {}) {
    const P = Object.assign({}, DEFAULT, o.P || {}), flat = o.flat || 120, off = M.rad(o.hall || 0), cycles = o.cycles || 3, spp = o.spp || 40;
    const pp = P.poles / 2, wm = rpm / RPM, we = pp * Math.max(wm, 1e-3), Te_ = 2 * Math.PI / we, h = 1 / P.fsw / spp;
    const n = Math.floor(cycles * Te_ / h), keep = Math.floor(Te_ / h), every = Math.max(1, Math.floor(keep / 4000));
    const st = { i: [0, 0, 0], th: 0, wm };
    const R = { t: [], i: [[], [], []], v: [[], [], []], vn: [], e: [[], [], []], Te: [], pwm: [], sector: [], fl: [[], [], []], up: [[], [], []], dn: [[], [], []] };
    let t0 = null;
    for (let k = 0; k < n; k++) {
      const t = k * h, o2 = stepSim(st, h, t, duty, method, P, flat, off);
      st.th += pp * st.wm * h;
      if (k >= n - keep && (k - (n - keep)) % every === 0) {
        if (t0 === null) t0 = t;
        R.t.push(t - t0); R.vn.push(o2.vn); R.Te.push(o2.Te); R.pwm.push(o2.on); R.sector.push(sector(st.th - off));
        for (let j = 0; j < 3; j++) { R.i[j].push(st.i[j]); R.v[j].push(o2.v[j]); R.e[j].push(o2.e[j]); R.fl[j].push(!o2.known[j]); R.up[j].push(o2.up[PH[j]]); R.dn[j].push(o2.dn[PH[j]]); }
      }
    }
    R.P = P; R.wm = wm; return R;
  }
  function drive(rpmRef, ctrl, method, TL, o = {}) {
    const P = Object.assign({}, DEFAULT), J = 2e-4, tend = 0.12, tload = 0.08, wcs = 2 * Math.PI * 20, Imax = 10, spp = 20;
    const { Vdc, R, L, ke, fsw } = P, pp = P.poles / 2, h = 1 / fsw / spp, n = Math.floor(tend / h);
    const st = { i: [0, 0, 0], th: 0, wm: 0 }, kt = 2 * ke, Kps = J * wcs / kt, Kis = Kps * wcs / 5, wcc = 2 * Math.PI * 500, Kpc = 2 * L * wcc, Kic = 2 * R * wcc;
    let xw = 0, xi = 0, duty = 0; const wr = rpmRef / RPM, every = 4, Ts = 1 / fsw;
    const out = { t: [], rpm: [], Te: [], i: [[], [], []], ea: [] };
    for (let k = 0; k < n; k++) {
      const t = k * h;
      if (k % spp === 0) {
        const ew = wr - st.wm; let vv;
        if (ctrl === "전류 제어") {
          const iu = Kps * ew + xw, istar = M.clip(iu, 0, Imax); xw += Ts * Kis * (ew - (iu - istar) / Kps);
          const idc = 0.5 * (Math.abs(st.i[0]) + Math.abs(st.i[1]) + Math.abs(st.i[2])), ei = istar - idc, vu = Kpc * ei + xi + 2 * ke * st.wm;
          vv = M.clip(vu, 0, Vdc); xi += Ts * Kic * (ei - (vu - vv) / Kpc);
        } else { const Kpv = Kps * Kpc / (2 * L), vu = Kpv * ew + xw; vv = M.clip(vu, 0, Vdc); if (vu === vv) xw += Ts * Kpv * wcs / 5 * ew; }
        duty = vv / Vdc;
      }
      const r = stepSim(st, h, t, duty, method, P, 120, 0);
      st.wm = Math.max(0, st.wm + h * (r.Te - (t >= tload ? TL : 0) - 1e-5 * st.wm) / J); st.th += pp * st.wm * h;
      if (k % every === 0) { out.t.push(t); out.rpm.push(st.wm * RPM); out.Te.push(r.Te); out.ea.push(r.e[0]); for (let j = 0; j < 3; j++) out.i[j].push(st.i[j]); }
    }
    return out;
  }
  function zeroCrossings(R, ph = 0) {
    const t = R.t, v = R.v[ph], e = R.e[ph], Vh = R.P.Vdc / 2, fl = R.fl[ph], det = [], tru = [];
    let last = -1;
    for (let k = 0; k < t.length; k++) {
      if (!fl[k]) { last = -1; continue; }
      if (!R.pwm[k]) continue;
      if (last >= 0 && (v[last] - Vh) * (v[k] - Vh) < 0) det.push(t[k]);
      last = k;
    }
    for (let k = 0; k < t.length - 1; k++) if (e[k] * e[k + 1] < 0 && stepInfo(R.sector[k])[2] === PH[ph]) tru.push(t[k + 1]);
    return [det, tru];
  }

  // ---------------------------------------------------------------- 그림: 3상 인버터 + Y 결선
  function inverterSVG(sw, roles, title) {
    const o = svg.start(560, 300), xs = { a: 150, b: 240, c: 330 }, yT = 45, yB = 255, yM = 150, POS = "#d62828", NEG = "#1d4ed8", FLT = "#9ca3af";
    svg.text(o, 280, 16, title, 12, "#333");
    svg.line(o, 40, yT, 360, yT); svg.line(o, 40, yB, 360, yB); svg.line(o, 40, yT, 40, yM - 28); svg.line(o, 40, yB, 40, yM + 28); svg.source(o, 40, yM, 28, "Vdc");
    const cx = 470, cy = 150, ends = { a: [cx, cy - 70], b: [cx - 60, cy + 40], c: [cx + 60, cy + 40] };
    for (const p of PH) {
      const x = xs[p]; svg.line(o, x, yT, x, yT + 20); svg.line(o, x, yT + 60, x, yB - 60); svg.line(o, x, yB - 20, x, yB);
      svg.sw(o, x, yT + 40, !!sw[p + "+"], p.toUpperCase() + "+"); svg.sw(o, x, yB - 40, !!sw[p + "-"], p.toUpperCase() + "−");
      const col = roles[p] === "+" ? POS : roles[p] === "−" ? NEG : FLT, dash = roles[p] === "개방" ? "4 3" : "";
      const [ex, ey] = ends[p], kx = 385 + (p === "a" ? 0 : p === "b" ? 10 : 20);
      svg.poly(o, [[x, yM], [kx, yM], [kx, ey], [ex, ey]].map((q) => q), col, roles[p] === "개방" ? 1.5 : 2.5);
      if (dash) o[o.length - 1] = o[o.length - 1].replace("/>", ` stroke-dasharray="${dash}"/>`);
      svg.line(o, ex, ey, cx, cy, col, 3);
      svg.text(o, ex + (p === "b" ? -14 : 14), ey + (p === "a" ? -10 : 12), `${p} (${roles[p]})`, 12, col, p === "b" ? "end" : "start", "bold");
    }
    svg.circle(o, cx, cy, 4, "#333"); svg.text(o, cx + 12, cy, "n", 12);
    return svg.done(o);
  }

  // ---------------------------------------------------------------- 탭
  const T = {};
  const deg = (a) => a.map(M.deg);

  T.shapes = function (tab) {
    tab.section((s) => {
      s.row(); s.radio("ek", "역기전력 모양", ["사다리꼴", "정현파"], "사다리꼴"); s.slider("flat", "사다리꼴 평탄부 폭 [°]", 0, 180, 10, 120); s.radio("ik", "상전류 모양", ["120° 사각파", "정현파"], "120° 사각파");
      s.end(); const p = s.plot(560), m = s.metrics(1);
      const n = 720, th = M.range(n, (k) => (k + 0.5) / n * 2 * Math.PI), x = deg(th);
      s.on((v) => {
        const e = SHIFT.map((sh) => th.map((a) => emf(a - sh, v.ek, v.flat))), i = SHIFT.map((sh) => th.map((a) => curShape(a - sh, v.ik)));
        const Tq = th.map((_, k) => e[0][k] * i[0][k] + e[1][k] * i[1][k] + e[2][k] * i[2][k]);
        const lay = sub(3, 1, { titles: ["상 역기전력 e (단위값)", "상전류 i (단위값)", "토크 ∝ Σ e·i"], sharex: true }); Object.assign(lay.xaxis3, tx("전기각 θe [°]"), { dtick: 60 });
        const tr = [];
        PH.forEach((p, k) => tr.push(line(x, e[k], `e${p}`, { color: COLP[p] }), line(x, i[k], `i${p}`, { color: COLP[p], n: 2, shape: v.ik === "정현파" ? undefined : "hv" }), line(x, e[k].map((q, j) => q * i[k][j]), `T${p} = e${p}·i${p}`, { color: COLP[p], n: 3, dash: "dot" })));
        tr.push(line(x, Tq, "3상 토크 (합)", { n: 3, color: "#111", width: 3 }));
        draw(p, tr, Object.assign(lay, { legend: { orientation: "v", x: 1.01, y: 1 }, margin: { r: 110, b: 40 } }));
        metric(m[0], "토크 리플 (최대−최소)/평균", `${ripple(Tq).toFixed(1)} %`);
      });
    });
  };

  T.sixstep = function (tab) {
    tab.section((s) => {
      const [c0, c1] = s.cols([1, 2]);
      s.into(c0); s.slider("deg", "회전자 위치 θe [°] (전기각)", 0, 359, 1, 45, { all: true }); const hd = s.h(""), m = s.metrics(2), nt = s.note();
      s.into(c1); const box = s.svg(300);
      s.end(); const [d0, d1] = s.cols([2, 3]); s.into(d0); const pp = s.plot(320), nt2 = s.note(); s.into(d1); s.html("<b>홀 센서 전압</b> V_H = (R_H/d)·I_H·B → 비교기로 0/1 신호"); const ph = s.plot(260);
      s.end(); const pw = s.plot(480), tb = s.table();
      const xg = M.linspace(0, 360, 721), xr = xg.map(M.rad);
      table(tb, ["구간", "홀 (H1H2H3)", "켜는 스위치", "개방 상"], M.range(6, (i) => [`${i + 1}: ${30 + 60 * i}°~${90 + 60 * i}°`, hall(M.rad(60 + 60 * i)).join(""), `${STEP[i][0].toUpperCase()}+, ${STEP[i][1].toUpperCase()}−`, stepInfo(i)[2]]));
      s.on((v) => {
        const th = M.rad(v.deg), k = sector(th), [hi, lo, fl] = stepInfo(k), H = hall(th);
        const roles = { [hi]: "+", [lo]: "−", [fl]: "개방" };
        hd.textContent = `구간 ${k + 1} (${30 + 60 * k}° ~ ${90 + 60 * k}°)`;
        metric(m[0], "홀 센서 (H1 H2 H3)", H.join(" ")); metric(m[1], "켜는 스위치", `${hi.toUpperCase()}+ , ${lo.toUpperCase()}−`);
        nt.innerHTML = `전류 경로: <b>Vdc(+) → ${hi.toUpperCase()}+ → ${hi}상 → 중성점 → ${lo}상 → ${lo.toUpperCase()}− → Vdc(−)</b>, <b>${fl}상은 개방</b> (역기전력만 나타남)`;
        box.innerHTML = inverterSVG({ [hi + "+"]: 1, [lo + "-"]: 1 }, roles, `θe = ${v.deg}° : ${hi}+ / ${lo}− 통전, ${fl} 개방`);
        const axd = { a: 0, b: 120, c: 240 }, vx = Math.cos(M.rad(axd[hi])) - Math.cos(M.rad(axd[lo])), vy = Math.sin(M.rad(axd[hi])) - Math.sin(M.rad(axd[lo]));
        const sa = M.deg(Math.atan2(vy, vx)), rot = (v.deg + 180) % 360, lead = ((sa - rot + 540) % 360) - 180;
        const tr = [{ type: "scatterpolar", r: [0, 1], theta: [0, sa], mode: "lines+markers", line: { color: "#7c3aed", width: 6 }, name: "고정자 자계 (통전 상의 기자력)" },
          { type: "scatterpolar", r: [0, 0.8], theta: [0, rot], mode: "lines+markers", line: { color: "#d62828", width: 6 }, name: "회전자 N 극" }];
        for (const p of PH) tr.push({ type: "scatterpolar", r: [0, 1.1], theta: [0, axd[p]], mode: "lines", line: { color: COLP[p], width: 1, dash: "dot" }, showlegend: false });
        draw(pp, tr, { polar: { radialaxis: { visible: false, range: [0, 1.15] } }, margin: { l: 30, r: 30, t: 20, b: 60 }, legend: { y: -0.08 } });
        nt2.textContent = `고정자 자계가 회전자보다 ${lead.toFixed(0)}° 앞섬 (60°~120° 사이에서 회전 방향 토크, 90° 에서 최대). θe 를 움직이면 자계가 60° 마다 한 칸씩 뜀.`;
        draw(ph, [line(xg, xr.map(Math.sin), "H1 홀 전압 (∝ 자속 밀도 B)", { color: COLP.a }), line(xg, xr.map((a) => (Math.sin(a) > 0 ? 1.2 : 0)), "H1 디지털 출력", { color: "#111", shape: "hv" })],
          { shapes: [vline(v.deg, 1, { color: "#16a34a", dash: "solid", width: 2 })], xaxis: Object.assign(tx("θe [°]"), { dtick: 60 }) });
        const lay = sub(3, 1, { titles: ["홀 센서 신호", "역기전력 (사다리꼴)", "이상적인 상전류 (120° 통전)"], sharex: true }); Object.assign(lay.xaxis3, tx("θe [°]"), { dtick: 60 });
        const tw = [];
        PH.forEach((p, j) => tw.push(line(xg, xr.map((a) => hall(a)[j] * 0.8 + (2 - j) * 1.1), `H${j + 1}`, { color: COLP[p], shape: "hv" }), line(xg, xr.map((a) => trap(a - SHIFT[j])), `e${p}`, { color: COLP[p], n: 2 }),
          line(xg, xr.map((a) => curShape(a - SHIFT[j], "")), `i${p}`, { color: COLP[p], n: 3, shape: "hv" })));
        lay.shapes = [];
        for (let b = 30; b < 360; b += 60) for (const nn of [1, 2, 3]) lay.shapes.push(vline(b, nn, { color: "#ddd", dash: "solid", width: 1 }));
        for (const nn of [1, 2, 3]) lay.shapes.push(vline(v.deg, nn, { color: "#16a34a", dash: "solid", width: 3 }));
        draw(pw, tw, Object.assign(lay, { legend: { orientation: "v", x: 1.01, y: 1 }, margin: { r: 70, b: 40 } }));
      });
    });
  };

  T.commutation = function (tab) {
    tab.section((s) => {
      s.row(); s.slider("rpm", "속도 [rpm] (고정)", 200, 4000, 100, 1500); s.slider("duty", "PWM 듀티", 0.05, 1, 0.05, 0.6); s.slider("hoff", "홀 센서 위치 오차 [°]", -30, 30, 5, 0); s.slider("flat", "역기전력 평탄부 [°]", 60, 180, 10, 120);
      s.end(); const p = s.plot(520), pz = s.plot(380), m = s.metrics(4), nt = s.note();
      s.on((v) => {
        const r = simulate(v.rpm, v.duty, "hpwm", { flat: v.flat, hall: v.hoff }), t = r.t.map((x) => x * 1000);
        const lay = sub(3, 1, { titles: ["상전류 [A]", "역기전력 [V]", "토크 [N·m]"], sharex: true }); Object.assign(lay.xaxis3, tx("시간 [ms] (전기각 1주기)"));
        const tr = []; PH.forEach((q, j) => tr.push(line(t, r.i[j], `i${q}`, { color: COLP[q] }), line(t, r.e[j], `e${q}`, { color: COLP[q], n: 2, dash: "dot", legend: false })));
        tr.push(line(t, r.Te, "Te", { n: 3, color: "#111" }));
        draw(p, tr, lay);
        let k0 = -1; const ks = []; for (let k = 0; k < r.sector.length - 1; k++) if (r.sector[k] !== r.sector[k + 1]) ks.push(k);
        if (ks.length) { k0 = ks[Math.floor(ks.length / 2)]; const win = Math.floor(t.length / 6 * 0.6), a = Math.max(k0 - Math.floor(win / 3), 0), b = Math.min(k0 + win, t.length);
          const lz = sub(2, 1, { titles: ["상 전환 구간 확대: 상전류", "토크 (전환 구간에서 솟거나 꺼짐)"], sharex: true }); Object.assign(lz.xaxis2, tx("시간 [ms]"));
          lz.shapes = [vline(t[k0 + 1], 1, { color: "#16a34a" }), vline(t[k0 + 1], 2, { color: "#16a34a" })];
          const tz = []; PH.forEach((q, j) => tz.push(line(t.slice(a, b), r.i[j].slice(a, b), `i${q}`, { color: COLP[q] }))); tz.push(line(t.slice(a, b), r.Te.slice(a, b), "Te", { n: 2, color: "#111" }));
          draw(pz, tz, lz); }
        const E = r.P.ke * r.wm;
        metric(m[0], "평균 토크", `${M.mean(r.Te).toFixed(3)} N·m`); metric(m[1], "토크 리플", `${ripple(r.Te).toFixed(0)} %`); metric(m[2], "상 역기전력 E", `${E.toFixed(1)} V`);
        metric(m[3], "Vdc / 4E", (r.P.Vdc / (4 * E)).toFixed(2), "1 보다 크면 전환 시 토크가 솟고, 작으면 꺼짐");
        nt.textContent = `전동기: Vdc = ${r.P.Vdc} V, R = ${r.P.R} Ω, L = ${r.P.L * 1e3} mH, ke = ${r.P.ke} V·s/rad, ${r.P.poles}극, PWM ${r.P.fsw / 1000} kHz (H_PWM-L_ON).`;
      });
    });
  };

  T.pwm = function (tab) {
    tab.section((s) => {
      s.row(); s.select("m", "PWM 기법", Object.keys(METHODS), Object.keys(METHODS)[1], { wide: true }); s.slider("rpm", "속도 [rpm] (고정)", 300, 3000, 100, 1500);
      s.slider("duty", "PWM 듀티", 0.1, 1, 0.05, 0.6); s.select("fsw", "PWM 주파수", [5000, 10000, 20000], 10000, { fmt: (x) => `${x / 1000} kHz` });
      s.end(); const p = s.plot(540), pg = s.plot(320), tb = s.table();
      s.on((v) => {
        const r = simulate(v.rpm, v.duty, METHODS[v.m], { P: { fsw: v.fsw } }), t = r.t.map((x) => x * 1000);
        const lay = sub(3, 1, { titles: ["상전류 [A]", "a상 단자 전압 va [V] (점선: 중성점 전압 vn)", "토크 [N·m]"], sharex: true }); Object.assign(lay.xaxis3, tx("시간 [ms]"));
        const tr = []; PH.forEach((q, j) => tr.push(line(t, r.i[j], `i${q}`, { color: COLP[q] })));
        tr.push(line(t, r.v[0], "va", { n: 2, color: COLP.a, width: 1 }), line(t, r.vn, "vn", { n: 2, color: "#666", dash: "dot", width: 1 }), line(t, r.Te, "Te", { n: 3, color: "#111" }));
        draw(p, tr, lay);
        const tg = []; PH.forEach((q, j) => tg.push(line(t, r.up[j].map((x) => x * 0.8 + (5 - 2 * j)), `${q.toUpperCase()}+`, { color: COLP[q], shape: "hv", width: 1 }),
          line(t, r.dn[j].map((x) => x * 0.8 + (4 - 2 * j)), `${q.toUpperCase()}−`, { color: COLP[q], shape: "hv", width: 1, dash: "dot" })));
        draw(pg, tg, { showlegend: false, margin: { b: 45 }, yaxis: { tickvals: [5.4, 4.4, 3.4, 2.4, 1.4, 0.4], ticktext: ["A+", "A−", "B+", "B−", "C+", "C−"] }, xaxis: tx("시간 [ms] — 6개 스위치의 게이트 신호 (상단·하단·선단·후단 PWM)") });
        table(tb, ["PWM 기법", "평균 토크 [N·m]", "토크 리플 [%]"], Object.entries(METHODS).map(([lab, mm]) => { const q = mm === METHODS[v.m] ? r : simulate(v.rpm, v.duty, mm, { P: { fsw: v.fsw }, spp: 20 }); return [lab, M.mean(q.Te).toFixed(3), ripple(q.Te).toFixed(0)]; }));
      });
    });
    tab.section((s) => {
      s.h("3.4.1 속도 제어로 정지 상태에서 기동 (속도·토크·역기전력·상전류)");
      s.row(); s.radio("ctrl", "제어 구조 (전압 제어: 속도 PI → 듀티 / 전류 제어: 속도 PI → 전류 PI → 듀티)", ["전류 제어", "전압(듀티) 제어"], "전류 제어", { wide: true });
      s.slider("rpmr", "속도 지령 [rpm]", 500, 3500, 100, 2000); s.slider("TLd", "0.08 s 에 거는 부하 [N·m]", 0, 0.3, 0.01, 0.1);
      s.end(); const p = s.plot(480), m = s.metrics(1);
      s.on((v) => {
        const d = drive(v.rpmr, v.ctrl, "hpwm", v.TLd);
        const lay = sub(2, 2, { titles: ["속도 [rpm]", "토크 [N·m]", "a상 역기전력 [V]", "상전류 [A]"] }); Object.assign(lay.xaxis3, tx("시간 [s]")); Object.assign(lay.xaxis4, tx("시간 [s]"));
        lay.shapes = [hline(v.rpmr, 1)];
        const tr = [line(d.t, d.rpm, "속도"), line(d.t, d.Te, "토크", { n: 2, width: 1, color: "#d62828" }), line(d.t, d.ea, "ea", { n: 3, width: 1, color: "#2a9d8f" })];
        PH.forEach((q, j) => tr.push(line(d.t, d.i[j], `i${q}`, { n: 4, width: 1, color: COLP[q] })));
        draw(p, tr, lay);
        metric(m[0], "최대 상전류", `${Math.max(...d.i.map((a) => M.max(a.map(Math.abs)))).toFixed(1)} A`, v.ctrl === "전류 제어" ? "전류 제어는 10 A 로 제한" : "전류 제한 없음");
      });
    });
  };

  T.sensorless = function (tab) {
    tab.section((s) => {
      s.row(); s.slider("rpm", "속도 [rpm] (고정)", 300, 4000, 100, 1500); s.slider("duty", "PWM 듀티", 0.1, 1, 0.05, 0.6);
      s.select("fsw", "PWM 주파수", [5000, 10000, 20000], 10000, { fmt: (x) => `${x / 1000} kHz` });
      s.select("m", "PWM 기법 (상단·하단·선단·후단 구동의 단자 전압)", Object.keys(METHODS).slice(1), Object.keys(METHODS)[1], { wide: true });
      s.end(); const p = s.plot(480), m = s.metrics(3);
      s.on((v) => {
        const r = simulate(v.rpm, v.duty, METHODS[v.m], { P: { fsw: v.fsw } }), [det, tru] = zeroCrossings(r, 0), t = r.t.map((x) => x * 1000), Vh = r.P.Vdc / 2;
        const we = r.wm * r.P.poles / 2;
        const lay = sub(2, 1, { titles: ["a상 단자 전압 va 와 Vdc/2 (가상 중성점)", "a상 역기전력 ea 와 개방 구간"], sharex: true }); Object.assign(lay.xaxis2, tx("시간 [ms] (전기각 1주기)"));
        lay.shapes = [hline(Vh, 1, { color: "#16a34a", dash: "dash" })];
        for (const td of det) for (const nn of [1, 2]) lay.shapes.push(vline(td * 1000, nn, { color: "#16a34a", dash: "solid", width: 2 }), vline((td + M.rad(30) / we) * 1000, nn, { color: "#e76f51", dash: "dash" }));
        draw(p, [line(t, r.v[0], "va (측정)", { color: COLP.a, width: 1 }), line(t, r.e[0].map((x) => x + Vh), "ea + Vdc/2", { color: "#111", dash: "dot" }),
          line(t, r.e[0], "ea", { n: 2, color: COLP.a }), line(t, r.fl[0].map((f) => (f ? 0 : NaN)), "개방 구간 (전류 0)", { n: 2, color: "#16a34a", width: 8 }),
          pts(tru.map((x) => x * 1000), tru.map(() => 0), "실제 영점", { n: 2, symbol: "x", color: "#111" })], Object.assign(lay, { legend: { orientation: "v", x: 1.01, y: 1 }, margin: { r: 130, b: 40 } }));
        metric(m[0], "검출한 영점 수", String(det.length));
        if (det.length && tru.length) { let e = Infinity; for (const d of det) for (const q of tru) e = Math.min(e, Math.abs(d - q)); metric(m[1], "검출 오차 (전기각)", `${M.deg(e * we).toFixed(1)}°`); } else metric(m[1], "검출 오차", "—");
        metric(m[2], "영점 → 상 전환 지연", "30° (주황 점선)");
      });
    });
  };

  const api = Object.assign(T, { _calc: { trap, hall, sector, stepInfo, simulate, drive, zeroCrossings, ripple, METHODS } });
  root.LabCh3 = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
