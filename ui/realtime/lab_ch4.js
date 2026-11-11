/* 강의 실습 4장 교류 전동기 (브라우저 계산). 계산식은 lectures/ch4.py 와 같음. */
(function (root) {
  "use strict";
  const { M, C, cx, metric, table, sub, hline, vline, vrect, topLabel, line, pts, draw, tx, svg, COL, el } = root.Lab;
  const RPM = M.RPM, COLP = { a: "#d62828", b: "#2a9d8f", c: "#1d4ed8" }, PH = ["a", "b", "c"];
  const IM = { V: 380, f: 60, P: 4, Rs: 0.5, Xls: 2 * Math.PI * 60 * 3.2e-3, Rr: 0.4, Xlr: 2 * Math.PI * 60 * 3.2e-3, Xm: 2 * Math.PI * 60 * 106e-3, Rc: 0, I_rated: 13 };

  // ---------------------------------------------------------------- 유도 전동기 등가회로
  function circuit(s, Mo, V, f) {
    Mo = Mo || IM; V = V === undefined ? Mo.V : V; f = f === undefined ? Mo.f : f;
    const k = f / Mo.f, Xls = Mo.Xls * k, Xlr = Mo.Xlr * k, Xm = Mo.Xm * k;
    if (Math.abs(s) < 1e-9) s = 1e-9;
    const Vph = V / Math.sqrt(3), Zs = new C(Mo.Rs, Xls), Zr = new C(Mo.Rr / s, Xlr), Zm = new C(0, Xm);
    const Zp = Zm.mul(Zr).div(Zm.add(Zr)), I1 = new C(Vph).div(Zs.add(Zp)), E1 = I1.mul(Zp), I2 = E1.div(Zr);
    const ws = 2 * Math.PI * f / (Mo.P / 2), I2a = I2.abs(), Pag = 3 * I2a * I2a * Mo.Rr / s, Pin = 3 * Vph * I1.re;
    const Pcu1 = 3 * I1.abs() ** 2 * Mo.Rs, Pmech = (1 - s) * Pag;
    return { I1, I2, Pin, Pcu1, Pag, Pcu2: s * Pag, Pmech, T: Pag / ws, pf: Math.cos(I1.arg()), eta: Pin > 0 && Pmech > 0 ? Pmech / Pin : NaN, n: (1 - s) * 120 * f / Mo.P, ws };
  }
  function maxTorque(Mo, V, f) {
    Mo = Mo || IM; V = V === undefined ? Mo.V : V; f = f === undefined ? Mo.f : f;
    const k = f / Mo.f, Zs = new C(Mo.Rs, Mo.Xls * k), Zm = new C(0, Mo.Xm * k);
    const Vth = V / Math.sqrt(3) * Zm.div(Zs.add(Zm)).abs(), Zth = Zs.mul(Zm).div(Zs.add(Zm));
    const R = Zth.re, X = Zth.im + Mo.Xlr * k, ws = 2 * Math.PI * f / (Mo.P / 2), rt = Math.hypot(R, X);
    return [3 * Vth * Vth / (2 * ws * (R + rt)), Mo.Rr / rt];
  }
  function opPoints(Mo, loadf, V, f, n = 1200) {
    f = f === undefined ? Mo.f : f;
    const s = M.linspace(1, 1e-4, n), out = [];
    let prev = null, prevN = null;
    for (const sk of s) {
      const r = circuit(sk, Mo, V, f), d = r.T - loadf(r.n);
      if (prev !== null && (d === 0 || prev * d < 0)) { const a = prev / (prev - d); out.push([prevN + a * (r.n - prevN), d < prev]); }
      prev = d; prevN = r.n;
    }
    return out;
  }
  function doubleCage(s, Mo, Ro, Xo, Ri, Xi) {
    const Vph = Mo.V / Math.sqrt(3), Zs = new C(Mo.Rs, Mo.Xls), Z1 = new C(Ro / s, Xo), Z2 = new C(Ri / s, Xi);
    const Zpar = Z1.mul(Z2).div(Z1.add(Z2)), Zr = new C(0, Mo.Xlr * 0.5).add(Zpar), Zm = new C(0, Mo.Xm);
    const I1 = new C(Vph).div(Zs.add(Zm.mul(Zr).div(Zm.add(Zr)))), I2 = I1.mul(Zm).div(Zm.add(Zr)), ws = 2 * Math.PI * Mo.f / (Mo.P / 2);
    return [3 * I2.abs() ** 2 * Zpar.re / ws, I1.abs()];
  }
  const NEMA = { "A급 (일반, 저슬립)": { single: 0.3 }, "B급 (표준, 저기동전류)": { Ro: 1.2, Xo: 0.8, Ri: 0.32, Xi: 1.6 },
    "C급 (고기동토크)": { Ro: 2.2, Xo: 0.5, Ri: 0.35, Xi: 3.0 }, "D급 (고저항, 고슬립)": { single: 1.9 } };
  const nema = (cls, s) => { const p = NEMA[cls]; if (p.single) return circuit(s, Object.assign({}, IM, { Rr: p.single })).T; return doubleCage(s, IM, p.Ro, p.Xo, p.Ri, p.Xi)[0]; };
  function deepBar(fr, h = 25, rho = 2.8e-8) {
    const d = Math.sqrt(2 * rho / (2 * Math.PI * Math.max(fr, 1e-6) * 4e-7 * Math.PI)), x = Math.min(h * 1e-3 / d, 50);
    return x * (Math.sinh(2 * x) + Math.sin(2 * x)) / (Math.cosh(2 * x) - Math.cos(2 * x));
  }
  function runTests(Mo = IM) {
    const nl = circuit(1e-4, Mo), Iu = circuit(1, Mo, 1).I1.abs(), Vbl = Mo.I_rated / Iu, bl = circuit(1, Mo, Vbl);
    return { R_ll: 2 * Mo.Rs, V_nl: Mo.V, I_nl: nl.I1.abs(), P_nl: nl.Pin, V_bl: Vbl, I_bl: bl.I1.abs(), P_bl: bl.Pin };
  }
  function estimate(m, split = 0.5) {
    const Rs = m.R_ll / 2, Zbl = m.V_bl / Math.sqrt(3) / m.I_bl, Rbl = m.P_bl / (3 * m.I_bl ** 2), Xbl = Math.sqrt(Math.max(Zbl ** 2 - Rbl ** 2, 0));
    const Znl = m.V_nl / Math.sqrt(3) / m.I_nl, Rnl = m.P_nl / (3 * m.I_nl ** 2), Xnl = Math.sqrt(Math.max(Znl ** 2 - Rnl ** 2, 0));
    return { Rs, Rr: Rbl - Rs, Xls: split * Xbl, Xlr: (1 - split) * Xbl, Xm: Xnl - split * Xbl };
  }
  const vfV = (f, boost = 0) => Math.min(boost + (IM.V - boost) * f / IM.f, IM.V);
  function regions(Ilim, npts = 60) {
    const pp = IM.P / 2, nsb = 120 * IM.f / IM.P, n = M.linspace(nsb * 0.02, nsb * 3, npts), fr = M.linspace(0.05, 30, 300);
    const R = { n, T: [], V: [], I: [], f: [], sf: [] };
    for (const nk of n) {
      let best = [0, 0, 0, 0, 0];
      for (const frk of fr) { const f = nk * pp / 60 + frk, V = Math.min(IM.V * f / IM.f, IM.V), r = circuit(frk / f, IM, V, f), I1 = r.I1.abs(); if (I1 <= Ilim && r.T > best[0]) best = [r.T, V, I1, f, frk]; }
      R.T.push(best[0]); R.V.push(best[1]); R.I.push(best[2]); R.f.push(best[3]); R.sf.push(best[4]);
    }
    R.P = R.T.map((T, k) => T * n[k] / 60 * 2 * Math.PI);
    return R;
  }
  function vfClosed(nref, TL, frmax, boost, tend = 3, h = 2e-3) {
    const pp = IM.P / 2, J = 0.1, Kp = 0.02, Ki = 0.2, n = Math.round(tend / h), R = { t: [], n: [], nref: [], fs: [], fr: [], T: [] };
    let wm = 0, x = 0;
    for (let k = 0; k < n; k++) {
      const t = k * h, nr = t >= 0.2 ? nref : 0, tl = t >= 2 ? TL : 0, nm = wm * RPM, e = nr - nm, fu = Kp * e + x, fr = M.clip(fu, -frmax, frmax);
      if (fu === fr) x += Ki * e * h;
      const fm = nm * pp / 60, fs = Math.max(fm + fr, 0.2), V = vfV(fs, boost), T = circuit((fs - fm) / fs, IM, V, fs).T;
      wm += h * (T - tl * Math.sign(Math.abs(wm) > 1e-3 ? wm : 1) - 0.002 * wm) / J;
      if (k % 3 === 0) { R.t.push(t); R.n.push(nm); R.nref.push(nr); R.fs.push(fs); R.fr.push(fr); R.T.push(T); }
    }
    return R;
  }
  // 동기 전동기
  function syncPhasor(Vs, Ef, d, Xd, Xq) {
    Xq = Xq === undefined ? Xd : Xq;
    const Efp = C.polar(Ef, -d);
    let I;
    if (Math.abs(Xd - Xq) < 1e-12) I = new C(Vs).sub(Efp).div(new C(0, Xd));
    else { const q = C.polar(1, -d), dd = q.mul(new C(0, -1)), V = new C(Vs), Vd = V.mul(dd.conj()).re, Vq = V.mul(q.conj()).re;
      const Id = (Vq - Ef) / Xd, Iq = -Vd / Xq; I = dd.scale(Id).add(q.scale(Iq)); }
    const S = new C(3 * Vs).mul(I.conj());
    return { I, Ef: Efp, pf: Math.cos(Math.atan2(I.im, I.re)), P: S.re, Q: S.im };
  }
  const syncTorque = (d, Vs, Ef, Xd, Xq, ws) => [3 / ws * Vs * Ef / Xd * Math.sin(d), 3 / ws * Vs * Vs * (Xd - Xq) / (2 * Xd * Xq) * Math.sin(2 * d)];
  // 회전자계
  function mmf(phi, t, f, poles, mode, unb) {
    const w = 2 * Math.PI * f, pp = poles / 2;
    let cur;
    if (mode.startsWith("한 상")) { const ia = Math.cos(w * t - Math.PI / 6); cur = [ia, 0, -ia]; }
    else { const amps = mode.startsWith("단상") ? [1, 0, 0] : [1, 1, mode.startsWith("불평형") ? unb : 1]; cur = [0, 1, 2].map((k) => amps[k] * Math.cos(w * t - 2 * Math.PI * k / 3)); }
    const F = [0, 1, 2].map((k) => phi.map((p) => cur[k] * Math.cos(pp * p - 2 * Math.PI * k / 3)));
    return [F, phi.map((_, i) => F[0][i] + F[1][i] + F[2][i]), cur];
  }
  function windingMMF(th, q, mode) {
    const slot = Math.PI / (3 * q);
    const phase = (sh) => th.map((t) => { let F = 0; for (let k = 0; k < q; k++) { const c0 = sh + (k - (q - 1) / 2) * slot; F += (Math.cos(t - c0) >= 0 ? 0.5 : -0.5) / q; } return F; });
    let F = phase(0);
    if (mode !== "a상만") { const b = phase(2 * Math.PI / 3), c = phase(4 * Math.PI / 3); F = F.map((v, i) => v - 0.5 * b[i] - 0.5 * c[i]); }
    const a1 = 2 * M.mean(F.map((v, i) => v * Math.cos(th[i]))), b1 = 2 * M.mean(F.map((v, i) => v * Math.sin(th[i])));
    const fund = th.map((t) => a1 * Math.cos(t) + b1 * Math.sin(t)), kd = Math.sin(q * slot / 2) / (q * Math.sin(slot / 2));
    const p1 = 0.5 * (a1 * a1 + b1 * b1), thd = Math.sqrt(Math.max(M.mean(F.map((v) => v * v)) - p1, 0)) / Math.sqrt(p1);
    return { F, fund, kd, thd };
  }
  const arago = (dv, sigma = 5.8e7, B = 0.5, t = 2e-3, vc = 40) => sigma * t * B * B * dv / (1 + (dv / vc) ** 2);

  // ---------------------------------------------------------------- 그림
  function eqSVG(vals) {
    const o = svg.start(560, 200), yT = 60, yB = 170;
    svg.circle(o, 20, yT, 5); svg.circle(o, 20, yB, 5); svg.text(o, 12, (yT + yB) / 2, "Vs", 13, "#222", "end");
    svg.line(o, 25, yT, 40, yT); svg.resistor(o, 40, yT, 120, yT); svg.inductor(o, 120, yT, 200, yT); svg.line(o, 200, yT, 330, yT);
    svg.inductor(o, 330, yT, 410, yT); svg.line(o, 410, yT, 440, yT); svg.resistor(o, 440, yT, 440, yB); svg.line(o, 25, yB, 440, yB);
    svg.inductor(o, 265, yT, 265, yB);
    svg.text(o, 80, yT - 22, `Rs ${vals.Rs}`, 12); svg.text(o, 160, yT - 22, `jXls ${vals.Xls}`, 12); svg.text(o, 370, yT - 22, `jXlr′ ${vals.Xlr}`, 12);
    svg.text(o, 285, (yT + yB) / 2, `jXm ${vals.Xm}`, 12, "#222", "start"); svg.text(o, 455, (yT + yB) / 2, vals.Rrs, 12, "#222", "start");
    svg.arrow(o, 40, yT - 42, 110, yT - 42); svg.text(o, 75, yT - 54, vals.I1, 12, "#d62828");
    svg.arrow(o, 330, yT - 42, 400, yT - 42); svg.text(o, 365, yT - 54, vals.I2, 12, "#d62828");
    svg.arrow(o, 248, yT + 20, 248, yB - 20); svg.text(o, 242, (yT + yB) / 2, vals.Im, 12, "#d62828", "end");
    return svg.done(o);
  }
  function phasorFig(items) {
    const tr = [], ann = []; let lim = 1;
    for (const [z, z0, name, col] of items) {
      ann.push({ x: z.re, y: z.im, ax: z0.re, ay: z0.im, xref: "x", yref: "y", axref: "x", ayref: "y", showarrow: true, arrowhead: 2, arrowsize: 1.3, arrowwidth: 2.4, arrowcolor: col, text: "" });
      ann.push({ x: z.re, y: z.im, text: `<b>${name}</b>`, showarrow: false, font: { color: col, size: 13 }, xshift: z.re >= z0.re ? 14 : -14, yshift: name.startsWith("I") ? -14 : 10 });
      lim = Math.max(lim, z.abs(), z0.abs());
    }
    const xs = [0], ys = [0]; for (const [z, z0] of items) xs.push(z.re, z0.re), ys.push(z.im, z0.im);
    const pad = 0.15 * lim, xr = [M.min(xs) - pad, M.max(xs) + pad], yr = [M.min(ys) - pad, M.max(ys) + pad];
    return { tr: [{ type: "scatter", x: [0], y: [0], mode: "markers", marker: { size: 4, color: "#333" }, showlegend: false }],
      lay: { annotations: ann, xaxis: { range: xr, showticklabels: false, showgrid: false, zeroline: true }, yaxis: { range: yr, showticklabels: false, showgrid: false, zeroline: true, scaleanchor: "x", constrain: "domain" }, showlegend: false, margin: { l: 10, r: 10, t: 10, b: 10 }, hovermode: false } };
  }

  // ---------------------------------------------------------------- 공통: 전동기 파라미터
  function imControls(s) {
    s.row(); s.check("custom", "유도 전동기 파라미터 직접 바꾸기 (기본 = 380 V, 60 Hz, 4극)", false, { all: true, wide: true });
    s.num("Rs", "Rs [Ω]", 0.01, 5, 0.05, 0.5, { all: true }); s.num("Rr", "Rr′ [Ω]", 0.01, 5, 0.05, 0.4, { all: true });
    s.num("Xls", "Xls [Ω]", 0.05, 10, 0.05, +IM.Xls.toFixed(3), { all: true }); s.num("Xlr", "Xlr′ [Ω]", 0.05, 10, 0.05, +IM.Xlr.toFixed(3), { all: true });
    s.num("Xm", "Xm [Ω]", 1, 200, 1, +IM.Xm.toFixed(2), { all: true }); s.select("P", "극수 P", [2, 4, 6, 8], 4, { all: true });
    s.end();
  }
  const imP = (v) => (v.custom ? Object.assign({}, IM, { Rs: v.Rs, Rr: v.Rr, Xls: v.Xls, Xlr: v.Xlr, Xm: v.Xm, P: +v.P }) : Object.assign({}, IM));

  // ---------------------------------------------------------------- 탭
  const T = {};

  T.structure = function (tab) {
    tab.section((s) => {
      s.h("아라고의 원판: 자석을 돌리면 구리 원판이 와전류 때문에 조금 느리게 따라 돎");
      s.row(); s.slider("vm", "자석 속도 [m/s] (원판 둘레 기준)", 0, 100, 1, 40);
      s.select("mat", "원판 재질", ["구리 (σ = 5.8×10⁷)", "알루미늄 (3.5×10⁷)", "스테인리스 (1.4×10⁶)", "플라스틱 (부도체)"], "구리 (σ = 5.8×10⁷)"); s.slider("bf", "마찰 제동 (상대값)", 0, 2, 0.05, 0.3);
      s.end(); const [c0, c1] = s.cols([3, 2]); s.into(c0); const p = s.plot(300); s.into(c1); const m = s.metrics(2);
      s.note("원판이 자석과 같은 속도가 되면 자속 변화가 없어 와전류·힘이 0 → 항상 조금 느리게 돎 = 유도 전동기의 슬립. 부도체는 와전류가 없어 돌지 않음.");
      const dv = M.linspace(0, 100, 300), F0 = arago(40);
      s.on((v) => {
        const sig = { "구": 5.8e7, "알": 3.5e7, "스": 1.4e6, "플": 0 }[v.mat[0]];
        let vd = 0; if (sig > 0) { let best = Infinity; for (let k = 0; k <= 2000; k++) { const x = v.vm * k / 2000, b = Math.abs(arago(v.vm - x, sig) / F0 - v.bf * x / 40); if (b < best) { best = b; vd = x; } } }
        draw(p, [line(dv, dv.map((x) => arago(x, sig) / F0), "와전류 힘 (상대 속도 = 슬립의 함수)"), pts([v.vm - vd], [arago(v.vm - vd, sig) / F0], "현재 운전점")],
          { xaxis: tx("자석과 원판의 상대 속도 Δv [m/s]"), yaxis: tx("원판을 끄는 힘 (상대값)") });
        metric(m[0], "원판 속도", `${vd.toFixed(1)} m/s`, `자석 ${v.vm} m/s 보다 ${(v.vm - vd).toFixed(1)} m/s 느림`);
        metric(m[1], "슬립 (vm − vd)/vm", v.vm > 0 ? `${((v.vm - vd) / v.vm * 100).toFixed(1)} %` : "—");
      });
    });
    tab.section((s) => {
      s.h("철손: 히스테리시스 손실 (루프 면적 × 주파수) 과 와전류 손실 (주파수² × 두께²)");
      s.row(); s.radio("mat2", "철심 재료", ["연자성체 (규소 강판)", "경자성체 (영구자석 재료)"], "연자성체 (규소 강판)"); s.slider("th", "강판 두께 [mm]", 0.1, 2, 0.05, 0.35);
      s.slider("fq", "주파수 [Hz]", 10, 400, 10, 60); s.slider("Bm", "최대 자속 밀도 [T]", 0.5, 1.8, 0.1, 1.4);
      s.end(); const p = s.plot(340);
      s.on((v) => {
        const Hc = v.mat2.startsWith("연") ? 40 : 600, H = M.linspace(-2000, 2000, 300), ff = M.linspace(1, 400, 200);
        const Ph = ff.map((f) => 0.02 * f * Math.pow(v.Bm, 1.8)), Pe = ff.map((f) => 0.6e-3 * (f * v.th) ** 2 * v.Bm ** 2);
        const lay = sub(1, 2, { titles: ["B–H 히스테리시스 루프 (면적 = 한 주기 손실)", "주파수에 따른 철손"] });
        Object.assign(lay.xaxis, tx("H [A/m]")); Object.assign(lay.yaxis, tx("B [T]")); Object.assign(lay.xaxis2, tx("주파수 [Hz]")); Object.assign(lay.yaxis2, tx("손실 [W/kg] (상대값)"));
        lay.shapes = [vline(v.fq, 2)];
        draw(p, [line(H, H.map((h) => 1.6 * Math.tanh((h - Hc) / 200)), "자화 증가", { color: "#d62828" }), line(H, H.map((h) => 1.6 * Math.tanh((h + Hc) / 200)), "자화 감소", { color: "#1d4ed8" }),
          line(ff, Ph, "히스테리시스 손실 ∝ f", { n: 2, color: "#2a9d8f" }), line(ff, Pe, "와전류 손실 ∝ f²·t²", { n: 2, color: "#e9c46a" }), line(ff, Ph.map((x, i) => x + Pe[i]), "철손 합", { n: 2, width: 3, color: "#264653" })], lay);
      });
    });
    tab.section((s) => {
      s.h("분포권: 슬롯에 나눠 감은 도체가 만드는 계단 모양 기자력 → 정현파에 가까워짐");
      const [c0, c1] = s.cols([1, 3]); s.into(c0); s.options("q", "매극 매상 슬롯 수 q", [1, 2, 3, 4, 6], 2); s.radio("wm", "전류", ["a상만", "3상 합성 (ia = 1, ib = ic = −½)"], "a상만"); const m = s.metrics(2);
      s.into(c1); const p = s.plot(300);
      const th = M.range(1440, (k) => k / 1440 * 2 * Math.PI), x = th.map(M.deg);
      s.on((v) => {
        const r = windingMMF(th, v.q, v.wm);
        draw(p, [line(x, r.F, "실제 기자력 (계단)", { shape: "hv" }), line(x, r.fund, "기본파 성분", { dash: "dot", color: "#d62828" })], { xaxis: Object.assign(tx("공극 위치 (전기각) [°]"), { dtick: 60 }) });
        metric(m[0], "분포 계수 kd", r.kd.toFixed(4)); metric(m[1], "고조파 비율 (THD)", `${(r.thd * 100).toFixed(1)} %`, "q 를 늘리면 줄어듦");
      });
    });
  };

  T.rotating = function (tab) {
    tab.section((s) => {
      s.row(); s.select("mode", "전류 조건", ["평형 3상", "불평형 (c상 크기 변경)", "한 상 단선 (b상 끊김)", "단상 (a상만)"], "평형 3상", { all: true });
      s.select("P", "극수 P", [2, 4, 6], 2, { all: true }); s.slider("unb", "c상 전류 크기 (불평형)", 0, 1.5, 0.1, 0.5, { all: true }); s.num("f", "주파수 f [Hz]", 1, 400, 5, 60, { all: true });
      s.end(); s.row(); const ts = s.slider("t", "시각 t (전원 전기각) [°]", 0, 360, 1, 0, { all: true });
      const btn = el("button", { text: "▶ 재생", style: "padding:6px 14px;border:1px solid #d9534f;color:#d9534f;background:#fff;border-radius:8px;cursor:pointer;align-self:flex-end;margin-bottom:6px" }, s.cur);
      let playing = false, last = 0;
      const tick = (now) => { if (!playing) return; if (now - last > 30) { last = now; ts.value = (+ts.value + 3) % 361; ts.dispatchEvent(new Event("input")); } requestAnimationFrame(tick); };
      btn.onclick = () => { playing = !playing; btn.textContent = playing ? "⏸ 멈춤" : "▶ 재생"; if (playing) requestAnimationFrame(tick); };
      s.end(); const [c0, c1] = s.cols([3, 2]); s.into(c0); const p = s.plot(380); s.into(c1); const pp = s.plot(380);
      s.end(); const pc = s.plot(260), m = s.metrics(3);
      const phi = M.linspace(0, 2 * Math.PI, 361), dg = phi.map(M.deg), tt = M.linspace(0, 360, 361);
      s.on((v) => {
        const t = M.rad(v.t) / (2 * Math.PI * 60), [F, Fs, cur] = mmf(phi, t, 60, +v.P, v.mode, v.unb);
        const tr = PH.map((q, k) => line(dg, F[k], `${q}상 기자력`, { color: COLP[q], dash: "dot", width: 1.4 }));
        tr.push(line(dg, Fs, "합성 기자력", { color: "#111", width: 3 }));
        draw(p, tr, { xaxis: Object.assign(tx("공극 둘레 위치 (기계각) [°]"), { dtick: 45 }), yaxis: Object.assign(tx("기자력 (단위값)"), { range: [-1.7, 1.7] }) });
        let km = 0; Fs.forEach((x, i) => { if (x > Fs[km]) km = i; });
        const pt = [{ type: "scatterpolar", r: [0, Math.max(Fs[km], 0)], theta: [0, dg[km]], mode: "lines+markers", line: { color: "#111", width: 4 }, name: "합성 기자력 최대 위치" }];
        PH.forEach((q, k) => pt.push({ type: "scatterpolar", r: [0, Math.abs(cur[k])], theta: [0, (cur[k] >= 0 ? 120 * k : 120 * k + 180) / (v.P / 2)], mode: "lines", line: { color: COLP[q], width: 2 }, name: `${q}상 성분`, showlegend: false }));
        draw(pp, pt, { polar: { radialaxis: { range: [0, 1.7], showticklabels: false } }, margin: { l: 30, r: 30, t: 20, b: 50 }, legend: { y: -0.05 } });
        draw(pc, PH.map((q, k) => line(tt, tt.map((x) => Math.cos(M.rad(x - 120 * k))), `i${q}`, { color: COLP[q] })),
          { shapes: [vline(v.t, 1, { color: "#111", dash: "solid", width: 2 })], xaxis: Object.assign(tx("전원 전기각 [°] (세로선 = 현재 시각)"), { dtick: 90 }) });
        metric(m[0], "동기 속도 ns = 120f/P", `${(120 * v.f / v.P).toFixed(0)} rpm`); metric(m[1], "전원 1주기 동안 회전", `기계각 ${(720 / v.P).toFixed(0)}°`, "2/P 바퀴");
        metric(m[2], "합성 기자력 크기 (평형)", "상 최대값의 1.5 배");
      });
    });
    tab.section((s) => {
      s.h("고정자 회전자계와 회전자 회전자계: 회전자 속도 nm + 슬립 속도 nr = 동기 속도 ns");
      const [c0, c1] = s.cols([1, 2]); s.into(c0); s.slider("sl", "슬립 s", 0.01, 0.5, 0.01, 0.1); const tq = s.slider("tq", "시각 (전원 주기 수)", 0, 4, 0.01, 1);
      const btn = el("button", { text: "▶ 재생", style: "padding:6px 14px;border:1px solid #d9534f;color:#d9534f;background:#fff;border-radius:8px;cursor:pointer" }, s.cur);
      let playing = false; const tick = () => { if (!playing) return; tq.value = (+tq.value + 0.01) % 4; tq.dispatchEvent(new Event("input")); requestAnimationFrame(tick); };
      btn.onclick = () => { playing = !playing; btn.textContent = playing ? "⏸ 멈춤" : "▶ 재생"; if (playing) requestAnimationFrame(tick); };
      s.note("Fs 와 Fr 은 같이 돌아 사이 각이 일정 (지속적인 토크), 회전자 표시(별)는 그보다 느리게 뒤처짐.");
      s.into(c1); const p = s.plot(340);
      s.on((v) => {
        const as = 360 * v.tq, am = 360 * v.tq * (1 - v.sl), ar = am + 360 * v.tq * v.sl - 105;
        draw(p, [{ type: "scatterpolar", r: [0, 1], theta: [0, as], mode: "lines+markers", line: { color: "#1d4ed8", width: 6 }, name: "고정자 회전자계 Fs (ns)" },
          { type: "scatterpolar", r: [0, 0.75], theta: [0, ar], mode: "lines+markers", line: { color: "#d62828", width: 6 }, name: "회전자 회전자계 Fr (nm + nr)" },
          { type: "scatterpolar", r: [0.95], theta: [am], mode: "markers", marker: { size: 14, color: "#e9c46a", symbol: "star" }, name: "회전자 표시 (nm)" }],
          { polar: { radialaxis: { visible: false, range: [0, 1.05] } }, margin: { l: 30, r: 30, t: 20, b: 60 }, legend: { y: -0.08 } });
      });
    });
  };

  T.emf = function (tab) {
    tab.section((s) => {
      s.row(); s.slider("Bmax", "최대 공극 자속 밀도 Bmax [T]", 0.3, 1.2, 0.05, 0.8); s.slider("lr", "철심 길이 l × 반지름 r [cm²]", 20, 400, 10, 120);
      s.slider("N", "상당 직렬 턴 수 N", 20, 300, 10, 100); s.slider("fs", "주파수 f [Hz]", 10, 120, 5, 60);
      s.end(); const p = s.plot(320), m = s.metrics(3);
      s.on((v) => {
        const phi = 2 * v.Bmax * v.lr * 1e-4, Kw = 0.92, E = 4.44 * v.fs * v.N * phi * Kw, th = M.linspace(0, 360, 361), t = M.linspace(0, 2 / v.fs, 300), tm = t.map((x) => x * 1000);
        const lay = sub(1, 3, { titles: ["공극 자속 밀도 B(θ) = Bmax cosθ", "a상 쇄교 자속 λa(t)", "유기 기전력 ea(t) = −dλa/dt"] });
        Object.assign(lay.xaxis, tx("θ [°]")); Object.assign(lay.xaxis2, tx("시간 [ms]")); Object.assign(lay.xaxis3, tx("시간 [ms]"));
        const tr = [line(th, th.map((d) => v.Bmax * Math.cos(M.rad(d))), "B(θ)"), line(tm, t.map((x) => v.N * phi * Kw * Math.cos(2 * Math.PI * v.fs * x)), "λa", { n: 2, color: "#7c3aed" })];
        PH.forEach((q, k) => tr.push(line(tm, t.map((x) => E * Math.SQRT2 * Math.sin(2 * Math.PI * v.fs * x - 2 * Math.PI * k / 3)), `e${q}`, { n: 3, color: COLP[q] })));
        draw(p, tr, lay);
        metric(m[0], "극당 자속 φ = 2·Bmax·l·r", `${(phi * 1000).toFixed(2)} mWb`); metric(m[1], "유기 기전력 실효값 E = 4.44 f N φ Kw", `${E.toFixed(1)} V`, `권선 계수 Kw = ${Kw}`);
        metric(m[2], "공극 자속 ∝ E / f", `${(E / v.fs).toFixed(2)} V/Hz`, "V/f 를 일정하게 하면 자속 일정");
      });
    });
    tab.section((s) => {
      s.h("회전자 유기 기전력과 주파수: 슬립에 비례 (정지 시 최대, 동기 속도에서 0)");
      const p = s.plot(280); s.row(); s.slider("sv", "슬립 s", 0.005, 1, 0.005, 0.03); s.end(); const m = s.metrics(2);
      const ns = 1800, n = M.linspace(0, ns, 200);
      s.on((v) => {
        const lay = sub(1, 2, { titles: ["회전자 기전력 Er = s·Er0 (상대값)", "회전자 주파수 fr = s·f [Hz]"] }); Object.assign(lay.xaxis, tx("회전자 속도 [rpm]")); Object.assign(lay.xaxis2, tx("회전자 속도 [rpm]"));
        lay.shapes = [vline((1 - v.sv) * ns, 1, { color: "#d62828" }), vline((1 - v.sv) * ns, 2, { color: "#d62828" })];
        draw(p, [line(n, n.map((x) => 1 - x / ns), "Er"), line(n, n.map((x) => (1 - x / ns) * 60), "fr", { n: 2, color: "#2a9d8f" })], Object.assign(lay, { showlegend: false, margin: { b: 40 } }));
        const I1 = new C(v.sv * 100).div(new C(IM.Rr, v.sv * IM.Xlr)), I2 = new C(100).div(new C(IM.Rr / v.sv, IM.Xlr));
        metric(m[0], "실제 회전자 회로 sE/(Rr + j s Xr)", `${I1.abs().toFixed(2)} A`, `주파수 fr = ${(v.sv * 60).toFixed(2)} Hz`);
        metric(m[1], "고정자 주파수로 변환 E/(Rr/s + jXr)", `${I2.abs().toFixed(2)} A`, "크기가 같음 → 등가회로에 Rr/s 로 그림");
      });
    });
  };

  T.equivalent = function (tab) {
    tab.section((s) => imControls(s));
    tab.section((s) => {
      const [c0, c1] = s.cols([1, 2]); s.into(c0); s.slider("nr", "회전 속도 [% 동기 속도]", 0, 100, 0.25, 97); const m = s.metrics(4); s.into(c1); const box = s.svg(220);
      s.end(); const p = s.plot(320);
      s.on((v) => {
        const Mo = imP(v), ns = 120 * Mo.f / Mo.P, sl = Math.max(1 - v.nr / 100, 1e-4), r = circuit(sl, Mo);
        box.innerHTML = eqSVG({ Rs: Mo.Rs.toFixed(2), Xls: Mo.Xls.toFixed(2), Xlr: Mo.Xlr.toFixed(2), Xm: Mo.Xm.toFixed(1), Rrs: `Rr′/s = ${(Mo.Rr / sl).toFixed(2)} Ω`,
          I1: `I1 = ${r.I1.abs().toFixed(1)} A`, I2: `I2′ = ${r.I2.abs().toFixed(1)} A`, Im: `Im = ${r.I1.sub(r.I2).abs().toFixed(1)} A` });
        metric(m[0], "속도 · 슬립", `${(v.nr / 100 * ns).toFixed(0)} rpm`, `s = ${sl.toFixed(4)}`); metric(m[1], "토크", `${r.T.toFixed(1)} N·m`);
        metric(m[2], "역률", `${r.pf.toFixed(3)} (지상)`); metric(m[3], "효율", isFinite(r.eta) ? `${(r.eta * 100).toFixed(1)} %` : "—");
        const labs = ["입력 전력", "고정자 동손", "공극 전력", "회전자 동손 s·Pag", "기계적 출력 (1−s)Pag"], vals = [r.Pin, r.Pcu1, r.Pag, r.Pcu2, r.Pmech].map((x) => x / 1000);
        draw(p, [{ type: "bar", x: labs, y: vals, marker: { color: ["#264653", "#e76f51", "#2a9d8f", "#e76f51", "#e9c46a"] }, text: vals.map((x) => `${x.toFixed(2)} kW`), textposition: "outside", showlegend: false }],
          { yaxis: tx("kW"), showlegend: false, margin: { b: 40 }, hovermode: false });
      });
    });
  };

  T.characteristics = function (tab) {
    tab.section((s) => imControls(s));
    tab.section((s) => {
      s.row(); s.select("load", "부하", ["일정 토크", "속도 제곱 (팬·펌프)", "없음"], "일정 토크"); s.slider("TL", "부하 토크 (동기 속도 기준) [N·m]", 0, 150, 5, 50); s.slider("Vr", "전압 [% 정격]", 50, 110, 5, 100);
      s.end(); const p = s.plot(440), m = s.metrics(4);
      s.on((v) => {
        const Mo = imP(v), ns = 120 * Mo.f / Mo.P, V = Mo.V * v.Vr / 100, sl = M.linspace(2, -1, 900).filter((x) => Math.abs(x) > 1e-4), R = sl.map((x) => circuit(x, Mo, V));
        const n = R.map((r) => r.n), [Tmax, smax] = maxTorque(Mo, V);
        const lf = v.load === "일정 토크" ? (x) => v.TL : v.load === "없음" ? () => 0 : (x) => v.TL * (x / ns) ** 2;
        const lay = sub(1, 2, { titles: ["토크–속도 특성", "전류·역률·효율 (전동기 영역)"], colw: [0.6, 0.4] });
        const tr = [line(n, R.map((r) => r.T), "전동기 토크", { color: "#264653", width: 3 })];
        if (v.load !== "없음") {
          const nn = M.linspace(0, ns, 200); tr.push(line(nn, nn.map(lf), "부하 토크", { color: "#e76f51" }));
          for (const [nk, stb] of opPoints(Mo, lf, V)) tr.push(pts([nk], [lf(nk)], stb ? "안정 운전점" : "불안정 운전점", { color: stb ? "#16a34a" : "#d62828", symbol: stb ? "circle" : "x", size: 13 }));
        }
        tr.push(pts([(1 - smax) * ns], [Tmax], "최대 토크", { color: "#111", size: 10, text: ["최대 토크"], textpos: "top center" }));
        const mi = sl.map((x, i) => (x > 0 && x <= 1 ? i : -1)).filter((i) => i >= 0), nm = mi.map((i) => n[i]);
        tr.push(line(nm, mi.map((i) => R[i].I1.abs()), "고정자 전류 [A]", { n: 2, color: "#1d4ed8" }), line(nm, mi.map((i) => R[i].I2.abs()), "회전자 전류 [A]", { n: 2, dash: "dash", color: "#7c3aed" }),
          line(nm, mi.map((i) => (1 - sl[i]) * 100), "이상 효율 1 − s [%]", { n: 2, dash: "dot", color: "#94a3b8" }), line(nm, mi.map((i) => R[i].pf * 100), "역률 [%]", { n: 2, color: "#e9c46a" }),
          line(nm, mi.map((i) => R[i].eta * 100), "효율 [%]", { n: 2, color: "#2a9d8f" }));
        lay.shapes = [vrect(-ns, 0, 1, "rgba(29,78,216,0.08)"), vrect(0, ns, 1, "rgba(42,157,143,0.08)"), vrect(ns, 2 * ns, 1, "rgba(231,111,81,0.08)")];
        lay.annotations.push(topLabel(-ns / 2, "플러깅 (s > 1)"), topLabel(ns / 2, "전동기 (0 < s < 1)"), topLabel(1.5 * ns, "발전기 (s < 0)"));
        Object.assign(lay.xaxis, tx("속도 [rpm]")); Object.assign(lay.xaxis2, tx("속도 [rpm]")); Object.assign(lay.yaxis, tx("토크 [N·m]"));
        draw(p, tr, lay);
        const st = circuit(1, Mo, V);
        metric(m[0], "최대 토크", `${Tmax.toFixed(0)} N·m`, `슬립 ${smax.toFixed(3)} (${((1 - smax) * ns).toFixed(0)} rpm)`); metric(m[1], "기동 토크 (s = 1)", `${st.T.toFixed(0)} N·m`);
        metric(m[2], "기동 전류", `${st.I1.abs().toFixed(0)} A`); metric(m[3], "동기 속도", `${ns.toFixed(0)} rpm`);
      });
    });
    tab.section((s) => {
      s.h("토크 식의 근사: 동기 속도 근처는 슬립에 비례, 저속은 슬립에 반비례");
      const p = s.plot(300);
      s.on((v) => {
        const Mo = imP(v), ns = 120 * Mo.f / Mo.P, V = Mo.V * v.Vr / 100, Vph = V / Math.sqrt(3), ws = 2 * Math.PI * Mo.f / (Mo.P / 2), sp = M.linspace(0.002, 1, 300), n = sp.map((x) => (1 - x) * ns);
        const Tmax = maxTorque(Mo, V)[0];
        draw(p, [line(n, sp.map((x) => circuit(x, Mo, V).T), "등가회로 토크", { width: 3 }), line(n, sp.map((x) => 3 / ws * Vph * Vph / Mo.Rr * x), "작은 슬립 근사 T ≈ 3Vs²s/(ωs Rr) (∝ s)", { dash: "dot", color: "#d62828" }),
          line(n, sp.map((x) => 3 / ws * Vph * Vph * Mo.Rr / ((Mo.Xls + Mo.Xlr) ** 2 * x)), "큰 슬립 근사 T ≈ 3Vs²Rr/(ωs X² s) (∝ 1/s)", { dash: "dash", color: "#2a9d8f" })],
          { xaxis: tx("속도 [rpm]"), yaxis: Object.assign(tx("토크 [N·m]"), { range: [0, Tmax * 1.4] }) });
      });
    });
    tab.section((s) => {
      s.h("교재 예제 1 (5 HP, 220 V, 60 Hz, 1750 r/min, 4극, 역률 0.85, 효율 90 %) · 예제 2 (팬 부하 TL = 0.1ωm, Rr = 0.379 Ω)");
      s.row(); s.num("hp", "출력 [HP]", 0.5, 100, 0.5, 5); s.num("VL", "선간 전압 [V]", 100, 1000, 10, 220); s.num("nrt", "정격 속도 [r/min]", 100, 3600, 10, 1750); s.num("pf", "역률", 0.5, 1, 0.01, 0.85); s.num("Rr2", "예제 2: Rr [Ω]", 0.05, 5, 0.001, 0.379);
      s.end(); const tb = s.table(), nt = s.note();
      s.on((v) => {
        const Pm = v.hp * 746, Ir = Pm / (Math.sqrt(3) * v.VL * v.pf * 0.9), ns1 = 1800, s1 = (ns1 - v.nrt) / ns1;
        table(tb, ["항목", "값"], [["① 정격 전류 = Pm / (√3·V·cosθ·η)", `${Ir.toFixed(1)} A`], ["② 동기 속도 120f/P", `${ns1} r/min`], ["② 정격 슬립", s1.toFixed(4)],
          ["③ 슬립 주파수 fr = s·f", `${(s1 * 60).toFixed(3)} Hz`], ["④ 정격 토크 Pm/ωm", `${(Pm / (v.nrt / 60 * 2 * Math.PI)).toFixed(2)} N·m`]]);
        const ws2 = 60 * Math.PI; let best = Infinity, wsol = 0;
        for (let k = 0; k <= 20000; k++) { const w = 150 + (ws2 - 1e-3 - 150) * k / 20000, Tm = 3 / ws2 * (220 / Math.sqrt(3)) ** 2 / v.Rr2 * (ws2 - w) / ws2, d = Math.abs(Tm - 0.1 * w); if (d < best) { best = d; wsol = w; } }
        nt.innerHTML = `예제 2: 3/ωs·Vs²/Rr·(ωs − ωm)/ωs = 0.1·ωm 을 풀면 <b>ωm = ${wsol.toFixed(1)} rad/s = ${(wsol * RPM).toFixed(1)} r/min</b> (교재: 183.4 rad/s, 1751.3 r/min)`;
      });
    });
  };

  T.rotor = function (tab) {
    tab.section((s) => {
      s.row(); s.slider("Ro", "바깥 도체 저항 [Ω]", 0.5, 5, 0.1, 2); s.slider("Xo", "바깥 도체 리액턴스 [Ω]", 0.1, 3, 0.1, 0.6); s.slider("Ri", "안쪽 도체 저항 [Ω]", 0.1, 1, 0.05, 0.3); s.slider("Xi", "안쪽 도체 리액턴스 [Ω]", 0.5, 8, 0.1, 3);
      s.end(); const p = s.plot(380);
      const sl = M.linspace(1, 0.002, 300), n = sl.map((x) => (1 - x) * 1800);
      s.on((v) => {
        const lay = sub(1, 2, { titles: ["토크–속도", "전류–속도"] }), tr = [];
        [["일반 농형 (저저항 0.4 Ω)", 0.4, "#264653"], ["고저항 농형 (1.6 Ω)", 1.6, "#e76f51"]].forEach(([lab, Rr, c]) => { const R = sl.map((x) => circuit(x, Object.assign({}, IM, { Rr })));
          tr.push(line(n, R.map((r) => r.T), lab, { color: c }), line(n, R.map((r) => r.I1.abs()), "", { color: c, n: 2, legend: false })); });
        const D = sl.map((x) => doubleCage(x, IM, v.Ro, v.Xo, v.Ri, v.Xi));
        tr.push(line(n, D.map((d) => d[0]), "2중 농형", { color: "#2a9d8f", width: 3 }), line(n, D.map((d) => d[1]), "", { color: "#2a9d8f", width: 3, n: 2, legend: false }));
        Object.assign(lay.xaxis, tx("속도 [rpm]")); Object.assign(lay.xaxis2, tx("속도 [rpm]"));
        draw(p, tr, lay);
      });
    });
    tab.section((s) => {
      s.h("심구형 도체: 회전자 주파수가 높을수록(기동 시) 유효 저항이 커짐 (표피 효과)");
      const [c0, c1] = s.cols([1, 3]); s.into(c0); s.slider("hb", "도체 깊이 [mm]", 5, 50, 1, 25); s.into(c1); const p = s.plot(280);
      const fr = M.linspace(0.1, 60, 300);
      s.on((v) => draw(p, [line(fr, fr.map((f) => deepBar(f, v.hb)), "R_ac / R_dc")], { shapes: [vrect(0, 3, 1, "rgba(42,157,143,0.12)"), vline(60, 1)],
        annotations: [topLabel(1.5, "정상 운전 (1~3 Hz)"), topLabel(57, "기동 시 (60 Hz)")], xaxis: tx("회전자 주파수 fr [Hz]"), yaxis: tx("저항비 R_ac / R_dc"), showlegend: false, margin: { b: 40 } }));
    });
    tab.section((s) => {
      s.h("NEMA 형식별 토크–속도 특성 (A·B·C·D 급)");
      const p = s.plot(320), sl = M.linspace(1, 0.002, 300), n = sl.map((x) => (1 - x) * 1800);
      draw(p, Object.keys(NEMA).map((c, i) => line(n, sl.map((x) => nema(c, x)), c, { color: COL[i] })), { xaxis: tx("속도 [rpm]"), yaxis: tx("토크 [N·m]") });
    });
  };

  T.tests = function (tab) {
    const meas = runTests();
    tab.section((s) => {
      s.note("기준 전동기(파라미터를 알고 있는 전동기)로 세 가지 시험을 <b>가상으로</b> 해서 측정값을 만들고, 교재 방법으로 등가회로 정수를 다시 구합니다. 측정값을 직접 바꿔 넣어 볼 수도 있습니다.");
      s.row(); s.num("R_ll", "① 단자 사이 직류 저항 [Ω]", 0.01, 20, 0.01, +meas.R_ll.toFixed(3));
      s.num("V_nl", "② 무부하: 선간 전압 [V]", 10, 1000, 1, +meas.V_nl.toFixed(1)); s.num("I_nl", "② 무부하: 상전류 [A]", 0.1, 100, 0.01, +meas.I_nl.toFixed(3)); s.num("P_nl", "② 무부하: 3상 입력 전력 [W]", 0, 10000, 1, +meas.P_nl.toFixed(1));
      s.end(); s.row(); s.num("V_bl", "③ 구속: 선간 전압 [V]", 1, 1000, 0.5, +meas.V_bl.toFixed(2)); s.num("I_bl", "③ 구속: 상전류 [A]", 0.1, 200, 0.1, +meas.I_bl.toFixed(2));
      s.num("P_bl", "③ 구속: 3상 입력 전력 [W]", 1, 50000, 1, +meas.P_bl.toFixed(1)); s.slider("split", "Xls : Xlr′ 분배 (Xls 비율, NEMA A·D 0.5, B 0.4, C 0.3)", 0.3, 0.7, 0.05, 0.5);
      s.end(); const tb = s.table();
      s.on((v) => {
        const e = estimate(v, v.split), keys = [["Rs", "Rs [Ω]"], ["Rr", "Rr′ [Ω]"], ["Xls", "Xls [Ω]"], ["Xlr", "Xlr′ [Ω]"], ["Xm", "Xm [Ω]"]];
        table(tb, ["정수", "시험으로 구한 값", "기준 전동기 실제 값", "오차"], keys.map(([k, lab]) => [lab, e[k].toFixed(3), IM[k].toFixed(3), `${((e[k] / IM[k] - 1) * 100 >= 0 ? "+" : "")}${((e[k] / IM[k] - 1) * 100).toFixed(1)} %`]));
      });
    });
  };

  T.speed = function (tab) {
    tab.section((s) => {
      const [c0, c1] = s.cols([1, 1]); s.into(c0); s.radio("m", "방법", ["고정자 전압 제어", "회전자 저항 제어 (권선형)", "주파수 제어 (전압 일정)", "V/f 일정 제어"], "V/f 일정 제어");
      s.into(c1); s.slider("TL", "부하 토크 (동기 속도에서) [N·m]", 0, 80, 5, 40); s.radio("lt", "부하 종류", ["일정 토크", "팬·펌프 (속도 제곱)"], "일정 토크", { horiz: true }); s.slider("bst", "V/f 저속 전압 부스트 [V]", 0, 40, 2, 0, { all: true });
      s.end(); const p = s.plot(380), tb = s.table();
      const sl = M.linspace(1, 0.0005, 400);
      s.on((v) => {
        let cases;
        if (v.m.startsWith("고정자")) cases = [100, 85, 70, 55].map((k) => [`V = ${k}%`, { V: IM.V * k / 100 }, IM.f]);
        else if (v.m.startsWith("회전자")) cases = [0.4, 1, 2, 4].map((k) => [`Rr′ = ${k} Ω`, { Rr: k }, IM.f]);
        else if (v.m.startsWith("주파수")) cases = [20, 30, 40, 50, 60, 70].map((k) => [`f = ${k} Hz`, {}, k]);
        else cases = [10, 20, 30, 40, 50, 60].map((k) => [`f = ${k} Hz, V = ${vfV(k, v.bst).toFixed(0)} V`, { V: vfV(k, v.bst) }, k]);
        const lf = v.lt === "일정 토크" ? () => v.TL : (x) => v.TL * (x / 1800) ** 2, tr = [], rows = [];
        cases.forEach(([lab, kw, f], i) => {
          const Mo = Object.assign({}, IM, kw), R = sl.map((x) => circuit(x, Mo, Mo.V, f));
          tr.push(line(R.map((r) => r.n), R.map((r) => r.T), lab, { color: COL[i] }));
          const ptsS = opPoints(Mo, lf, Mo.V, f, 600).filter((q) => q[1]), ns = 120 * f / IM.P;
          if (ptsS.length) { const nk = ptsS[ptsS.length - 1][0]; tr.push(pts([nk], [lf(nk)], "", { color: COL[i], legend: false })); rows.push([lab, nk.toFixed(0), `${((1 - nk / ns) * 100).toFixed(1)} %`]); }
          else rows.push([lab, "정지 (토크 부족)", "—"]);
        });
        const nn = M.linspace(0, 2250, 200); tr.push(line(nn, nn.map(lf), "부하 토크", { color: "#999", dash: "dash" }));
        draw(p, tr, { xaxis: Object.assign(tx("속도 [rpm]"), { rangemode: "tozero" }), yaxis: Object.assign(tx("토크 [N·m]"), { rangemode: "tozero" }) });
        table(tb, ["조건", "운전 속도 [rpm]", "슬립"], rows);
      });
    });
    tab.section((s) => {
      s.h("V/f 패턴과 저속 전압 부스트");
      const p = s.plot(260); s.note("저주파에서는 고정자 저항 전압 강하 비율이 커 자속이 줄어듦 → 전압을 조금 올려(부스트) 토크를 보완. 위 'V/f 일정 제어' 에서 부스트를 올려 10 Hz 곡선을 비교해 보세요.");
      const fv = M.linspace(0, 80, 200);
      s.on((v) => draw(p, [line(fv, fv.map((f) => vfV(f, 0)), "V/f 일정"), line(fv, fv.map((f) => vfV(f, Math.max(v.bst, 20))), `부스트 ${Math.max(v.bst, 20)} V`, { color: "#d62828" })],
        { xaxis: tx("고정자 주파수 [Hz]"), yaxis: tx("선간 전압 [V]") }));
    });
    tab.section((s) => {
      s.h("일정 V/f + 슬립 주파수 조절 폐루프 속도 제어 (fs* = fm + fr*)");
      s.row(); s.slider("nref", "속도 지령 [rpm]", 200, 1700, 50, 1200); s.slider("TLc", "2 s 에 거는 부하 [N·m]", 0, 80, 5, 40); s.slider("frm", "슬립 주파수 제한 [Hz]", 0.5, 5, 0.5, 3);
      s.end(); const p = s.plot(320); s.note("속도가 지령보다 낮으면 슬립 주파수를 키워 토크를 늘리고(제한값까지), 높으면 줄임 → 운전점이 토크 곡선을 갈아타며 이동 (교재 그림 4.45).");
      s.on((v) => {
        const r = vfClosed(v.nref, v.TLc, v.frm, v.bst), lay = sub(1, 3, { titles: ["속도 [rpm]", "주파수 fs, 슬립 주파수 fr [Hz]", "토크 [N·m]"] });
        for (const k of ["xaxis", "xaxis2", "xaxis3"]) Object.assign(lay[k], tx("시간 [s]"));
        draw(p, [line(r.t, r.nref, "지령", { dash: "dash", color: "#999" }), line(r.t, r.n, "속도"), line(r.t, r.fs, "fs", { n: 2, color: "#d62828" }), line(r.t, r.fr.map((x) => x * 10), "fr × 10", { n: 2, color: "#e9c46a" }),
          line(r.t, r.T, "토크", { n: 3, color: "#2a9d8f" })], lay);
      });
    });
    tab.section((s) => {
      s.h("교재 예제: 220 V, 60 Hz, 1750 r/min, 4극 전동기를 V/f 일정으로 운전");
      s.row(); s.slider("f50", "운전 주파수 [Hz]", 10, 60, 5, 50); s.end(); const nt = s.note();
      s.on((v) => { nt.innerHTML = `① 공급 전압 V = 220 × ${v.f50}/60 = <b>${(220 * v.f50 / 60).toFixed(2)} V</b> ② 전부하 슬립 속도 = 1800 − 1750 = 50 r/min (V/f 일정이면 그대로) → 동기 속도 ${120 * v.f50 / 4} r/min − 50 = <b>${120 * v.f50 / 4 - 50} r/min</b> (교재: 50 Hz 에서 183.33 V, 1450 r/min)`; });
    });
    tab.section((s) => {
      s.h("4.1.9 속도 영역: 정격 전류·정격 전압 안에서 낼 수 있는 최대 토크");
      s.row(); s.slider("Ilim", "전류 한계 [A]", 8, 30, 1, 13); s.end(); const p = s.plot(360);
      s.on((v) => {
        const R = regions(v.Ilim), nsb = 1800, mx = M.max(R.sf); let kb = R.sf.findIndex((x) => x >= 0.98 * mx); if (kb < 0) kb = R.n.length - 1;
        const nb = R.n[kb], nend = R.n[R.n.length - 1], lay = sub(1, 2, { titles: ["토크·출력", "전압·주파수·자속·전류"] });
        lay.shapes = [1, 2].flatMap((c) => [vrect(0, nsb, c, "rgba(42,157,143,0.08)"), vrect(nsb, nb, c, "rgba(233,196,106,0.15)"), vrect(nb, nend, c, "rgba(231,111,81,0.10)")]);
        lay.annotations.push(topLabel(nsb / 2, "일정 토크"), topLabel((nsb + nb) / 2, "일정 출력"), topLabel((nb + nend) / 2, "특성 영역"));
        Object.assign(lay.xaxis, tx("속도 [rpm]")); Object.assign(lay.xaxis2, tx("속도 [rpm]"));
        draw(p, [line(R.n, R.T, "최대 토크 [N·m]"), line(R.n, R.P.map((x) => x / 1000), "출력 [kW]", { color: "#d62828" }), line(R.n, R.V.map((x) => x / IM.V * 100), "전압 [% 정격]", { n: 2, color: "#2a9d8f" }),
          line(R.n, R.sf.map((x) => x * 10), "슬립 주파수 ×10 [Hz]", { n: 2, color: "#e9c46a" }), line(R.n, R.f, "인버터 주파수 [Hz]", { n: 2, color: "#7c3aed" }),
          line(R.n, R.V.map((x, i) => (R.f[i] > 0 ? x / R.f[i] / (IM.V / IM.f) * 100 : 0)), "공극 자속 ∝ V/f [% 정격]", { n: 2, dash: "dot", color: "#264653" }),
          line(R.n, R.I.map((x) => x / IM.I_rated * 100), "고정자 전류 [% 정격]", { n: 2, dash: "dash", color: "#e76f51" })], lay);
      });
    });
  };

  T.synchronous = function (tab) {
    tab.section((s) => {
      s.row(); s.slider("Vs", "상전압 Vs [V]", 100, 300, 10, 220, { all: true }); s.slider("Ef", "여자 전압 Ef [V] (계자 전류)", 50, 400, 5, 260, { all: true }); s.slider("d", "토크각 δ [°]", 0, 180, 1, 30, { all: true });
      s.slider("Xd", "동기 리액턴스 Xd [Ω]", 1, 20, 0.5, 6, { all: true }); s.slider("Xq", "q축 리액턴스 Xq [Ω] (= Xd 이면 원통형)", 1, 20, 0.5, 6, { all: true });
      s.end(); const [c0, c1] = s.cols([2, 3]); s.into(c0); s.html("<b>페이저도 (Vs 기준)</b>"); const pph = s.plot(360); s.into(c1); const p = s.plot(380); s.end(); const m = s.metrics(4);
      s.h("동기 전동기의 토크–속도 특성: 속도는 동기 속도로 고정, 부하가 늘면 δ 가 커짐 (최대 토크를 넘으면 탈조)"); const pts_ = s.plot(260);
      s.h("V 곡선: 부하 일정에서 여자(계자 전류)에 따른 전기자 전류"); const pv = s.plot(330);
      s.html('<div class="info">기동: 정지 상태에서 60 Hz 를 바로 걸면 평균 토크가 0 이라 기동하지 못합니다. 댐퍼 권선으로 유도 전동기처럼 기동하거나, 인버터로 낮은 주파수부터 올립니다. PMSM 시뮬레이터의 \'계통 직결\' 탭에서 동기 운전·탈조를 볼 수 있습니다.</div>');
      const ws = 2 * Math.PI * 60 / 2, dg = M.linspace(0, 180, 181);
      s.on((v) => {
        const r = syncPhasor(v.Vs, v.Ef, M.rad(v.d), v.Xd, v.Xq), sc = v.Vs / Math.max(r.I.abs(), 1e-9) * 0.6;
        const ph = phasorFig([[new C(v.Vs), new C(0), "Vs", "#111"], [r.Ef, new C(0), "Ef", "#2a9d8f"], [new C(v.Vs), r.Ef, "jX·I", "#e9c46a"], [r.I.scale(sc), new C(0), "Ia (배율)", "#d62828"]]);
        draw(pph, ph.tr, ph.lay);
        const TT = dg.map((x) => syncTorque(M.rad(x), v.Vs, v.Ef, v.Xd, v.Xq, ws)), tot = TT.map((q) => q[0] + q[1]);
        let km = 0; tot.forEach((x, i) => { if (x > tot[km]) km = i; });
        const [tf, trr] = syncTorque(M.rad(v.d), v.Vs, v.Ef, v.Xd, v.Xq, ws), Tnow = tf + trr;
        const tr = [line(dg, TT.map((q) => q[0]), "여자 토크 Tf", { dash: "dot" })];
        if (Math.abs(v.Xd - v.Xq) > 1e-9) tr.push(line(dg, TT.map((q) => q[1]), "릴럭턴스 토크 Tr", { dash: "dot", color: "#e9c46a" }));
        tr.push(line(dg, tot, "전체 토크", { width: 3, color: "#2a9d8f" }), pts([v.d], [Tnow], "현재"));
        draw(p, tr, { shapes: [vrect(0, dg[km], 1)], annotations: [topLabel(dg[km] / 2, "안정 운전 범위")], xaxis: tx("토크각 δ [°]"), yaxis: tx("토크 [N·m] (4극, 60 Hz)") });
        const lag = r.Q > 0;
        metric(m[0], "전기자 전류", `${r.I.abs().toFixed(1)} A`); metric(m[1], "역률", `${Math.abs(r.pf).toFixed(3)} ${lag ? "지상" : "진상"}`, lag ? "부족여자" : "과여자");
        metric(m[2], "입력 전력 (3상)", `${(r.P / 1000).toFixed(2)} kW`); metric(m[3], "토크", `${Tnow.toFixed(1)} N·m`, `최대 ${tot[km].toFixed(1)} N·m @ ${dg[km]}°`);
        draw(pts_, [line([1800, 1800], [0, tot[km]], "동기 전동기: 동기 속도에서만 토크", { width: 5 }), pts([1800], [Tnow], "현재 토크 (토크각 δ 로 결정)")],
          { xaxis: Object.assign(tx("속도 [rpm]"), { range: [0, 2200] }), yaxis: tx("토크 [N·m]"), legend: { y: -0.3 }, margin: { b: 80 } });
        const Efr = M.linspace(60, 450, 200);
        draw(pv, [0, 5, 10, 15].map((Pk, i) => line(Efr, Efr.map((E) => { const sd = Pk * 1000 * v.Xd / (3 * v.Vs * E); return Math.abs(sd) <= 1 ? syncPhasor(v.Vs, E, Math.asin(sd), v.Xd).I.abs() : NaN; }), `부하 ${Pk} kW`, { color: COL[i] })),
          { shapes: [vline(v.Ef, 1, { color: "#d62828" })], xaxis: tx("여자 전압 Ef [V] (∝ 계자 전류)"), yaxis: Object.assign(tx("전기자 전류 [A]"), { rangemode: "tozero" }) });
      });
    });
  };

  const api = Object.assign(T, { _calc: { IM, circuit, maxTorque, opPoints, doubleCage, nema, deepBar, runTests, estimate, regions, vfClosed, syncPhasor, syncTorque, mmf, windingMMF } });
  root.LabCh4 = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
