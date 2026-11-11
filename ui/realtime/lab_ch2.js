/* 강의 실습 2장 (브라우저 계산). 계산식은 lectures/ch2.py 와 같음. */
(function (root) {
  "use strict";
  const { M, C, metric, table, sub, hline, vline, vrect, label, topLabel, line, pts, draw, tx, svg, COL } = root.Lab;
  const RPM = M.RPM;
  const TEXTBOOK = { V: 140, I: 25, n: 3000, P: 3336, Ra: 0.26, La: 1.7e-3, J: 0.00252, B: 0 };
  TEXTBOOK.K = TEXTBOOK.P / (TEXTBOOK.n / RPM) / TEXTBOOK.I;
  const EXAMPLE2 = { V: 125, I: 43.96, n: 1800, Ra: 0.256, La: 1.7e-3, J: 0.00252, B: 0, K: 0.6034 };

  // ---------------------------------------------------------------- 계산
  const speedTorque = (T, V, K, Ra) => V / K - Ra * T / (K * K);
  function capability(P, ratio = 3, n = 200) {
    const wb = (P.V - P.Ra * P.I) / P.K, w = M.linspace(1e-3, ratio * wb, n);
    const K = w.map((x) => (x <= wb ? P.K : (P.V - P.Ra * P.I) / x));
    return { w, K, T: K.map((k) => k * P.I), Pw: K.map((k, i) => k * P.I * w[i]), V: K.map((k, i) => Math.min(P.Ra * P.I + k * w[i], P.V)), wb };
  }
  function vToSpeed(P, La) {
    La = La === undefined ? P.La : La;
    const a = La * P.J, b = P.Ra * P.J + La * P.B, c = P.Ra * P.B + P.K * P.K;
    return { poles: M.roots2(a, b, c), zeta: b / (2 * Math.sqrt(a * c)), wn: Math.sqrt(c / a), Tm: P.J * P.Ra / (P.K * P.K), Ta: La / P.Ra };
  }
  function voltageStep(P, V, t0, tend, La, n = 4000) {
    La = La === undefined ? P.La : La;
    const h = tend / n, t = [], ia = [], w = [];
    let x = [0, 0];
    const f = (tt, s) => { const v = tt >= t0 ? V : 0;
      if (La === 0) { return [0, (P.K * (v - P.K * s[1]) / P.Ra - P.B * s[1]) / P.J]; }
      return [(v - P.Ra * s[0] - P.K * s[1]) / La, (P.K * s[0] - P.B * s[1]) / P.J]; };
    const sub2 = 4, hh = h / sub2;
    for (let k = 0; k <= n; k++) {
      const tt = k * h; t.push(tt);
      const v = tt >= t0 ? V : 0;
      ia.push(La === 0 ? (v - P.K * x[1]) / P.Ra : x[0]); w.push(x[1]);
      for (let s = 0; s < sub2; s++) {
        const ts = tt + s * hh;
        const k1 = f(ts, x), k2 = f(ts + hh / 2, x.map((q, i) => q + hh / 2 * k1[i])), k3 = f(ts + hh / 2, x.map((q, i) => q + hh / 2 * k2[i])), k4 = f(ts + hh, x.map((q, i) => q + hh * k3[i]));
        x = x.map((q, i) => q + hh / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]));
      }
    }
    return { t, ia, w };
  }
  const currentGains = (P, wcc) => [P.La * wcc, P.Ra * wcc];
  const speedGains = (P, wcs) => { const Kp = P.J * wcs / P.K; return [Kp, Kp * wcs / 5]; };
  function rlDemo(P, kind, Kp, Ki, iref = 20, tend = 0.02, h = 2e-6, every = 10) {
    const n = Math.round(tend / h), t = [], I = [], U = [];
    let i = 0, xi = 0;
    for (let k = 0; k <= n; k++) {
      const e = iref - i, kp = kind === "I" ? 0 : Kp, ki = kind === "P" ? 0 : Ki, v = kp * e + xi;
      if (k % every === 0) { t.push(k * h); I.push(i); U.push(v); }
      xi += ki * e * h; i += h * (v - P.Ra * i) / P.La;
    }
    return { t, i: I, v: U };
  }
  function loopBode(P, Kp, Ki, w) {
    const mag = [], ph = [];
    let prev = null;
    for (const x of w) { const s = new C(0, x), L = new C(Kp).add(new C(Ki).div(s)).div(s.scale(P.La).add(P.Ra));
      mag.push(20 * Math.log10(L.abs())); let a = M.deg(L.arg()); if (prev !== null) while (a - prev > 180) a -= 360; prev = a; ph.push(a); }
    let wc = NaN, pm = NaN;
    for (let k = 0; k < w.length - 1; k++) if (mag[k] >= 0 && mag[k + 1] < 0) { wc = w[k]; pm = 180 + ph[k]; break; }
    return { mag, ph, wc, pm };
  }
  /* 직류 전동기 + PI 전류 제어 (+ 속도 제어). o: {iref(t), wref(t), TL(t), fixed, wcc, wcs, ff, Vlim, aw, alpha, Ilim, h, tend, every} */
  function simulate(P, o) {
    const h = o.h || 1e-5, n = Math.round(o.tend / h), every = o.every || Math.max(1, Math.floor(n / 3000));
    const [Kpc, Kic] = currentGains(P, o.wcc || 2 * Math.PI * 500), [Kps, Kis] = speedGains(P, o.wcs || 2 * Math.PI * 50);
    const Vlim = o.Vlim === undefined ? P.V : o.Vlim, Ilim = o.Ilim === undefined ? 2 * P.I : o.Ilim, aw = o.aw === undefined ? 1 : (o.aw ? 1 : 0);
    const alpha = o.alpha === undefined ? 1 : o.alpha, ff = o.ff === undefined ? true : o.ff;
    const R = { t: [], ia: [], w: [], istar: [], vstar: [], v: [], wref: [], xi: [] };
    let ia = 0, w = o.fixed === undefined ? 0 : o.fixed, xi = 0, xw = 0;
    for (let k = 0; k <= n; k++) {
      const t = k * h; let istar, wr = NaN;
      if (o.wref) { wr = o.wref(t); const ew = wr - w, iu = Kps * (alpha * wr - w) + xw; istar = M.clip(iu, -Ilim, Ilim); xw += h * (Kis * ew - (Kis / Kps) * (iu - istar) * aw); }
      else istar = o.iref(t);
      const e = istar - ia, vu = Kpc * e + xi + (ff ? P.K * w : 0), v = M.clip(vu, -Vlim, Vlim);
      xi += h * Kic * (e - (1 / Kpc) * (vu - v) * aw);
      if (k % every === 0) { R.t.push(t); R.ia.push(ia); R.w.push(w); R.istar.push(istar); R.vstar.push(vu); R.v.push(v); R.wref.push(wr); R.xi.push(xi); }
      const TL = o.TL ? o.TL(t) : 0, di = (v - P.Ra * ia - P.K * w) / P.La, im = ia + 0.5 * h * di;
      ia += h * (v - P.Ra * im - P.K * w) / P.La;
      if (o.fixed === undefined) w += h * (P.K * ia - P.B * w - TL) / P.J;
    }
    R.gains = { Kpc, Kic, Kps, Kis };
    return R;
  }
  function stepMetrics(t, y, yf, t0 = 0, t1 = Infinity) {
    let y0 = null, mx = -Infinity, t10 = NaN, t90 = NaN;
    for (let k = 0; k < t.length; k++) { if (t[k] < t0 || t[k] >= t1) continue; if (y0 === null) y0 = y[k];
      const r = (y[k] - y0) / (yf - y0); if (r > mx) mx = r; if (isNaN(t10) && r >= 0.1) t10 = t[k]; if (isNaN(t90) && r >= 0.9) t90 = t[k]; }
    return [Math.max(0, (mx - 1) * 100), t90 - t10];
  }
  function chopper(mode, Vdc, va, fsw, R, L, E, periods = 3, pts_ = 300) {
    const T = 1 / fsw, h = T / pts_, warm = Math.max(30, Math.floor(6 * L / R / T)), ntot = (warm + periods) * pts_, m = va / Vdc, a = Math.exp(-h * R / L);
    let i = (va - E) / R; const o = { t: [], tri: [], S1: [], S2: [], v: [], i: [] };
    for (let k = 0; k < ntot; k++) {
      const t = k * h, ph = (t / T) % 1, tri = ph < 0.5 ? 4 * ph - 1 : 3 - 4 * ph;
      let S1, S2, v;
      if (mode === "1상한") { S1 = m > (tri + 1) / 2 ? 1 : 0; S2 = 0; v = S1 ? Vdc : 0; if (!S1 && i <= 0) v = E; }
      else if (mode === "바이폴라") { S1 = m > tri ? 1 : 0; S2 = 1 - S1; v = S1 ? Vdc : -Vdc; }
      else { S1 = m > tri ? 1 : 0; S2 = -m > tri ? 1 : 0; v = Vdc * (S1 - S2); }
      const iss = (v - E) / R; i = iss + (i - iss) * a; if (mode === "1상한" && i < 0) i = 0;
      if (k >= warm * pts_) { o.t.push(t - warm * pts_ * h); o.tri.push(tri); o.S1.push(S1); o.S2.push(S2); o.v.push(v); o.i.push(i); }
    }
    return o;
  }
  function chopperRamp(mode, Vdc, fsw, periods = 40, pts_ = 80) {
    const T = 1 / fsw, h = T / pts_, n = periods * pts_, t = [], vr = [], v = [];
    for (let k = 0; k < n; k++) { const tt = k * h, m = 0.95 - 1.9 * tt / ((n - 1) * h), ph = (tt / T) % 1, tri = ph < 0.5 ? 4 * ph - 1 : 3 - 4 * ph;
      t.push(tt); vr.push(m * Vdc); v.push(mode === "바이폴라" ? (m > tri ? Vdc : -Vdc) : Vdc * ((m > tri ? 1 : 0) - (-m > tri ? 1 : 0))); }
    return { t, vr, v };
  }
  function chopperDrive(P, mode, fsw, bw, tend = 0.2, per = 100) {
    const [Kpc, Kic] = currentGains(P, 2 * Math.PI * 500), [Kps, Kis] = speedGains(P, 2 * Math.PI * bw);
    const h = 1 / fsw / per, n = Math.floor(tend / h), Ilim = P.I;
    let ia = 0, w = 0, xi = 0, xw = 0;
    const R = { t: [], w: [], ia: [], Te: [] }, Z = { t: [], tri: [], vref: [], Sa: [], Sb: [], va: [], ia: [] };
    const every = Math.max(1, Math.floor(n / 4000)), z0 = 0.1, z1 = 0.1 + 3 / fsw;
    for (let k = 0; k < n; k++) {
      const t = k * h, wr = t >= 0.05 ? 2500 / RPM : 0;
      const iu = Kps * (wr - w) + xw, istar = M.clip(iu, -Ilim, Ilim); xw += h * Kis * ((wr - w) - (iu - istar) / Kps);
      const e = istar - ia, vu = Kpc * e + xi + P.K * w, vref = M.clip(vu, -P.V, P.V); xi += h * Kic * (e - (vu - vref) / Kpc);
      const ph = (t * fsw) % 1, tri = ph < 0.5 ? 4 * ph - 1 : 3 - 4 * ph, m = vref / P.V;
      let Sa, Sb, va;
      if (mode === "유니폴라") { Sa = m > tri ? 1 : 0; Sb = -m > tri ? 1 : 0; va = P.V * (Sa - Sb); }
      else { Sa = m > tri ? 1 : 0; Sb = 1 - Sa; va = Sa ? P.V : -P.V; }
      ia += h * (va - P.Ra * ia - P.K * w) / P.La; w += h * (P.K * ia - P.B * w) / P.J;
      if (k % every === 0) { R.t.push(t); R.w.push(w); R.ia.push(ia); R.Te.push(P.K * ia); }
      if (t >= z0 && t <= z1) { Z.t.push((t - z0) * 1000); Z.tri.push(tri); Z.vref.push(vref / P.V); Z.Sa.push(Sa); Z.Sb.push(Sb); Z.va.push(va); Z.ia.push(ia); }
    }
    return { R, Z };
  }

  // ---------------------------------------------------------------- 그림: H-브리지
  function hbridgeSVG(st, idir, vaText, title) {
    const o = svg.start(460, 300), xA = 150, xB = 360, yT = 50, yB = 250, yM = 150;
    svg.text(o, 230, 18, title, 12, "#333");
    svg.line(o, 40, yT, 400, yT); svg.line(o, 40, yB, 400, yB); svg.line(o, 40, yT, 40, yM - 28); svg.line(o, 40, yB, 40, yM + 28);
    svg.source(o, 40, yM, 28, "Vdc");
    for (const [x, u, d] of [[xA, "T1", "T2"], [xB, "T3", "T4"]]) {
      svg.line(o, x, yT, x, yT + 22); svg.line(o, x, yT + 58, x, yB - 58); svg.line(o, x, yB - 22, x, yB);
      svg.sw(o, x, yT + 40, !!st[u], u); svg.sw(o, x, yB - 40, !!st[d], d);
    }
    svg.line(o, xA, yM, 205, yM); svg.resistor(o, 205, yM, 235, yM); svg.inductor(o, 235, yM, 265, yM); svg.circle(o, 285, yM, 16); svg.text(o, 285, yM, "E", 12, "#111", "middle", "bold");
    svg.line(o, 301, yM, xB, yM);
    svg.text(o, xA - 12, yM - 10, "A", 12); svg.text(o, xB + 12, yM - 10, "B", 12);
    svg.text(o, 255, yM + 32, vaText, 12, "#d62828");
    if (idir) { if (idir > 0) svg.arrow(o, 200, yM - 22, 300, yM - 22); else svg.arrow(o, 300, yM - 22, 200, yM - 22); svg.text(o, 250, yM - 34, "ia", 12, "#d62828"); }
    return svg.done(o);
  }

  // ---------------------------------------------------------------- 공통: 전동기 선택
  function motorControls(s, withPreset = true) {
    if (withPreset) s.radio("pre", "전동기", ["교재 2.9절 전동기 (140 V, 25 A, 3000 r/min)", "교재 예제 2 (5 kW, 125 V, 1800 r/min)"], "교재 2.9절 전동기 (140 V, 25 A, 3000 r/min)", { all: true, horiz: true, wide: true });
    s.end(); s.row();
    s.check("custom", "파라미터 직접 바꾸기", false, { all: true });
    s.num("cRa", "Ra [Ω]", 0.05, 5, 0.01, 0.26, { all: true }); s.num("cLa", "La [mH]", 0.1, 50, 0.1, 1.7, { all: true });
    s.num("cJ", "J [kg·m²]", 1e-4, 0.1, 1e-4, 0.00252, { all: true }); s.num("cK", "Kφ [V·s/rad]", 0.05, 2, 0.001, 0.4248, { all: true });
    s.end();
    s.note("교재 m-file 값: Power = 3336 W, Ra = 0.26 Ω, La = 1.7 mH, J = 0.00252 kg·m², B = 0, K = Te정격/Ia정격 = 0.4248. 예제 2: Ra = 0.256 Ω, La = 1.7 mH, J = 0.00252, kφ = 0.6034. '파라미터 직접 바꾸기' 를 켜면 아래 값이 쓰입니다.");
  }
  function motorP(v) {
    const P = Object.assign({}, (v.pre || "").startsWith("교재 예제") ? EXAMPLE2 : TEXTBOOK);
    if (v.custom) Object.assign(P, { Ra: v.cRa, La: v.cLa * 1e-3, J: v.cJ, K: v.cK });
    return P;
  }

  // ---------------------------------------------------------------- 탭
  const T = {};

  T.types = function (tab) {
    tab.section((s) => {
      s.h("정류자와 브러시의 역할: 전기자 도체 전류(교류)와 토크");
      s.row(); s.slider("n", "전기자 코일 수", 1, 12, 1, 1); s.end();
      const p = s.plot(380);
      s.note("정류자가 없으면 도체 전류가 한 방향이라 토크가 +, − 를 오가며 평균 0. 정류자로 반 바퀴마다 전류를 뒤집으면 토크가 한 방향, 코일을 늘리면 리플이 작아져 거의 일정한 토크가 됨.");
      const th = M.linspace(0, 4 * Math.PI, 721), x = th.map(M.deg);
      s.on((v) => {
        const lay = sub(2, 1, { titles: ["한 도체의 전류 (정류자가 반 바퀴마다 뒤집음 → 교류)", "토크"], sharex: true });
        Object.assign(lay.xaxis2, tx("회전 각도 [°]"), { dtick: 90 });
        const tr = [line(x, th.map((a) => Math.sign(Math.sin(a))), "도체 전류", { shape: "hv" }),
          line(x, th.map(Math.cos), "정류자 없음 (평균 0)", { dash: "dot", n: 2, color: "#94a3b8" }),
          line(x, th.map((a) => Math.abs(Math.cos(a))), "코일 1개 + 정류자", { n: 2, color: "#d62828" })];
        if (v.n > 1) tr.push(line(x, th.map((a) => M.mean(M.range(v.n, (k) => Math.abs(Math.cos(a - k * Math.PI / v.n))))), `코일 ${v.n}개 + 정류자`, { n: 2, width: 3, color: "#2a9d8f" }));
        draw(p, tr, lay);
      });
    });
  };

  T.steady = function (tab) {
    tab.section((s) => { s.row(); motorControls(s); });
    tab.section((s) => {
      const [c0, c1] = s.cols([1, 3]);
      s.into(c0); s.radio("mode", "속도 제어 방법", ["전기자 전압 제어", "계자 자속 제어 (약계자)"], "전기자 전압 제어");
      s.slider("TLr", "부하 토크 (정격 대비) [%]", 0, 200, 5, 60); const nt = s.note();
      s.into(c1); const p = s.plot(380);
      s.end(); const pf = s.plot(240);
      s.on((v) => {
        const P = motorP(v), Tmax = 2 * P.I * P.K, Tg = M.linspace(0, Tmax, 50), TL = v.TLr / 100 * P.I * P.K, tr = [];
        const shapes = [vline(TL, 1, { color: "#e76f51", dash: "solid" }), vline(P.I * P.K, 1, { color: "#d62828", dash: "dash" })];
        if (v.mode.startsWith("전기자")) {
          [35, 70, 105, 140].forEach((V, i) => { tr.push(line(Tg, Tg.map((T_) => speedTorque(T_, V * P.V / 140, P.K, P.Ra) * RPM), `V = ${(V * P.V / 140).toFixed(0)} V`, { color: COL[i] }));
            tr.push(pts([TL], [speedTorque(TL, V * P.V / 140, P.K, P.Ra) * RPM], "", { color: "#111", size: 8, legend: false })); });
          nt.textContent = "기울기(−Ra/K²)는 같고 무부하 속도 V/K 만 비례해서 변함 → 기저 속도 이하에서 쓰는 방법";
        } else {
          [1, 0.8, 0.6, 0.5].forEach((r, i) => { tr.push(line(Tg, Tg.map((T_) => speedTorque(T_, P.V, P.K * r, P.Ra) * RPM), `Φ = ${r * 100}% 정격`, { color: COL[i] }));
            tr.push(pts([TL], [speedTorque(TL, P.V, P.K * r, P.Ra) * RPM], "", { color: "#111", size: 8, legend: false }));
            const Tr = P.K * r * P.I; tr.push(line([Tr, Tr], [0, speedTorque(Tr, P.V, P.K * r, P.Ra) * RPM], "", { color: "#aaa", dash: "dot", width: 1, legend: false })); });
          nt.textContent = "자속을 줄이면 무부하 속도는 1/Φ 로 오르고 기울기는 1/Φ² 로 가팔라짐 → 기저 속도 이상(약계자). 점선: 각 자속에서 정격 전류 토크";
        }
        draw(p, tr, { shapes, annotations: [topLabel(TL, "부하 토크"), topLabel(P.I * P.K, "정격 전류 시 토크 한계")],
          xaxis: tx("토크 T [N·m]"), yaxis: Object.assign(tx("속도 [rpm]"), { rangemode: "tozero" }) });
        pf.style.display = v.mode.startsWith("계자") ? "" : "none";
        if (!v.mode.startsWith("전기자")) {
          const If = M.linspace(0, 2, 100), k = Math.tanh(1.3);
          const ptsF = [[1, "정격 (A)"], [0.8, "B"], [0.6, "C"]].map(([r]) => Math.atanh(r * k) / 1.3);
          draw(pf, [line(If, If.map((x) => Math.tanh(1.3 * x) / k), "자속 Φ (상대값)"), pts(ptsF, [1, 0.8, 0.6], "", { text: ["정격 (A)", "B", "C"], size: 9, legend: false })],
            { xaxis: tx("계자 전류 If (상대값) — 정격 자속은 포화 직전이라 주로 줄이는(약계자) 쪽으로 씀"), yaxis: tx("계자 자속 Φ"), showlegend: false, margin: { b: 45 } });
        }
      });
    });
    tab.section((s) => {
      s.h("능력 곡선 (일정 토크 영역 / 일정 출력 영역)");
      const p = s.plot(340);
      s.on((v) => {
        const P = motorP(v), cap = capability(P), x = cap.w.map((q) => q * RPM), wb = cap.wb * RPM;
        const lay = sub(1, 2, { titles: ["능력 곡선: 토크·출력", "전압·자속·역기전력·전류"] });
        lay.shapes = [vrect(0, wb, 1), vrect(wb, x[x.length - 1], 1, "rgba(231,111,81,0.10)"), vrect(0, wb, 2), vrect(wb, x[x.length - 1], 2, "rgba(231,111,81,0.10)")];
        lay.annotations.push(topLabel(wb / 2, "일정 토크 영역"), topLabel(wb * 2, "일정 출력 영역 (약계자)"));
        Object.assign(lay.xaxis, tx("속도 [rpm]")); Object.assign(lay.xaxis2, tx("속도 [rpm]"));
        draw(p, [line(x, cap.T, "최대 토크 [N·m]"), line(x, cap.Pw.map((q) => q / 1000), "출력 [kW]", { color: "#d62828" }),
          line(x, cap.V, "전기자 전압 [V]", { n: 2, color: "#2a9d8f" }), line(x, cap.K.map((k) => k / P.K * 100), "계자 자속 [% 정격]", { n: 2, color: "#7c3aed" }),
          line(x, cap.K.map((k, i) => k * cap.w[i]), "역기전력 E [V]", { n: 2, dash: "dot", color: "#e76f51" }), line(x, x.map(() => P.I), "전기자 전류 [A]", { n: 2, dash: "dash", color: "#264653" })], lay);
      });
    });
    tab.section((s) => {
      s.h("교재 예제 1: 5 kW, 125 V, 1800 r/min 직류 전동기 (효율 91 %, Ra = 0.256 Ω)");
      s.row(); s.num("eP", "출력 [kW]", 0.1, 100, 0.5, 5); s.num("eV", "정격 전압 [V]", 10, 1000, 5, 125); s.num("en", "정격 속도 [r/min]", 100, 10000, 50, 1800);
      s.num("eeta", "효율 [%]", 50, 100, 1, 91); s.num("eRa", "전기자 저항 Ra [Ω]", 0.01, 5, 0.001, 0.256);
      s.end(); const tb = s.table();
      s.on((v) => {
        const Pe = v.eP * 1000, Ia = Pe / (v.eeta / 100) / v.eV, wm = v.en / RPM, Te = Pe / wm, kp = (v.eV - Ia * v.eRa) / wm;
        const w10 = (0.9 * v.eV - Ia * v.eRa) / kp, wf = (v.eV - Ia * v.eRa) / (0.9 * kp);
        table(tb, ["항목", "값"], [["① 정격 전기자 전류 Ia = P/(η·V)", `${Ia.toFixed(2)} A`], ["① 정격 토크 Te = P/ωm", `${Te.toFixed(2)} N·m`],
          ["kφ = (V − Ia·Ra)/ωm", `${kp.toFixed(5)} V·s/rad`], ["② 전압 10 % 감소 시 속도 (정격 전류)", `${(w10 * RPM).toFixed(0)} r/min (${w10.toFixed(2)} rad/s)`],
          ["③ 자속 10 % 감소 시 속도", `${(wf * RPM).toFixed(0)} r/min (${wf.toFixed(2)} rad/s)`], ["③ 그때 낼 수 있는 토크 0.9kφ·Ia", `${(0.9 * kp * Ia).toFixed(2)} N·m`]]);
      });
    });
  };

  T.transient = function (tab) {
    tab.section((s) => { s.row(); motorControls(s); });
    tab.section((s) => {
      const m = s.metrics(4), p = s.plot(360);
      s.on((v) => {
        const P = motorP(v), r = vToSpeed(P);
        metric(m[0], "감쇠비 ζ", r.zeta.toFixed(3), r.zeta < 1 ? "부족감쇠 (진동)" : "과감쇠 (진동 없음)");
        metric(m[1], "고유 주파수 ωn", `${r.wn.toFixed(1)} rad/s`);
        metric(m[2], "전기 기계 시정수 Tm = JRa/K²", `${(r.Tm * 1000).toFixed(2)} ms`);
        metric(m[3], "전기자 시정수 Ta = La/Ra", `${(r.Ta * 1000).toFixed(2)} ms`, "Tm < 4Ta 이면 진동");
        const a = voltageStep(P, P.V / 2, 0.05, 0.2), b = voltageStep(P, P.V, 0.05, 0.2), c0 = voltageStep(P, P.V, 0.05, 0.2, 0);
        const lay = sub(1, 3, { titles: ["속도 [rpm]", "전기자 전류 [A]", "극점 (s 평면)"], colw: [0.38, 0.38, 0.24] });
        Object.assign(lay.xaxis, tx("시간 [s]")); Object.assign(lay.xaxis2, tx("시간 [s]")); Object.assign(lay.xaxis3, tx("실수부")); Object.assign(lay.yaxis3, tx("허수부"));
        draw(p, [line(a.t, a.w.map((x) => x * RPM), `${(P.V / 2).toFixed(0)} V`), line(b.t, b.w.map((x) => x * RPM), `${P.V.toFixed(0)} V`, { color: "#d62828" }),
          line(c0.t, c0.w.map((x) => x * RPM), `${P.V.toFixed(0)} V, La = 0 근사 (1차)`, { dash: "dot", color: "#2a9d8f" }),
          line(a.t, a.ia, "", { n: 2, legend: false, color: COL[0] }), line(b.t, b.ia, "", { n: 2, legend: false, color: "#d62828" }),
          pts(r.poles.map((q) => q[0]), r.poles.map((q) => q[1]), "극점", { symbol: "x", size: 14, n: 3 })], lay);
      });
    });
    tab.section((s) => {
      s.h("극점 위치와 과도 응답 (안정·불안정 영역, 부족·임계·과감쇠)");
      const [c0, c1] = s.cols([1, 3]);
      s.into(c0); s.slider("ps", "극점 실수부 −σ (오른쪽 = 불안정)", -200, 60, 5, -75); s.slider("pw", "극점 허수부 ±ωd", 0, 400, 10, 280); const nt = s.note();
      s.into(c1); const p = s.plot(330); s.end(); const pz = s.plot(280);
      const t = M.linspace(0, 0.08, 500);
      draw(pz, [[0.3, "부족감쇠 ζ = 0.3"], [1, "임계감쇠 ζ = 1"], [2, "과감쇠 ζ = 2"]].map(([z, lab], i) => line(t, M.stepTF([150 * 150], [1, 2 * z * 150, 150 * 150], t), lab, { color: COL[i] })),
        { xaxis: tx("시간 [s]") });
      s.on((v) => {
        const sig = -v.ps, wn2 = sig * sig + v.pw * v.pw, y = wn2 > 1e-9 ? M.stepTF([wn2], [1, 2 * sig, wn2], t) : t.map(() => 0);
        const lay = sub(1, 2, { titles: ["s 평면", "계단 응답"] });
        lay.shapes = [{ type: "rect", xref: "x", yref: "y", x0: -250, x1: 0, y0: -420, y1: 420, fillcolor: "rgba(42,157,143,0.08)", line: { width: 0 }, layer: "below" },
          { type: "rect", xref: "x", yref: "y", x0: 0, x1: 80, y0: -420, y1: 420, fillcolor: "rgba(214,40,40,0.08)", line: { width: 0 }, layer: "below" }, hline(1, 2)];
        Object.assign(lay.xaxis, tx("실수축 (왼쪽 = 빨리 수렴)"), { range: [-250, 80] }); Object.assign(lay.yaxis, tx("허수축 (멀수록 진동↑)"), { range: [-420, 420] });
        Object.assign(lay.xaxis2, tx("시간 [s]")); Object.assign(lay.yaxis2, { range: [-1, 3] });
        draw(p, [pts([v.ps, v.ps], [v.pw, -v.pw], "극점", { symbol: "x", size: 14 }), line(t, y.map((q) => M.clip(q, -5, 5)), "응답", { n: 2 })], lay);
        const z = Math.hypot(v.ps, v.pw) > 0 ? -v.ps / Math.hypot(v.ps, v.pw) : 0;
        nt.innerHTML = `ζ = ${z.toFixed(2)} → ` + (v.ps > 0 ? "<b>불안정 (발산)</b>" : v.pw > 0 ? "진동하며 수렴 (부족감쇠)" : "진동 없음");
      });
    });
  };

  T.basics = function (tab) {
    const P = TEXTBOOK, [kp0, ki0] = currentGains(P, 2 * Math.PI * 500);
    tab.section((s) => {
      s.note("대상: 회전자를 멈춘 전기자 회로 (Ra–La, 1차 시스템) 의 전류를 20 A 로 제어 (교재 2.9절 전동기).");
      s.row(); s.slider("Kp", "비례 이득 Kp [V/A]", 0.5, 30, 0.1, Math.round(kp0 * 10) / 10, { all: true }); s.slider("Ki", "적분 이득 Ki [V/(A·s)]", 0, 3000, 10, Math.round(ki0 / 10) * 10, { all: true });
      s.end(); s.note(`극점-영점 상쇄 값 (500 Hz): Kp = La·ωcc = ${kp0.toFixed(2)}, Ki = Ra·ωcc = ${ki0.toFixed(0)}`);
      const p = s.plot(330), m = s.metrics(3), pb = s.plot(360), mb = s.metrics(2);
      const w = M.range(500, (i) => Math.pow(10, 1 + 5 * i / 499));
      s.on((v) => {
        const lay = sub(1, 2, { titles: ["전류 응답", "제어기 출력 전압"] }), tr = [], res = {};
        [["P", "#e76f51"], ["I", "#2a9d8f"], ["PI", "#264653"]].forEach(([k, c]) => { const r = rlDemo(P, k, v.Kp, Math.max(v.Ki, 1e-9)); res[k] = r.i[r.i.length - 1];
          tr.push(line(r.t.map((x) => x * 1000), r.i, `${k} 제어`, { color: c }), line(r.t.map((x) => x * 1000), r.v, "", { color: c, n: 2, legend: false })); });
        lay.shapes = [hline(20)]; Object.assign(lay.xaxis, tx("시간 [ms]")); Object.assign(lay.xaxis2, tx("시간 [ms]"));
        draw(p, tr, lay);
        metric(m[0], "P 제어 정상상태 오차", `${(20 - res.P).toFixed(2)} A`, `이론 20·Ra/(Ra+Kp) = ${(20 * P.Ra / (P.Ra + v.Kp)).toFixed(2)} A`);
        metric(m[1], "I 제어 최종 값", `${res.I.toFixed(2)} A`, "느리고 진동할 수 있음"); metric(m[2], "PI 제어 최종 값", `${res.PI.toFixed(2)} A`, "정상상태 오차 0");
        const b = loopBode(P, v.Kp, v.Ki, w), f = w.map((x) => x / (2 * Math.PI));
        const lb = sub(2, 1, { titles: ["개루프 이득 |L(jω)| [dB]", "위상 [°]"], sharex: true });
        lb.xaxis.type = "log"; lb.xaxis2.type = "log"; Object.assign(lb.xaxis2, tx("주파수 [Hz]"));
        lb.shapes = [hline(0, 1), hline(-180, 2, { color: "#d62828" })]; if (isFinite(b.wc)) lb.shapes.push(vline(b.wc / (2 * Math.PI), 1), vline(b.wc / (2 * Math.PI), 2));
        draw(pb, [line(f, b.mag, "이득"), line(f, b.ph, "위상", { n: 2, color: "#d62828" })], Object.assign(lb, { showlegend: false }));
        metric(mb[0], "이득 교차 주파수 (≈ 대역폭)", isFinite(b.wc) ? `${(b.wc / (2 * Math.PI)).toFixed(0)} Hz` : "—");
        metric(mb[1], "위상 여유", isFinite(b.pm) ? `${b.pm.toFixed(0)}°` : "—", "클수록 안정 (보통 45° 이상)");
      });
    });
    tab.section((s) => {
      s.h("오차가 일정할 때 제어기 출력 u(t) (P 는 계단, I 는 경사, PI 는 둘의 합)");
      const p = s.plot(260), t = M.linspace(0, 0.01, 100);
      s.on((v) => draw(p, [line(t.map((x) => x * 1000), t.map(() => v.Kp), "P: Kp·e"), line(t.map((x) => x * 1000), t.map((x) => v.Ki * x), "I: Ki·∫e dt", { color: "#2a9d8f" }),
        line(t.map((x) => x * 1000), t.map((x) => v.Kp + v.Ki * x), "PI: 합", { width: 3, color: "#d62828" })], { xaxis: tx("시간 [ms] (오차 e = 1 A 일정)"), yaxis: tx("제어기 출력 u [V]") }));
    });
    tab.section((s) => {
      s.h("주파수 응답: 정현파 입력에 대한 정상상태 출력 (폐루프 전류 제어 = 1차 저역 통과)");
      const [c0, c1] = s.cols([1, 2]); s.into(c0); s.slider("fin", "입력 주파수 [Hz]", 10, 5000, 10, 500); const m = s.metrics(2); s.into(c1); const p = s.plot(260);
      s.on((v) => {
        const wcc = v.Kp / P.La, G = new C(wcc).div(new C(wcc, 2 * Math.PI * v.fin)), t = M.linspace(0, 3 / v.fin, 400);
        draw(p, [line(t.map((x) => x * 1000), t.map((x) => Math.sin(2 * Math.PI * v.fin * x)), "입력 r(t) = sin ωt"),
          line(t.map((x) => x * 1000), t.map((x) => G.abs() * Math.sin(2 * Math.PI * v.fin * x + G.arg())), "출력 y(t) = |G| sin(ωt + ∠G)", { color: "#d62828" })], { xaxis: tx("시간 [ms]") });
        metric(m[0], "크기 비 |G(jω)|", `${G.abs().toFixed(3)} (${(20 * Math.log10(G.abs())).toFixed(1)} dB)`);
        metric(m[1], "위상 ∠G(jω)", `${M.deg(G.arg()).toFixed(1)}°`, `대역폭 ${(wcc / (2 * Math.PI)).toFixed(0)} Hz 에서 −3 dB, −45°`);
      });
    });
    tab.section((s) => {
      s.h("대역폭이 넓을수록 빠른 응답 (폐루프 주파수 응답과 시간 응답)");
      const p = s.plot(300), w = M.range(300, (i) => Math.pow(10, 1 + 4 * i / 299)), t = M.linspace(0, 0.005, 300);
      const lay = sub(1, 2, { titles: ["폐루프 크기 [dB]", "계단 응답"] }); lay.xaxis.type = "log"; Object.assign(lay.xaxis, tx("주파수 [Hz]")); Object.assign(lay.xaxis2, tx("시간 [ms]")); lay.shapes = [hline(-3, 1)];
      const tr = [];
      [[250, "#1d4ed8"], [1000, "#d62828"]].forEach(([bw, c]) => { const wc = 2 * Math.PI * bw;
        tr.push(line(w.map((x) => x / (2 * Math.PI)), w.map((x) => 20 * Math.log10(wc / Math.hypot(x, wc))), `대역폭 ${bw} Hz`, { color: c }),
          line(t.map((x) => x * 1000), t.map((x) => 1 - Math.exp(-wc * x)), "", { color: c, n: 2, legend: false })); });
      draw(p, tr, lay);
    });
    tab.section((s) => {
      s.h("안정도: 이득 여유와 위상 여유 (개루프 L(s) = K / [s (s/a + 1)(s/b + 1)])");
      s.row(); s.slider("gK", "루프 이득 K", 0.5, 30, 0.5, 5); s.slider("ga", "극점 a [rad/s]", 1, 20, 0.5, 2); s.slider("gb", "극점 b [rad/s]", 5, 50, 1, 10);
      s.end(); const p = s.plot(420), m = s.metrics(3);
      const w = M.range(800, (i) => Math.pow(10, -2 + 5 * i / 799)), t = M.linspace(0, 10, 600);
      s.on((v) => {
        const mag = [], ph = []; let prev = null;
        for (const x of w) { const sj = new C(0, x), L = new C(v.gK).div(sj.mul(sj.scale(1 / v.ga).add(1)).mul(sj.scale(1 / v.gb).add(1)));
          mag.push(20 * Math.log10(L.abs())); let a = M.deg(L.arg()); if (prev !== null) while (a - prev > 180) a -= 360; while (prev !== null && a - prev < -180) a += 360; prev = a; ph.push(a); }
        let pm = NaN, gm = Infinity, wc = NaN, w180 = NaN;
        for (let k = 0; k < w.length - 1; k++) { if (isNaN(wc) && mag[k] >= 0 && mag[k + 1] < 0) { wc = w[k]; pm = 180 + ph[k]; } if (isNaN(w180) && ph[k] >= -180 && ph[k + 1] < -180) { w180 = w[k]; gm = -mag[k]; } }
        const den = [1 / (v.ga * v.gb), 1 / v.ga + 1 / v.gb, 1, v.gK], y = M.stepTF([v.gK], den, t);
        const lay = sub(2, 2, { titles: ["|L(jω)| [dB]", "폐루프 계단 응답", "∠L(jω) [°]", ""] });
        lay.yaxis2.domain = [0, 1]; delete lay.xaxis4; delete lay.yaxis4;
        lay.xaxis.type = "log"; lay.xaxis3.type = "log"; Object.assign(lay.xaxis3, tx("ω [rad/s]")); Object.assign(lay.xaxis2, tx("시간 [s]")); Object.assign(lay.yaxis2, { range: [-3, 4] });
        lay.shapes = [hline(0, 1), hline(-180, 3, { color: "#d62828" }), hline(1, 2)];
        draw(p, [line(w, mag, "이득"), line(t, y.map((q) => isFinite(q) ? M.clip(q, -3, 4) : NaN), "출력", { n: 2, color: "#d62828" }), line(w, ph, "위상", { n: 3, color: "#2a9d8f" })], Object.assign(lay, { showlegend: false }));
        metric(m[0], "위상 여유", isFinite(pm) ? `${pm.toFixed(0)}°` : "—", "30~60° 가 좋음"); metric(m[1], "이득 여유", isFinite(gm) ? `${gm.toFixed(1)} dB` : "∞", "2~10 dB 정도");
        metric(m[2], "판정", isFinite(pm) && pm > 0 && gm > 0 ? "안정" : "불안정 (발산)");
      });
    });
  };

  T.current = function (tab) {
    tab.section((s) => { s.row(); motorControls(s); });
    tab.section((s) => {
      s.row(); s.select("bw", "전류 제어 대역폭", [250, 500, 1000, 2000], 500, { fmt: (x) => `${x} Hz` }); s.slider("rpm", "회전 속도 (고정) [rpm]", 0, 3000, 100, 1500);
      s.slider("iref", "전류 지령 [A]", 5, 60, 1, 20); s.check("ff", "역기전력 전향 보상", true); s.check("aw", "적분기 누적 방지", true);
      s.end(); s.row(); s.check("lim", "전압 한계 적용 (끄면 교재 Simulink 처럼 제한 없음)", false); s.slider("vl", "전압 한계 [V]", 20, 200, 5, 140); s.end();
      const p = s.plot(360), m = s.metrics(4), p2 = s.plot(320);
      s.note("PI 절점 주파수 Ki/Kp = Ra/La (점선) 가 전동기 극점과 같아 상쇄되고, 개루프는 −20 dB/dec 적분기 모양 → 위상 여유 90°.");
      s.on((v) => {
        const P = motorP(v), Vlim = v.lim ? v.vl : 1e6, step = (t) => (t >= 0.005 && t < 0.025 ? v.iref : 0);
        const o = { iref: step, fixed: v.rpm / RPM, Vlim, ff: v.ff, aw: v.aw, tend: 0.04, h: 2e-6 };
        const r = simulate(P, Object.assign({ wcc: 2 * Math.PI * v.bw }, o)), bw2 = v.bw < 2000 ? v.bw * 2 : v.bw / 2, r2 = simulate(P, Object.assign({ wcc: 2 * Math.PI * bw2 }, o));
        const ms = (a) => a.map((x) => x * 1000), lay = sub(1, 2, { titles: ["전기자 전류", "인가 전압"] });
        Object.assign(lay.xaxis, tx("시간 [ms]")); Object.assign(lay.xaxis2, tx("시간 [ms]")); if (v.lim) lay.shapes = [hline(Vlim, 2, { color: "#d62828" })];
        draw(p, [line(ms(r.t), r.istar, "지령 i*", { dash: "dot", color: "#999" }), line(ms(r.t), r.ia, `${v.bw} Hz`, { color: "#d62828" }), line(ms(r2.t), r2.ia, `${bw2} Hz (비교)`, { color: "#1d4ed8" }),
          line(ms(r.t), r.vstar, "제어기 출력 v*", { n: 2, color: "#e76f51", dash: "dash" }), line(ms(r.t), r.v, "실제 인가 v (제한 후)", { n: 2, color: "#264653" })], lay);
        const g = r.gains, [os_, trr] = stepMetrics(r.t, r.ia, v.iref, 0.005, 0.025);
        metric(m[0], "Kp = La·ωcc", `${g.Kpc.toFixed(2)} V/A`); metric(m[1], "Ki = Ra·ωcc", `${g.Kic.toFixed(0)} V/(A·s)`);
        metric(m[2], "상승 시간 (10→90 %)", `${(trr * 1000).toFixed(3)} ms`, `1차 시스템이면 2.2/ωcc = ${(2.2 / (2 * Math.PI * v.bw) * 1000).toFixed(3)} ms`);
        metric(m[3], "오버슈트", `${os_.toFixed(1)} %`);
        const w = M.range(300, (i) => Math.pow(10, 1 + 5 * i / 299)), b = loopBode(P, g.Kpc, g.Kic, w), wcc = 2 * Math.PI * v.bw;
        const l2 = sub(1, 3, { titles: ["적분기 값 (누적 방지 비교)", "PI 제어기 보드 (크기 dB)", "전류 제어 개루프·폐루프 (dB)"] });
        l2.xaxis2.type = "log"; l2.xaxis3.type = "log"; Object.assign(l2.xaxis, tx("시간 [ms]")); Object.assign(l2.xaxis2, tx("ω [rad/s]")); Object.assign(l2.xaxis3, tx("ω [rad/s]"));
        l2.shapes = [vline(g.Kic / g.Kpc, 2), hline(0, 3)];
        draw(p2, [line(ms(r.t), r.xi, "적분기 출력"), line(w, w.map((x) => 20 * Math.log10(Math.hypot(g.Kpc, g.Kic / x))), "PI: Kp + Ki/s", { n: 2, color: "#d62828" }),
          line(w, b.mag, "개루프 (−20 dB/dec 적분기)", { n: 3, color: "#2a9d8f" }), line(w, w.map((x) => 20 * Math.log10(wcc / Math.hypot(x, wcc))), "폐루프 (대역폭 ωcc)", { n: 3, color: "#7c3aed" })], l2);
      });
    });
  };

  T.speed = function (tab) {
    tab.section((s) => { s.row(); motorControls(s); });
    tab.section((s) => {
      s.row(); s.radio("scen", "시나리오", ["교재 2.9.3 (0.05 s 에 2500 r/min, 토크 제한 = 정격)", "직접 설정 (지령·부하 단계)"], "교재 2.9.3 (0.05 s 에 2500 r/min, 토크 제한 = 정격)", { horiz: true, wide: true, all: true });
      s.end(); s.row(); s.select("bw", "속도 제어 대역폭", [20, 50, 100], 50, { fmt: (x) => `${x} Hz`, all: true }); s.slider("alpha", "α (1 = PI, 0 = IP)", 0, 1, 0.05, 1);
      s.slider("rpm", "속도 지령 [rpm] (직접 설정)", 200, 3000, 100, 1000); s.slider("TL", "0.15 s 에 걸리는 부하 [N·m] (직접 설정)", 0, 10, 0.5, 4); s.check("cmp", "PI·IP 함께 보기", true);
      s.end(); const p = s.plot(360), tb = s.table(), nt = s.note();
      s.on((v) => {
        const P = motorP(v), book = v.scen.startsWith("교재"), ref = book ? 2500 : v.rpm, t0 = book ? 0.05 : 0.01;
        const o = { wref: (t) => (t >= t0 ? ref / RPM : 0), TL: (t) => (!book && t >= 0.15 ? v.TL : 0), wcs: 2 * Math.PI * v.bw, wcc: 2 * Math.PI * 1000, Ilim: book ? P.I : undefined, tend: book ? 0.2 : 0.3, h: 2e-5 };
        const runs = [["현재 설정", v.alpha, "#d62828"]].concat(v.cmp ? [["PI (α = 1)", 1, "#1d4ed8"], ["IP (α = 0)", 0, "#2a9d8f"]] : []);
        const lay = sub(1, 2, { titles: ["속도 [rpm]", "토크 Te = K·ia [N·m]"] }), tr = [], rows = [];
        let r;
        for (const [nm, a, c] of runs) {
          r = simulate(P, Object.assign({ alpha: a }, o)); const dash = nm === "현재 설정" ? undefined : "dot";
          tr.push(line(r.t, r.w.map((x) => x * RPM), nm, { color: c, dash }), line(r.t, r.ia.map((x) => x * P.K), "", { color: c, dash, n: 2, legend: false }));
          const [os_, trr] = stepMetrics(r.t, r.w, ref / RPM, t0, book ? 1 : 0.15);
          let dip = 0; if (!book) { let mn = Infinity; r.t.forEach((t, k) => { if (t >= 0.15) mn = Math.min(mn, r.w[k]); }); dip = (ref / RPM - mn) * RPM; }
          rows.push([nm, os_.toFixed(1), (trr * 1000).toFixed(1), dip.toFixed(0)]);
        }
        tr.push(line(r.t, r.wref.map((x) => x * RPM), "지령", { color: "#999", dash: "dash" }));
        Object.assign(lay.xaxis, tx("시간 [s]")); Object.assign(lay.xaxis2, tx("시간 [s]"));
        draw(p, tr, lay);
        table(tb, ["제어기", "오버슈트 [%]", "상승 시간 [ms]", "부하 투입 시 속도 저하 [rpm]"], rows);
        const g = r.gains;
        nt.innerHTML = `속도 PI 이득: Kp = J·ωcs/K = ${g.Kps.toFixed(3)} A·s/rad, Ki = Kp·ωcs/5 = ${g.Kis.toFixed(1)} A/rad (전류 제어 1000 Hz)` +
          (book ? "<br>토크 제한(정격 토크)에 걸려 있는 동안 속도는 직선으로 오르고(가속도 = Te정격/J), 지령에 닿으면 토크가 0 근처로 떨어짐 — 교재 그림 2.70." : "");
      });
    });
    tab.section((s) => {
      s.h("속도 제어 개루프 보드 선도와 PI 응답의 두 성분");
      const p = s.plot(340), nt = s.note();
      s.on((v) => {
        const P = motorP(v), w = M.range(400, (i) => Math.pow(10, 5 * i / 399)), lay = sub(1, 2, { titles: ["속도 제어 개루프 보드 (크기 dB)", "PI 폐루프 응답의 두 성분 (전류 제어 이상적)"] });
        const tr = [];
        [[50, "#1d4ed8"], [100, "#d62828"]].forEach(([bw, c]) => { const [Kp, Ki] = speedGains(P, 2 * Math.PI * bw), wcc = 2 * Math.PI * 1000;
          tr.push(line(w, w.map((x) => { const sj = new C(0, x); return 20 * Math.log10(new C(Kp).add(new C(Ki).div(sj)).mul(new C(wcc).div(sj.add(wcc))).mul(new C(P.K).div(sj.scale(P.J))).abs()); }), `ωcs = ${bw} Hz`, { color: c })); });
        const [Kp, Ki] = speedGains(P, 2 * Math.PI * v.bw), a1 = P.K * Kp / P.J, a0 = P.K * Ki / P.J, t = M.linspace(0, 0.06, 300);
        const y1 = M.stepTF([a0], [1, a1, a0], t), y2 = M.stepTF([a1, 0], [1, a1, a0], t);
        tr.push(line(t.map((x) => x * 1000), y1, "ωn²/(s²+2ζωn s+ωn²)", { n: 2, dash: "dot", color: "#2a9d8f" }), line(t.map((x) => x * 1000), y2, "2ζωn s/(…) — 영점 항 (오버슈트의 근원)", { n: 2, dash: "dash", color: "#e76f51" }),
          line(t.map((x) => x * 1000), y1.map((q, i) => q + y2[i]), "합 = PI 응답", { n: 2, width: 3, color: "#264653" }));
        lay.xaxis.type = "log"; Object.assign(lay.xaxis, tx("ω [rad/s]")); Object.assign(lay.xaxis2, tx("시간 [ms]")); lay.shapes = [hline(0, 1)];
        draw(p, tr, lay);
        nt.textContent = `감쇠비 ζ = √(ωcs/ωpi)/2 = √5/2 = ${(a1 / (2 * Math.sqrt(a0))).toFixed(3)} (과감쇠) 인데도 영점 항 때문에 오버슈트가 생김.`;
      });
    });
    tab.section((s) => {
      s.h("같은 오버슈트가 되도록 IP 제어기 대역폭을 키우면 (교재: 약 5.44 배)");
      const p = s.plot(300);
      s.on((v) => {
        const P = motorP(v), o = { wref: (t) => (t >= 0.01 ? 1000 / RPM : 0), TL: (t) => (t >= 0.15 ? 3 : 0), wcc: 2 * Math.PI * 1000, tend: 0.3, h: 2e-5 };
        const a = simulate(P, Object.assign({ alpha: 1, wcs: 2 * Math.PI * v.bw }, o)), b = simulate(P, Object.assign({ alpha: 0, wcs: 2 * Math.PI * v.bw * 5.44 }, o));
        draw(p, [line(a.t, a.w.map((x) => x * RPM), `PI (${v.bw} Hz)`), line(b.t, b.w.map((x) => x * RPM), `IP (${(v.bw * 5.44).toFixed(0)} Hz)`, { color: "#d62828" })],
          { xaxis: tx("시간 [s] (0.15 s 에 부하 3 N·m)"), yaxis: tx("속도 [rpm]") });
      });
    });
  };

  T.chopper = function (tab) {
    const P = TEXTBOOK;
    tab.section((s) => {
      s.row(); s.radio("mode", "방식", ["1상한", "바이폴라", "유니폴라"], "유니폴라", { all: true }); s.slider("va", "평균 전압 지령 Va* [V]", -140, 140, 5, 70, { all: true });
      s.select("fsw", "스위칭 주파수", [1000, 2000, 5000, 10000], 5000, { fmt: (x) => `${x / 1000} kHz`, all: true }); s.slider("rpm", "전동기 속도 (고정) [rpm]", 0, 3000, 50, 1450, { all: true });
      s.slider("tsel", "회로도에 보일 시점 [주기 %]", 0, 99, 1, 20);
      s.end(); const [c0, c1] = s.cols([2, 3]); s.into(c0); const box = s.svg(320); s.into(c1); const p = s.plot(560); s.end(); const tb = s.table();
      s.on((v) => {
        const va = v.mode === "1상한" ? Math.max(0, v.va) : v.va, E = P.K * v.rpm / RPM, w = chopper(v.mode, P.V, va, v.fsw, P.Ra, P.La, E);
        const k = Math.min(w.t.length - 1, Math.floor(v.tsel / 100 * w.t.length / 3));
        let st, title;
        if (v.mode === "1상한") { st = { T1: w.S1[k], T4: 1 }; title = "1상한 초퍼 (T4 항상 켜짐, T2 쪽 다이오드로 환류)"; }
        else if (v.mode === "바이폴라") { st = { T1: w.S1[k], T4: w.S1[k], T2: w.S2[k], T3: w.S2[k] }; title = "바이폴라: 대각 스위치 (T1·T4) ↔ (T2·T3) 를 쌍으로"; }
        else { st = { T1: w.S1[k], T2: 1 - w.S1[k], T3: w.S2[k], T4: 1 - w.S2[k] }; title = "유니폴라: A 레그는 Va*, B 레그는 −Va* 와 삼각파 비교"; }
        box.innerHTML = hbridgeSVG(st, Math.sign(w.i[k]), `va = ${w.v[k] >= 0 ? "+" : ""}${w.v[k].toFixed(0)} V`, title);
        const tm = w.t.map((x) => x * 1000), lay = sub(4, 1, { titles: ["삼각 반송파와 지령", "스위칭 신호", "출력 전압 va [V]", "전기자 전류 ia [A]"], sharex: true, ygap: 0.07 });
        lay.shapes = [hline(va / P.V, 1, { color: "#d62828", dash: "solid" }), hline(M.mean(w.v), 3, { color: "#e76f51" })].concat(M.range(4, (i) => vline(tm[k], i + 1, { color: "#16a34a" })));
        if (v.mode === "유니폴라") lay.shapes.push(hline(-va / P.V, 1, { color: "#1d4ed8", dash: "solid" }));
        Object.assign(lay.xaxis4, tx("시간 [ms]"));
        draw(p, [line(tm, v.mode === "1상한" ? w.tri.map((x) => (x + 1) / 2) : w.tri, "반송파", { color: "#999" }), line(tm, w.S1, "Sa (T1)", { n: 2, shape: "hv", color: "#d62828" }),
          line(tm, w.S2.map((x) => x * 0.9), v.mode === "유니폴라" ? "Sb (T3)" : "T2·T3", { n: 2, shape: "hv", color: "#1d4ed8" }), line(tm, w.v, "va", { n: 3, shape: "hv", color: "#264653" }),
          line(tm, w.i, "ia", { n: 4, color: "#e76f51" })], Object.assign(lay, { showlegend: false, margin: { b: 40 } }));
        table(tb, ["방식", "평균 전압 [V]", "전류 리플 (최대−최소) [A]"], ["바이폴라", "유니폴라"].map((mm) => { const q = chopper(mm, P.V, va, v.fsw, P.Ra, P.La, E); return [mm, M.mean(q.v).toFixed(1), M.ptp(q.i).toFixed(2)]; }));
      });
    });
    tab.section((s) => {
      s.h("지령 Va* 를 +Vdc 에서 −Vdc 로 천천히 바꿀 때의 출력 전압");
      const p = s.plot(300); s.note("바이폴라: 0 V 근처에서도 ±Vdc 펄스 (부드럽게 0 을 지남). 유니폴라: + 쪽은 +Vdc/0, − 쪽은 0/−Vdc 펄스.");
      const lay = sub(1, 2, { titles: ["바이폴라", "유니폴라"] }), tr = [];
      ["바이폴라", "유니폴라"].forEach((mm, i) => { const r = chopperRamp(mm, P.V, 1000), t = r.t.map((x) => x * 1000);
        tr.push(line(t, r.v, `${mm} va`, { n: i + 1, width: 1, shape: "hv", color: COL[i] }), line(t, r.vr, "평균 전압 Va*", { n: i + 1, color: "#d62828" })); });
      Object.assign(lay.xaxis, tx("시간 [ms]")); Object.assign(lay.xaxis2, tx("시간 [ms]"));
      draw(p, tr, Object.assign(lay, { showlegend: false, margin: { b: 40 } }));
    });
    tab.section((s) => {
      s.h("2.9.4 초퍼가 포함된 전체 구동 시스템 (속도 PI → 전류 PI → 초퍼 스위칭 → 전동기)");
      s.row(); s.radio("dm", "PWM 방식", ["유니폴라", "바이폴라"], "유니폴라", { horiz: true }); s.select("df", "스위칭 주파수", [2000, 5000, 10000], 5000, { fmt: (x) => `${x / 1000} kHz` });
      s.select("dbw", "속도 제어 대역폭", [20, 50], 50, { fmt: (x) => `${x} Hz` });
      s.end(); const p = s.plot(320), pz = s.plot(460); s.note("초퍼가 만든 PWM 전압 때문에 전기자 전류와 토크에 스위칭 주파수 리플이 남음 (교재 그림 2.72).");
      s.on((v) => {
        const { R, Z } = chopperDrive(P, v.dm, v.df, v.dbw);
        const lay = sub(1, 2, { titles: ["속도 지령·속도 [r/min]", "전기자 전류 Ia [A] · 토크 Te [N·m]"] });
        Object.assign(lay.xaxis, tx("시간 [s]")); Object.assign(lay.xaxis2, tx("시간 [s]"));
        draw(p, [line(R.t, R.t.map((t) => (t >= 0.05 ? 2500 : 0)), "지령", { dash: "dash", color: "#999" }), line(R.t, R.w.map((x) => x * RPM), "속도"),
          line(R.t, R.ia, "Ia", { n: 2, width: 1, color: "#d62828" }), line(R.t, R.Te, "Te", { n: 2, width: 1, color: "#2a9d8f" })], lay);
        const lz = sub(3, 1, { titles: ["Vref 와 반송파", "스위칭 펄스 Sa, Sb", "출력 전압 Va 와 전류 Ia"], sharex: true });
        Object.assign(lz.xaxis3, tx("시간 [ms] (t = 0.1 s 부근 확대)"));
        const tr = [line(Z.t, Z.tri, "반송파", { color: "#999" }), line(Z.t, Z.vref, "Vref/Vdc", { color: "#d62828" })];
        if (v.dm === "유니폴라") tr.push(line(Z.t, Z.vref.map((x) => -x), "−Vref/Vdc", { color: "#1d4ed8" }));
        tr.push(line(Z.t, Z.Sa.map((x) => x + 1.2), "Sa", { n: 2, shape: "hv", color: "#d62828" }), line(Z.t, Z.Sb, "Sb", { n: 2, shape: "hv", color: "#1d4ed8" }),
          line(Z.t, Z.va, "Va", { n: 3, shape: "hv", color: "#264653" }), line(Z.t, Z.ia.map((x) => x * 4), "Ia × 4", { n: 3, color: "#e76f51" }));
        draw(pz, tr, lz);
      });
    });
  };

  const api = Object.assign(T, { _calc: { TEXTBOOK, EXAMPLE2, vToSpeed, voltageStep, simulate, stepMetrics, chopper, chopperDrive, loopBode, rlDemo, capability, currentGains, speedGains } });
  root.LabCh2 = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
