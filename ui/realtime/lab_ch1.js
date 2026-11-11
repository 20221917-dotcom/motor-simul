/* 강의 실습 1장 (브라우저 계산). 계산식은 lectures/ch1.py 와 같음. */
(function (root) {
  "use strict";
  const { M, metric, sub, ax, hline, vline, label, line, pts, draw, tx, COL } = root.Lab;
  const MU0 = 4e-7 * Math.PI, G = 9.81, RPM = M.RPM;

  // ---------------------------------------------------------------- 계산
  function fluxDensity(F, g, lc = 0.3, mur = 4000, Bs = 1.6) {
    let lo = -Bs * (1 - 1e-12), hi = Bs * (1 - 1e-12);
    for (let k = 0; k < 60; k++) {
      const B = 0.5 * (lo + hi);
      const f = Bs / (mur * MU0) * Math.atanh(B / Bs) * lc + B * g / MU0 - F;
      if (f > 0) hi = B; else lo = B;
    }
    return 0.5 * (lo + hi);
  }
  const lambdaI = (i, o) => (o.N || 200) * (o.A || 4e-4) * fluxDensity((o.N || 200) * i, o.g, 0.3, 4000, o.Bs || 1.6);
  function energyCoenergy(imax, o, n = 200) {
    const i = M.linspace(0, imax, n), lam = i.map((x) => lambdaI(x, o));
    const Wc = M.trapz(lam, i), W = i[n - 1] * lam[n - 1] - Wc;
    return { W, Wc, i, lam };
  }
  function gapForce(i, g, N) { const dg = 1e-6, o = { N }; return (energyCoenergy(i, Object.assign({}, o, { g: g + dg }), 120).Wc - energyCoenergy(i, Object.assign({}, o, { g: Math.max(g - dg, 1e-7) }), 120).Wc) / (2 * dg); }
  const gapForceLinear = (i, g, N, A = 4e-4) => -0.5 * i * i * N * N * MU0 * A / ((g + 0.3 / 4000) ** 2);
  function linearPaths(i0, x1, x2) {
    const i = M.linspace(0, i0 * 1.6, 160), o1 = { g: x1 }, o2 = { g: x2 };
    const lam1 = i.map((x) => lambdaI(x, o1)), lam2 = i.map((x) => lambdaI(x, o2));
    const lA = lambdaI(i0, o1), lB = lambdaI(i0, o2), iC = M.interp(lA, lam2, i);
    const WA = energyCoenergy(i0, o1).W, WC = iC > 0 ? energyCoenergy(iC, o2).W : 0;
    const Wslow = energyCoenergy(i0, o2).Wc - energyCoenergy(i0, o1).Wc;
    return { i, lam1, lam2, A: [i0, lA], B: [i0, lB], C: [iC, lA], Wfast: WA - WC, Wslow };
  }
  const relT = (t, Im, ws, wm, d, L2) => -((Im * Math.cos(ws * t)) ** 2) * L2 * Math.sin(2 * (wm * t - d));
  function relAvg(Im, ws, wm, d, L2, cycles = 60, per = 400) {
    const n = cycles * per, T = 2 * Math.PI / ws * cycles; let s = 0;
    for (let k = 0; k < n; k++) s += relT(T * k / n, Im, ws, wm, d, L2);
    return s / n;
  }
  const dblT = (t, ws, wr, wm, th0) => -Math.cos(ws * t) * Math.cos(wr * t) * Math.sin(wm * t + th0);
  function dblAvg(ws, wr, wm, th0, T = 30, n = 9000) { let s = 0; for (let k = 0; k < n; k++) s += dblT(T * k / n, ws, wr, wm, th0); return s / n; }
  const LOADS = ["일정 토크 부하 (크레인·컨베이어)", "일정 출력 부하 (압연기·권취기)", "속도 제곱 부하 (팬·펌프·송풍기)"];
  function loadT(kind, w, T0, wref) {
    const a = Math.abs(w), sg = w === 0 ? 1 : Math.sign(w);
    if (kind.startsWith("일정 토크")) return T0 * sg;
    if (kind.startsWith("일정 출력")) return Math.min(T0 * wref / Math.max(a, 1e-9), 3 * T0) * sg;
    return T0 * (a / wref) ** 2 * sg;
  }
  const dcT = (w, V, K, Ra) => K * (V - K * w) / Ra;
  function opPoint(kind, V, K, Ra, T0, wref) {
    const f = (w) => dcT(w, V, K, Ra) - loadT(kind, w, T0, wref);
    let lo = 1e-6, hi = V / K; if (f(lo) < 0) return 0;
    for (let k = 0; k < 80; k++) { const m = 0.5 * (lo + hi); if (f(m) > 0) lo = m; else hi = m; }
    return 0.5 * (lo + hi);
  }
  function startup(kind, V, K, Ra, T0, wref, J, n = 1500) {
    const wop = opPoint(kind, V, K, Ra, T0, wref), tau = J * Ra / (K * K), tend = Math.max(6 * tau, 1e-3), h = tend / n;
    const acc = (x) => { const TL = (Math.abs(x) < 1e-9 && kind.startsWith("일정 토크") && dcT(0, V, K, Ra) < T0) ? 0 : loadT(kind, x, T0, wref); return (dcT(x, V, K, Ra) - TL) / J; };
    const t = [0], w = [0]; let x = 0;
    for (let k = 0; k < n; k++) {
      const k1 = acc(x), k2 = acc(x + h / 2 * k1), k3 = acc(x + h / 2 * k2), k4 = acc(x + h * k3);
      x = Math.max(0, x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)); t.push((k + 1) * h); w.push(x);
    }
    return { t, w, wop };
  }
  function elevator(mc, ml, mw, v, r) {
    const T = (mc + ml - mw) * G * r, w = v / r, P = T * w;
    const q = w >= 0 ? (T >= 0 ? 1 : 2) : (T <= 0 ? 3 : 4);
    return { T, w, P, q };
  }

  // ---------------------------------------------------------------- 탭
  const T = {};

  T.principle = function (tab) {
    tab.section((s) => {
      s.h("① 로렌츠의 힘: 자계 안의 전류가 흐르는 도체");
      s.row();
      s.slider("B", "자속 밀도 B [T]", 0.1, 2.0, 0.05, 0.8);
      s.slider("I", "전류 I [A]", 0, 50, 1, 10);
      s.slider("l", "도체 길이 l [m]", 0.05, 0.5, 0.01, 0.2);
      s.slider("r", "회전 반지름 r [m]", 0.01, 0.2, 0.01, 0.05);
      s.end(); const m = s.metrics(3);
      s.on((v) => {
        metric(m[0], "힘 F = I·l·B", `${(v.I * v.l * v.B).toFixed(2)} N`);
        metric(m[1], "토크 T = r × F (도체 1개)", `${(v.I * v.l * v.B * v.r).toFixed(3)} N·m`);
        metric(m[2], "힘의 방향", "플레밍 왼손 법칙", "자계 ⊥ 전류 ⊥ 힘");
      });
    });
    tab.section((s) => {
      s.h("② 두 자석 사이의 회전력: 회전자 축이 고정자 자계에서 θ 만큼 벗어나 있을 때");
      const [c0, c1, c2] = s.cols([1, 2, 2]);
      s.into(c0); s.slider("th", "회전자 각 θ [°]", -180, 180, 1, 60);
      s.radio("k", "회전자", ["자석–자석", "자석–자성체 (릴럭턴스)"], "자석–자석");
      s.into(c1); const p1 = s.plot(300); s.into(c2); const p2 = s.plot(300);
      const x = M.linspace(-180, 180, 361);
      s.on((v) => {
        const mm = v.k === "자석–자석", f = (d) => (mm ? Math.sin(M.rad(d)) : 0.5 * Math.sin(2 * M.rad(d)));
        draw(p1, [line(x, x.map(f), "복원 토크"), pts([v.th], [f(v.th)], "현재")],
          { xaxis: Object.assign(tx("θ [°]"), { dtick: 45 }), yaxis: tx("토크 (단위값, + = θ 를 줄이는 쪽)") });
        const tr = [{ type: "scatterpolar", r: [0, 1], theta: [0, 0], mode: "lines+markers", line: { color: "#1d4ed8", width: 5 }, name: "고정자 자계 (N→)" }];
        tr.push(mm ? { type: "scatterpolar", r: [0, 0.8], theta: [0, v.th], mode: "lines+markers", line: { color: "#d62828", width: 5 }, name: "회전자 자석 N" }
          : { type: "scatterpolar", r: [0.8, 0, 0.8], theta: [v.th, 0, v.th + 180], mode: "lines", line: { color: "#555", width: 10 }, name: "자성체 회전자 (돌극)" });
        draw(p2, tr, { polar: { radialaxis: { visible: false, range: [0, 1.05] } }, margin: { l: 20, r: 20, t: 20, b: 50 }, legend: { y: -0.08 } });
      });
    });
  };

  T.magnetic = function (tab) {
    tab.section((s) => {
      s.row();
      s.slider("N", "코일 권수 N", 50, 500, 10, 200);
      s.slider("g", "공극 길이 x [mm]", 0.1, 3.0, 0.1, 1.0);
      s.slider("im", "코일 전류 i [A]", 0.5, 30, 0.5, 8);
      s.slider("Bs", "철심 포화 자속 밀도 Bs [T]", 0.8, 2.0, 0.1, 1.6);
      s.end(); const p = s.plot(400), m = s.metrics(4);
      const i = M.linspace(0, 30, 241);
      s.on((v) => {
        const tr = [], lay = sub(1, 2, { titles: ["λ-i 특성 (공극 길이별)", "인덕턴스 L = λ/i 와 증분 dλ/di"] });
        let lamG = null;
        for (const [gg, col, w] of [[v.g * 0.5, "#94a3b8", 1.6], [v.g, "#d62828", 3], [v.g * 2, "#1d4ed8", 1.6]]) {
          const lam = i.map((x) => lambdaI(x, { N: v.N, g: gg * 1e-3, Bs: v.Bs }));
          tr.push(line(i, lam, `x = ${(+gg).toPrecision(2)} mm`, { color: col, width: w }));
          if (gg === v.g) lamG = lam;
        }
        const ec = energyCoenergy(v.im, { N: v.N, g: v.g * 1e-3, Bs: v.Bs });
        tr.push(line(ec.i.concat([0]), ec.lam.concat([ec.lam[ec.lam.length - 1]]), "자기 에너지 W (곡선 위쪽)", { fill: "toself", fillcolor: "rgba(214,40,40,0.15)", width: 0.1 }));
        tr.push(line(ec.i.concat([ec.i[ec.i.length - 1]]), ec.lam.concat([0]), "코에너지 W′ (곡선 아래쪽)", { fill: "toself", fillcolor: "rgba(29,78,216,0.12)", width: 0.1 }));
        tr.push(line(i.slice(1), lamG.slice(1).map((l, k) => l / i[k + 1] * 1e3), "L = λ/i [mH]", { color: "#d62828", n: 2 }));
        tr.push(line(i, M.gradient(lamG, i).map((x) => x * 1e3), "dλ/di [mH]", { color: "#d62828", dash: "dot", n: 2 }));
        Object.assign(lay.xaxis, tx("전류 i [A]")); Object.assign(lay.xaxis2, tx("전류 i [A]"));
        Object.assign(lay.yaxis, tx("쇄교 자속 λ [Wb·turn]")); Object.assign(lay.yaxis2, tx("[mH]"));
        draw(p, tr, lay);
        const lamE = ec.lam[ec.lam.length - 1], B = lamE / (v.N * 4e-4);
        metric(m[0], "쇄교 자속 λ", `${lamE.toFixed(4)} Wb·t`);
        metric(m[1], "자기 에너지 W = ∫i dλ", `${ec.W.toFixed(3)} J`);
        metric(m[2], "코에너지 W′ = ∫λ di", `${ec.Wc.toFixed(3)} J`, "선형이면 W = W′ = ½Li²");
        metric(m[3], "자속 밀도 B", `${B.toFixed(2)} T`, B > 0.85 * v.Bs ? "포화 영역" : "선형 영역");
      });
    });
    tab.section((s) => {
      s.h("코일의 유도 기전력 (패러데이 법칙 e = −dλ/dt, 렌츠의 법칙)");
      s.row(); s.slider("fm", "자석이 오가는 주파수 [Hz]", 0.5, 10, 0.5, 2); s.slider("lm", "최대 쇄교 자속 λmax [Wb·turn]", 0.01, 0.5, 0.01, 0.1);
      s.end(); const p = s.plot(360), nt = s.note();
      s.on((v) => {
        const t = M.linspace(0, 2 / v.fm, 400), lam = t.map((x) => v.lm * 0.5 * (1 - Math.cos(2 * Math.PI * v.fm * x)));
        const e = M.gradient(lam, t).map((x) => -x);
        const lay = sub(2, 1, { titles: ["쇄교 자속 λ (자석이 다가오면 증가)", "유도 기전력 e = −dλ/dt"], sharex: true });
        Object.assign(lay.xaxis2, tx("시간 [s]"));
        draw(p, [line(t, lam, "λ"), line(t, e, "e", { n: 2, color: "#d62828" })], lay);
        nt.innerHTML = `최대 기전력 = π·f·λmax = ${(Math.PI * v.fm * v.lm).toFixed(3)} V. 자석이 다가올 때(λ 증가) e 는 음, 멀어질 때 양 — 유도 전류는 언제나 자속 변화를 방해하는 방향 (렌츠의 법칙).`;
      });
    });
  };

  T.force = function (tab) {
    tab.section((s) => {
      s.h("① 직선 운동 기계 (단일 여자): 운동자에 걸리는 힘 F = ∂W′/∂x");
      s.row(); s.slider("fN", "권수 N", 50, 500, 10, 200); s.slider("fi", "전류 i [A]", 0.5, 20, 0.5, 3);
      s.end(); const p = s.plot(330);
      s.note("공극이 좁을수록 인덕턴스가 커지므로, 힘은 언제나 공극을 줄이는(인덕턴스가 커지는) 쪽으로 작용합니다. 포화되면 해석해(점선)보다 힘이 작아집니다.");
      s.on((v) => {
        const xg = M.linspace(0.2, 5, 40);
        const L = xg.map((x) => lambdaI(v.fi, { N: v.fN, g: x * 1e-3 }) / v.fi * 1e3);
        const F = xg.map((x) => gapForce(v.fi, x * 1e-3, v.fN)), Fl = xg.map((x) => gapForceLinear(v.fi, x * 1e-3, v.fN));
        const lay = sub(1, 2, { titles: ["공극에 따른 인덕턴스 L(x)", "운동자에 걸리는 힘 (− = 공극을 줄이는 쪽)"] });
        Object.assign(lay.xaxis, tx("공극 x [mm]")); Object.assign(lay.xaxis2, tx("공극 x [mm]"));
        Object.assign(lay.yaxis, tx("[mH]")); Object.assign(lay.yaxis2, tx("F [N]"));
        draw(p, [line(xg, L, "L [mH]"), line(xg, F, "힘 (포화 포함)", { n: 2, color: "#d62828" }), line(xg, Fl, "힘 (선형 해석해 ½i²dL/dx)", { n: 2, dash: "dot", color: "#2a9d8f" })], lay);
      });
    });
    tab.section((s) => {
      s.h("운동자가 x1 → x2 로 움직일 때 λ-i 평면의 동작점 이동 (빠른 이동 vs 느린 이동)");
      s.row(); s.slider("pi", "코일 전류 i [A]", 0.5, 10, 0.5, 3); s.slider("x1", "이동 전 공극 x1 [mm]", 0.5, 4, 0.1, 2); s.slider("x2", "이동 후 공극 x2 [mm]", 0.2, 3.5, 0.1, 1);
      s.end(); const p = s.plot(340), m = s.metrics(2);
      s.on((v) => {
        const r = linearPaths(v.pi, v.x1 * 1e-3, Math.min(v.x2, v.x1 - 0.1) * 1e-3);
        const lay = sub(1, 2, { titles: ["매우 빨리 이동 (λ 일정: A → C → B)", "매우 느리게 이동 (i 일정: A → B)"] });
        const tr = [];
        for (const n of [1, 2]) {
          tr.push(line(r.i, r.lam1, "x = x1", { color: "#1d4ed8", n, legend: n === 1 }));
          tr.push(line(r.i, r.lam2, "x = x2 (공극 감소)", { color: "#d62828", n, legend: n === 1 }));
        }
        const [A, B, Cc] = [r.A, r.B, r.C];
        tr.push(line([0, A[0], Cc[0], 0], [0, A[1], Cc[1], 0], "기계적 에너지 = 면적 OAC", { fill: "toself", fillcolor: "rgba(42,157,143,0.3)", color: "#2a9d8f" }));
        tr.push(pts([A[0], Cc[0], B[0]], [A[1], Cc[1], B[1]], "", { text: ["A", "C", "B"], color: "#111", size: 8, legend: false }));
        tr.push(line([0, A[0], B[0], 0], [0, A[1], B[1], 0], "기계적 에너지 = 면적 OAB", { fill: "toself", fillcolor: "rgba(233,196,106,0.4)", color: "#e9c46a", n: 2 }));
        tr.push(pts([A[0], B[0]], [A[1], B[1]], "", { text: ["A", "B"], color: "#111", size: 8, legend: false, n: 2 }));
        Object.assign(lay.xaxis, tx("i [A]")); Object.assign(lay.xaxis2, tx("i [A]")); Object.assign(lay.yaxis, tx("λ [Wb·turn]"));
        draw(p, tr, lay);
        metric(m[0], "빠른 이동의 기계적 에너지", `${(r.Wfast * 1000).toFixed(1)} mJ`, "자기 에너지에서 나옴 (전원 공급 없음)");
        metric(m[1], "느린 이동의 기계적 에너지", `${(r.Wslow * 1000).toFixed(1)} mJ`, "코에너지 증가분 (전원이 공급)");
      });
    });
    tab.section((s) => {
      s.h("교재 예제 1: L(x) = 5×10⁻³·x [H], 전류 2 A, 스프링 k = 5 N/m 일 때 힘과 이동 거리");
      s.row(); s.slider("ei", "전류 [A]", 0.5, 5, 0.5, 2); s.num("edL", "dL/dx [H/m]", 0.001, 0.05, 0.001, 0.005); s.slider("ek", "스프링 상수 k [N/m]", 1, 20, 0.5, 5);
      s.end(); const m = s.metrics(2);
      s.on((v) => { const F = 0.5 * v.ei * v.ei * v.edL; metric(m[0], "힘 Fm = ½ i² dL/dx", `${F.toFixed(3)} N`); metric(m[1], "이동 거리 Δx = Fm / k", `${(F / v.ek * 100).toFixed(2)} cm`); });
    });
    tab.section((s) => {
      s.h("② 회전 기계의 릴럭턴스 토크: L(θ) = L0 + L2·cos2θ, T = ½i²·dL/dθ");
      const pL = s.plot(250);
      s.row(); s.slider("ratio", "회전자 속도 ωm / 전류 각주파수 ωs", 0, 2, 0.05, 1); s.slider("delta", "초기 위치(부하각) δ [°]", -90, 90, 5, 30);
      s.end(); const p = s.plot(330), m = s.metrics(2);
      const th = M.linspace(0, 360, 361);
      draw(pL, [line(th, th.map((d) => 1 + 0.5 * Math.cos(M.rad(2 * d))), "Lss(θ)")], {
        xaxis: Object.assign(tx("회전자 위치 θ [°]"), { dtick: 90 }), yaxis: tx("고정자 자기 인덕턴스 (상대값)"), showlegend: false,
        shapes: [hline(1.5), hline(0.5), hline(1.0, 1, { dash: "dash" })],
        annotations: [label(300, 1.56, "Lmax (θ = 0°, 180°: 돌극이 자계 방향)"), label(300, 0.44, "Lmin (θ = 90°, 270°)"), label(300, 1.06, "L0 = (Lmax + Lmin)/2")],
        margin: { b: 40 } });
      const Im = 10, L2 = 0.01, ws = 2 * Math.PI * 10;
      let cacheD = null, cacheAvg = null;
      s.on((v) => {
        const t = M.linspace(0, 0.4, 1200), d = M.rad(v.delta);
        const Tq = t.map((x) => relT(x, Im, ws, v.ratio * ws, d, L2)), Tavg = relAvg(Im, ws, v.ratio * ws, d, L2);
        const rr = M.linspace(0, 2, 81);
        if (cacheD !== v.delta) { cacheD = v.delta; cacheAvg = rr.map((r) => relAvg(Im, ws, r * ws, d, L2, 60, 160)); }
        const lay = sub(1, 2, { titles: ["순시 토크 (전류 4주기)", "평균 토크 vs ωm/ωs"] });
        lay.shapes = [hline(Tavg, 1, { color: "#d62828", dash: "dash" })];
        Object.assign(lay.xaxis, tx("시간 [ms]")); Object.assign(lay.xaxis2, tx("ωm / ωs")); Object.assign(lay.yaxis, tx("T [N·m]"));
        draw(p, [line(t.map((x) => x * 1000), Tq, "순시 토크"), Object.assign(line(rr, cacheAvg, "평균 토크", { n: 2, color: "#2a9d8f" }), { mode: "lines+markers", marker: { size: 4 } }),
          pts([v.ratio], [Tavg], "현재", { n: 2 })], lay);
        metric(m[0], "평균 토크 (계산)", `${Tavg.toFixed(4)} N·m`);
        metric(m[1], "동기일 때 해석해 (Im²L2/4)·sin2δ", `${(0.25 * Im * Im * L2 * Math.sin(2 * d)).toFixed(4)} N·m`);
      });
    });
  };

  const MACH = {
    "직류 전동기": ["고정자 직류(ωs = 0), 회전자 교류: 정류자가 회전자 전류 주파수를 ωr = ωm 으로 맞춰 줌", 0, 20, 20],
    "동기 전동기": ["고정자 교류 ωs, 회전자 직류(ωr = 0): 회전자가 ωm = ωs (동기 속도)로 돌아야 함", 20, 0, 20],
    "유도 전동기": ["고정자 교류 ωs, 회전자 교류 ωr = ωs − ωm (슬립 주파수): 저절로 만족됨", 20, 1, 19],
  };
  T.double = function (tab) {
    tab.section((s) => {
      const [c0, c1] = s.cols([2, 3]);
      s.into(c0);
      const info = el => el;
      s.radio("kind", "전동기 종류로 맞추기 (고르면 아래 값이 그 조건으로 맞춰짐)", Object.keys(MACH), "직류 전동기");
      s.into(c1); const box = s.html(""); box.className = "info";
      s.end(); s.row();
      const sws = s.slider("ws", "고정자 전류 각주파수 ωs [rad/s]", 0, 40, 0.5, 0);
      const swr = s.slider("wr", "회전자 전류 각주파수 ωr [rad/s]", 0, 40, 0.5, 20);
      const swm = s.slider("wm", "회전자 속도 ωm [rad/s]", 0, 40, 0.5, 20);
      s.slider("th0", "회전자 초기 각 θ0 [°]", -180, 180, 15, -90);
      s.end(); const p = s.plot(340), m = s.metrics(1);
      let lastKind = null, cacheKey = null, cacheAv = null;
      s.on((v) => {
        if (lastKind !== null && lastKind !== v.kind) {     // 종류를 바꾸면 그 조건 값으로 슬라이더를 맞춤
          const [, a, b, c] = MACH[v.kind];
          for (const [inp, key, val] of [[sws, "ws", a], [swr, "wr", b], [swm, "wm", c]]) { inp.value = val; inp.dispatchEvent(new Event("input")); v[key] = val; }
        }
        lastKind = v.kind; box.textContent = MACH[v.kind][0];
        const th0 = M.rad(v.th0), t = M.linspace(0, 3, 1500);
        const Tq = t.map((x) => dblT(x, v.ws, v.wr, v.wm, th0)), avg = dblAvg(v.ws, v.wr, v.wm, th0);
        const sw = M.linspace(0, 40, 161), key = [v.ws, v.wr, v.th0].join();
        if (key !== cacheKey) { cacheKey = key; cacheAv = sw.map((w) => dblAvg(v.ws, v.wr, w, th0, 30, 6000)); }
        const lay = sub(1, 2, { titles: ["순시 토크 (단위값)", "평균 토크 vs 회전자 속도 ωm"] });
        lay.shapes = [hline(avg, 1, { color: "#d62828", dash: "dash" }), vline(v.ws + v.wr, 2), vline(Math.abs(v.ws - v.wr), 2)];
        lay.annotations.push({ x: v.ws + v.wr, y: 1, xref: "x2", yref: "y2 domain", text: "ωs+ωr", showarrow: false, yanchor: "bottom" },
          { x: Math.abs(v.ws - v.wr), y: 0.92, xref: "x2", yref: "y2 domain", text: "|ωs−ωr|", showarrow: false });
        Object.assign(lay.xaxis, tx("시간 [s]")); Object.assign(lay.xaxis2, tx("ωm [rad/s]"));
        draw(p, [line(t, Tq, "순시 토크"), line(sw, cacheAv, "평균 토크", { n: 2, color: "#2a9d8f" }), pts([v.wm], [avg], "현재", { n: 2 })], lay);
        metric(m[0], "평균 토크", `${avg.toFixed(3)} (단위값)`);
      });
    });
  };

  T.load = function (tab) {
    const K = 0.4058, Ra = 0.5, wref = 1000 / RPM;
    tab.section((s) => {
      s.row();
      s.select("kind", "부하 종류", LOADS, LOADS[0], { all: true });
      s.slider("T0", "기준 부하 토크 (1000 rpm 에서) [N·m]", 0.5, 20, 0.5, 6, { all: true });
      s.slider("V", "전동기 전압 V [V]", 20, 140, 5, 140, { all: true });
      s.slider("J", "관성 J [kg·m²] (전동기+부하)", 0.001, 0.05, 0.001, 0.01);
      s.end(); const p = s.plot(360), m = s.metrics(3);
      s.note("전동기는 Kφ = 0.406 V·s/rad, Ra = 0.5 Ω 의 직류 전동기입니다. 운전점은 두 곡선의 교점이고, 관성 J 가 클수록 그 점까지 가는 데 오래 걸립니다.");
      s.on((v) => {
        const w = M.linspace(0, v.V / K * 1.05, 200), st = startup(v.kind, v.V, K, Ra, v.T0, wref, v.J);
        const lay = sub(1, 2, { titles: ["토크–속도: 전동기 곡선과 부하 곡선", "기동 과정 (속도)"] });
        const tr = [line(w.map((x) => x * RPM), w.map((x) => dcT(x, v.V, K, Ra)), "전동기 토크 Te"),
          line(w.map((x) => x * RPM), w.map((x) => loadT(v.kind, x, v.T0, wref)), "부하 토크 TL", { color: "#d62828" })];
        for (const k of LOADS) if (k !== v.kind) tr.push(line(w.map((x) => x * RPM), w.map((x) => loadT(k, x, v.T0, wref)), k.split(" (")[0], { dash: "dot", width: 1 }));
        tr.push(pts([st.wop * RPM], [loadT(v.kind, st.wop, v.T0, wref)], "운전점"));
        tr.push(line(st.t, st.w.map((x) => x * RPM), "속도 [rpm]", { n: 2, color: "#2a9d8f" }));
        Object.assign(lay.yaxis, tx("토크 [N·m]"), { range: [0, Math.max(3 * v.T0, 10)] }); Object.assign(lay.yaxis2, tx("rpm"));
        Object.assign(lay.xaxis, tx("속도 [rpm]")); Object.assign(lay.xaxis2, tx("시간 [s]"));
        draw(p, tr, lay);
        const TLop = loadT(v.kind, st.wop, v.T0, wref);
        metric(m[0], "운전점 속도", `${(st.wop * RPM).toFixed(0)} rpm`); metric(m[1], "운전점 토크", `${TLop.toFixed(2)} N·m`); metric(m[2], "필요 출력 P = T·ω", `${(TLop * st.wop).toFixed(0)} W`);
      });
    });
    tab.section((s) => {
      s.h("부하 종류별 요구 전력 (일정 토크 → P ∝ ω, 일정 출력 → P 일정, 속도 제곱 → P ∝ ω³)");
      const p = s.plot(300);
      s.on((v) => {
        const w = M.linspace(0, v.V / K * 1.05, 200);
        draw(p, LOADS.map((k, i) => line(w.map((x) => x * RPM), w.map((x) => loadT(k, x, v.T0, wref) * x / 1000), k.split(" (")[0], { width: k === v.kind ? 3 : 1.5, color: COL[i] })),
          { xaxis: tx("속도 [rpm]"), yaxis: Object.assign(tx("부하 요구 전력 P = TL·ω [kW]"), { rangemode: "tozero" }) });
      });
    });
    tab.section((s) => {
      s.h("회전체의 관성 모멘트 J = ½ m r² (같은 질량이라도 반지름이 크면 J 가 큼)");
      s.row(); s.slider("mJ", "질량 m [kg]", 0.5, 50, 0.5, 10); s.slider("rJ", "반지름 r [m]", 0.02, 0.5, 0.01, 0.1);
      s.end(); const m = s.metrics(2);
      s.on((v) => { metric(m[0], "원통·원판 J = ½ m r²", `${(0.5 * v.mJ * v.rJ * v.rJ).toFixed(4)} kg·m²`); metric(m[1], "얇은 링 J = m r²", `${(v.mJ * v.rJ * v.rJ).toFixed(4)} kg·m²`); });
    });
    tab.section((s) => {
      s.h("기어·벨트와 직선 운동 부하를 전동기 축에서 보면");
      s.row(); s.slider("gn", "감속비 n = ωm/ωL", 1, 20, 0.5, 5); s.num("gJL", "부하 관성 JL [kg·m²]", 0, 10, 0.05, 0.5);
      s.num("gTL", "부하 축 토크 TL [N·m]", 0, 500, 5, 50); s.num("gm", "직선 운동 질량 m [kg]", 0, 5000, 10, 200); s.num("gr", "드럼·바퀴 반지름 r [m]", 0.01, 1, 0.01, 0.15);
      s.end(); const m = s.metrics(3);
      s.on((v) => {
        const Jl = v.gm * v.gr * v.gr, Jeq = 0.01 + (v.gJL + Jl) / (v.gn * v.gn);
        metric(m[0], "직선 부하의 등가 관성 m·r²", `${Jl.toFixed(3)} kg·m²`);
        metric(m[1], "전동기 축 등가 관성 Jm + (JL + m r²)/n²", `${Jeq.toFixed(4)} kg·m²`, "Jm = 0.01 으로 가정");
        metric(m[2], "전동기 축 부하 토크 TL/n", `${(v.gTL / v.gn).toFixed(2)} N·m`);
      });
    });
  };

  T.quadrant = function (tab) {
    const names = { 1: "1상한: 정방향 전동기 모드", 2: "2상한: 정방향 제동(발전기) 모드", 3: "3상한: 역방향 전동기 모드", 4: "4상한: 역방향 제동(발전기) 모드" };
    tab.section((s) => {
      s.row();
      s.slider("mc", "빈 카 질량 [kg]", 300, 1500, 50, 800); s.slider("ml", "승객 질량 [kg]", 0, 1200, 50, 600);
      s.slider("mw", "균형추 질량 [kg]", 300, 2500, 50, 1100); s.slider("v", "카 속도 [m/s] (+ 상승, − 하강)", -2, 2, 0.1, 1); s.slider("r", "드럼 반지름 [m]", 0.1, 0.5, 0.05, 0.25);
      s.end(); const [c0, c1] = s.cols([3, 2]);
      s.into(c0); const p = s.plot(420); s.into(c1); const hd = s.h(""), m = s.metrics(3), nt = s.note();
      s.on((v) => {
        const r = elevator(v.mc, v.ml, v.mw, v.v, v.r), lw = 10, lT = 4000;
        const reg = { 1: [0, lw, 0, lT], 2: [0, lw, -lT, 0], 3: [-lw, 0, -lT, 0], 4: [-lw, 0, 0, lT] };
        const shapes = [], ann = [];
        for (const k of [1, 2, 3, 4]) {
          const [x0, x1, y0, y1] = reg[k], base = k % 2 ? "42,157,143" : "231,111,81";
          shapes.push({ type: "rect", xref: "x", yref: "y", x0, x1, y0, y1, fillcolor: `rgba(${base},${k === r.q ? 0.45 : 0.15})`, line: { width: 0 }, layer: "below" });
          ann.push({ x: (x0 + x1) / 2, y: (y0 + y1) / 2 * 1.6, text: names[k].replace(": ", "<br>"), showarrow: false, font: { size: 12 } });
        }
        draw(p, [pts([r.w], [r.T], "현재 운전점", { size: 16 })], { shapes, annotations: ann, showlegend: false, margin: { b: 50 },
          xaxis: Object.assign(tx("전동기 속도 ω [rad/s] (+ = 카 상승)"), { range: [-lw, lw] }), yaxis: Object.assign(tx("전동기 토크 T [N·m] (+ = 카를 끌어올리는 방향)"), { range: [-lT, lT] }) });
        hd.textContent = names[r.q];
        metric(m[0], "전동기 토크", `${r.T.toFixed(0)} N·m`);
        metric(m[1], "전동기 속도", `${r.w.toFixed(2)} rad/s (${(r.w * RPM).toFixed(0)} rpm)`);
        metric(m[2], "전력 P = T·ω", `${(r.P / 1000).toFixed(2)} kW`, "+: 전원 → 부하 (전동기)  −: 부하 → 전원 (발전기)");
        nt.innerHTML = r.P >= 0 ? "전동기 모드" : "<b>제동 중</b>: 부하의 위치 에너지가 전기로 바뀝니다. 전원으로 되돌리면 <b>회생 제동</b>, 저항에서 열로 쓰면 <b>발전 제동</b>.";
      });
    });
  };

  const api = Object.assign(T, { _calc: { lambdaI, energyCoenergy, gapForce, gapForceLinear, linearPaths, relAvg, dblAvg, loadT, opPoint, startup, elevator, LOADS } });
  root.LabCh1 = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
