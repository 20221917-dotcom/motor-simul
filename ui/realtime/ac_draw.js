/* 교류 전동기 그림 (2극 등가, 전기각 기준). 상 코일 축: A 0°, B 120°, C 240°.
 * 상전류 > 0 이면 그 상 이빨 면이 S극(파랑) → 합성 고정자 자계는 전류 공간 벡터 방향을 가리킨다. */
(function (root) {
  "use strict";
  const DEG = Math.PI / 180, BETA = [0, 120 * DEG, 240 * DEG], PCOL = ["#d62828", "#2a9d3a", "#1d4ed8"], PH = ["A", "B", "C"];
  function M(W, H, half) { const S = Math.min(W, H) / (2 * half), cx = W / 2, cy = H / 2 + 8; return { S, cx, cy, P: (r, a) => [cx + r * S * Math.cos(a), cy - r * S * Math.sin(a)] }; }
  function sector(ctx, m, r0, r1, a0, a1, fill, stroke) {
    ctx.beginPath(); ctx.arc(m.cx, m.cy, r1 * m.S, -a0, -a1, true); ctx.arc(m.cx, m.cy, r0 * m.S, -a1, -a0, false); ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); } if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
  }
  function poleColor(i, Iref) {
    const a = Math.min(1, Math.abs(i) / Iref);
    if (Math.abs(i) < 1e-3 * Iref) return "#c9ced4";
    return i > 0 ? `rgba(59,125,216,${0.2 + 0.8 * a})` : `rgba(217,83,79,${0.2 + 0.8 * a})`;
  }
  function txt(ctx, s, x, y, o) { o = o || {}; ctx.font = o.font || "12px system-ui"; ctx.fillStyle = o.color || "#222"; ctx.textAlign = o.align || "center"; ctx.textBaseline = "middle"; ctx.fillText(s, x, y); }
  function arrow(ctx, x1, y1, x2, y2, col, w, dash) {
    const L = Math.hypot(x2 - x1, y2 - y1); if (L < 4) return;
    const ux = (x2 - x1) / L, uy = (y2 - y1) / L, hd = Math.min(12, 4 + L * 0.2);
    ctx.save(); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = w; if (dash) ctx.setLineDash(dash);
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2 - ux * hd, y2 - uy * hd); ctx.stroke(); ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(x2, y2); ctx.lineTo(x2 - ux * hd - uy * hd * 0.5, y2 - uy * hd + ux * hd * 0.5); ctx.lineTo(x2 - ux * hd + uy * hd * 0.5, y2 - uy * hd - ux * hd * 0.5); ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  function vec(ctx, m, ang, len, col, w, dash) { const [x2, y2] = m.P(len, ang); arrow(ctx, m.cx, m.cy, x2, y2, col, w, dash); }
  function stator(ctx, m, i3, Iref) {
    sector(ctx, m, 1.75, 2.0, 0, 2 * Math.PI, "#8a929b");
    for (let k = 0; k < 3; k++) for (const [off, sg] of [[0, 1], [Math.PI, -1]]) {
      const a = BETA[k] + off, half = 22 * DEG;
      sector(ctx, m, 1.12, 1.76, a - 0.35 * half, a + 0.35 * half, "#9aa3ad", "#666");
      sector(ctx, m, 1.12, 1.26, a - half, a + half, poleColor(sg * i3[k], Iref), "#555");
      sector(ctx, m, 1.3, 1.7, a - 0.75 * half, a - 0.38 * half, PCOL[k], null);
      sector(ctx, m, 1.3, 1.7, a + 0.38 * half, a + 0.75 * half, PCOL[k], null);
      const [lx, ly] = m.P(1.88, a); txt(ctx, PH[k] + (sg < 0 ? "′" : ""), lx, ly, { font: "bold 13px system-ui", color: "#fff" });
    }
  }
  /* 농형 회전자: 도체 Nb 개, 도체 전류 ∝ |ir|·sin(φ − ∠ir) (⊙ 양수) */
  function cage(ctx, m, thr, ira, irb, Iref, Nb) {
    Nb = Nb || 20;
    sector(ctx, m, 0.2, 1.02, 0, 2 * Math.PI, "#b9c0c8", "#555");
    const ang = Math.atan2(irb, ira), mag = Math.hypot(ira, irb);
    for (let k = 0; k < Nb; k++) {
      const ph = thr + k * 2 * Math.PI / Nb, val = mag * Math.sin(ph - ang), a = Math.min(1, Math.abs(val) / Iref);
      const [x, y] = m.P(0.88, ph), r = Math.max(4, 0.06 * m.S);
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = `rgba(199,125,58,${0.25 + 0.75 * a})`; ctx.fill(); ctx.strokeStyle = "#7a4a1f"; ctx.lineWidth = 1; ctx.stroke();
      if (a > 0.08) {
        ctx.fillStyle = "#222"; ctx.strokeStyle = "#222"; ctx.lineWidth = 1.4;
        if (val > 0) { ctx.beginPath(); ctx.arc(x, y, r * 0.3, 0, 2 * Math.PI); ctx.fill(); }
        else { const d = r * 0.5; ctx.beginPath(); ctx.moveTo(x - d, y - d); ctx.lineTo(x + d, y + d); ctx.moveTo(x + d, y - d); ctx.lineTo(x - d, y + d); ctx.stroke(); }
      }
    }
    ctx.beginPath(); ctx.arc(m.cx, m.cy, 0.2 * m.S, 0, 2 * Math.PI); ctx.fillStyle = "#444"; ctx.fill();
    const [kx, ky] = m.P(0.55, thr); ctx.beginPath(); ctx.arc(kx, ky, 5, 0, 2 * Math.PI); ctx.fillStyle = "#facc15"; ctx.fill(); ctx.strokeStyle = "#333"; ctx.stroke();
  }
  /* 영구자석 회전자: N 극 중심 = d축 = θe */
  function magnet(ctx, m, the) {
    sector(ctx, m, 0.25, 1.0, the - Math.PI / 2, the + Math.PI / 2, "#e05a55", "#444");
    sector(ctx, m, 0.25, 1.0, the + Math.PI / 2, the + 1.5 * Math.PI, "#4a86d8", "#444");
    const [nx, ny] = m.P(0.62, the), [sx, sy] = m.P(0.62, the + Math.PI);
    txt(ctx, "N", nx, ny, { font: "bold 18px system-ui", color: "#fff" }); txt(ctx, "S", sx, sy, { font: "bold 18px system-ui", color: "#fff" });
    ctx.beginPath(); ctx.arc(m.cx, m.cy, 0.25 * m.S, 0, 2 * Math.PI); ctx.fillStyle = "#444"; ctx.fill();
  }
  function axes(ctx, m, the) {
    ctx.save(); ctx.lineWidth = 1.5;
    ctx.strokeStyle = "#111"; ctx.beginPath(); ctx.moveTo(...m.P(1.1, the + Math.PI)); ctx.lineTo(...m.P(1.1, the)); ctx.stroke();
    ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(...m.P(1.1, the - Math.PI / 2)); ctx.lineTo(...m.P(1.1, the + Math.PI / 2)); ctx.stroke(); ctx.restore();
    const [dx, dy] = m.P(1.18, the), [qx, qy] = m.P(1.18, the + Math.PI / 2);
    txt(ctx, "d", dx, dy, { font: "bold 13px system-ui" }); txt(ctx, "q", qx, qy, { font: "bold 13px system-ui" });
  }
  // ---------------- 실제 구조 단면 (P극, 슬롯 S개) ----------------
  const rot = (r, t, a) => [r * Math.cos(a) - t * Math.sin(a), r * Math.sin(a) + t * Math.cos(a)];
  function polyM(ctx, m, pts, fill, stroke) {
    ctx.beginPath(); pts.forEach(([x, y], i) => { const X = m.cx + x * m.S, Y = m.cy - y * m.S; i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); });
    ctx.closePath(); if (fill) { ctx.fillStyle = fill; ctx.fill(); } if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
  }
  function symb(ctx, X, Y, r, sgn, col) {
    ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = Math.max(1, r / 3.5);
    if (sgn > 0) { ctx.beginPath(); ctx.arc(X, Y, Math.max(1.4, r * 0.35), 0, 2 * Math.PI); ctx.fill(); }
    else if (sgn < 0) { const d = r * 0.6; ctx.beginPath(); ctx.moveTo(X - d, Y - d); ctx.lineTo(X + d, Y + d); ctx.moveTo(X + d, Y - d); ctx.lineTo(X - d, Y + d); ctx.stroke(); }
  }
  function tag(ctx, m, tx, ty, lx, ly, text) {
    const X1 = m.cx + tx * m.S, Y1 = m.cy - ty * m.S, X2 = m.cx + lx * m.S, Y2 = m.cy - ly * m.S;
    ctx.strokeStyle = "rgba(30,30,30,0.6)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(X1, Y1); ctx.lineTo(X2, Y2); ctx.stroke();
    ctx.beginPath(); ctx.arc(X1, Y1, 2, 0, 2 * Math.PI); ctx.fillStyle = "#222"; ctx.fill();
    ctx.font = "11.5px system-ui"; const tw = ctx.measureText(text).width, cw = ctx.canvas.width / (ctx.getTransform().a || 1);
    let bx = lx < tx ? X2 - tw - 6 : X2 + 2; bx = Math.max(2, Math.min(bx, cw - tw - 6));
    ctx.fillStyle = "rgba(255,255,255,0.9)"; ctx.fillRect(bx, Y2 - 8, tw + 4, 16);
    ctx.fillStyle = "#222"; ctx.textAlign = "left"; ctx.textBaseline = "middle"; ctx.fillText(text, bx + 2, Y2);
  }
  /* opt: { w: {slots, poles, kind, cond:[[angle, layer, phase, sign]]}, i3, isa, isb, Iref, thm,
           rotor: "cage" | "ipm", ira, irb, Nb, labels } */
  function realSection(ctx, m, opt) {
    const w = opt.w, S = w.slots, P = w.poles, pp = P / 2, sp = 2 * Math.PI / S, Iref = opt.Iref || 1;
    // 고정자 계철 + 철심
    sector(ctx, m, 1.06, 2.0, 0, 2 * Math.PI, "#9aa3ad", null);
    ctx.strokeStyle = "#555"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(m.cx, m.cy, 2.0 * m.S, 0, 2 * Math.PI); ctx.stroke();
    // 공극 자계 띠 (기본파): F(θ) = |is|·cos(pp·θ − ∠is) > 0 → 고정자 면이 S극 (파랑)
    const ism = Math.hypot(opt.isa || 0, opt.isb || 0), ang = Math.atan2(opt.isb || 0, opt.isa || 0);
    for (let k = 0; k < 180; k++) {
      const a0 = k * 2 * Math.PI / 180, a1 = (k + 1) * 2 * Math.PI / 180, F = Math.cos(pp * (a0 + a1) / 2 - ang);
      const al = Math.min(1, ism / Iref) * Math.abs(F);
      sector(ctx, m, 1.06, 1.1, a0, a1, F > 0 ? `rgba(59,125,216,${0.15 + 0.85 * al})` : `rgba(217,83,79,${0.15 + 0.85 * al})`, null);
    }
    // 슬롯 + 도체
    const half = 0.29 * 1.3 * sp, conc = w.kind === "concentrated";
    for (let k = 0; k < S; k++) {
      const a = (k + 0.5) * sp;
      polyM(ctx, m, [rot(1.1, -half * 0.55, a), rot(1.56, -half, a), rot(1.56, half, a), rot(1.1, half * 0.55, a)], "#3f454c", null);
    }
    for (const [a, layer, ph, sg] of w.cond) {
      const i = sg * opt.i3[ph], al = Math.min(1, Math.abs(i) / Iref);
      let r0, r1, t0, t1;
      if (conc) { r0 = 1.17; r1 = 1.52; t0 = layer === 0 ? -half * 0.85 : half * 0.05; t1 = layer === 0 ? -half * 0.05 : half * 0.85; }
      else { r0 = layer === 0 ? 1.15 : 1.35; r1 = layer === 0 ? 1.33 : 1.53; t0 = -half * 0.75; t1 = half * 0.75; }
      const col = PCOL[ph];
      ctx.globalAlpha = 0.35 + 0.65 * al;
      polyM(ctx, m, [rot(r0, t0, a), rot(r1, t0, a), rot(r1, t1, a), rot(r0, t1, a)], col, null);
      ctx.globalAlpha = 1;
      const [cx, cy] = rot((r0 + r1) / 2, (t0 + t1) / 2, a), rr = Math.min((r1 - r0), Math.abs(t1 - t0)) * m.S * 0.38;
      if (al > 0.06 && rr > 2.2) symb(ctx, m.cx + cx * m.S, m.cy - cy * m.S, rr, Math.sign(i), "#fff");
    }
    // 회전자
    if (opt.rotor === "cage") {
      sector(ctx, m, 0.2, 1.02, 0, 2 * Math.PI, "#b9c0c8", null);
      const Nb = opt.Nb || 28, iam = Math.hypot(opt.ira, opt.irb), ia_ = Math.atan2(opt.irb, opt.ira);
      for (let k = 0; k < Nb; k++) {
        const ph = opt.thm + k * 2 * Math.PI / Nb, val = iam * Math.sin(pp * ph - ia_), al = Math.min(1, Math.abs(val) / Iref);
        const X = m.cx + 0.9 * m.S * Math.cos(ph), Y = m.cy - 0.9 * m.S * Math.sin(ph), r = Math.max(3, 0.055 * m.S);
        ctx.beginPath(); ctx.arc(X, Y, r, 0, 2 * Math.PI); ctx.fillStyle = `rgba(199,125,58,${0.3 + 0.7 * al})`; ctx.fill();
        ctx.strokeStyle = "#7a4a1f"; ctx.lineWidth = 1; ctx.stroke();
        if (al > 0.08) symb(ctx, X, Y, r, Math.sign(val), "#222");
      }
    } else {
      sector(ctx, m, 0.2, 1.02, 0, 2 * Math.PI, "#b9c0c8", null);
      for (let j = 0; j < P; j++) {   // 매입 자석 (N 극 중심 = d축, 기계각 θm + j·2π/P)
        const c = opt.thm + j * 2 * Math.PI / P, hl = 0.8 * Math.sin(Math.PI / P) * 0.78, tw = 0.07;
        polyM(ctx, m, [rot(0.78 - tw, -hl - 0.05, c), rot(0.78 + tw, -hl - 0.05, c), rot(0.78 + tw, hl + 0.05, c), rot(0.78 - tw, hl + 0.05, c)], "#e9ecef", null);  // 자속 장벽
        polyM(ctx, m, [rot(0.78 - tw, -hl, c), rot(0.78 + tw, -hl, c), rot(0.78 + tw, hl, c), rot(0.78 - tw, hl, c)], j % 2 === 0 ? "#e05a55" : "#4a86d8", "#333");
        const [tx, ty] = rot(0.78, 0, c); txt(ctx, j % 2 === 0 ? "N" : "S", m.cx + tx * m.S, m.cy - ty * m.S, { font: "bold 10px system-ui", color: "#fff" });
      }
      // 첫 극의 d·q 축
      ctx.save(); ctx.setLineDash([4, 3]); ctx.strokeStyle = "rgba(0,0,0,0.55)"; ctx.lineWidth = 1.3;
      const [dx, dy] = rot(1.0, 0, opt.thm), [qx, qy] = rot(1.0, 0, opt.thm + Math.PI / P);
      ctx.beginPath(); ctx.moveTo(m.cx, m.cy); ctx.lineTo(m.cx + dx * m.S, m.cy - dy * m.S); ctx.moveTo(m.cx, m.cy); ctx.lineTo(m.cx + qx * m.S, m.cy - qy * m.S); ctx.stroke(); ctx.restore();
      txt(ctx, "d", m.cx + dx * m.S * 1.04, m.cy - dy * m.S * 1.04, { font: "bold 12px system-ui" });
      txt(ctx, "q", m.cx + qx * m.S * 1.04, m.cy - qy * m.S * 1.04, { font: "bold 12px system-ui" });
    }
    ctx.beginPath(); ctx.arc(m.cx, m.cy, 0.2 * m.S, 0, 2 * Math.PI); ctx.fillStyle = "#444"; ctx.fill();
    const [kx, ky] = rot(0.13, 0, opt.thm); ctx.beginPath(); ctx.arc(m.cx + kx * m.S, m.cy - ky * m.S, 3, 0, 2 * Math.PI); ctx.fillStyle = "#facc15"; ctx.fill();
    if (opt.labels) {
      const ca = (w.cond.find((c) => c[2] === 0 && c[1] === 0) || [0])[0];
      tag(ctx, m, ...rot(1.85, 0, 2.45), -2.55, 1.9, "고정자 계철 (자속 귀로)");
      tag(ctx, m, ...rot(1.3, 0, 2.45 + sp / 2), -2.55, 1.45, "고정자 이빨 (철심)");
      tag(ctx, m, ...rot(1.24, 0, ca), 2.25, 1.7, `A상 도체 (${conc ? "집중권" : "분포권"}, 슬롯 ${S}개)`);
      tag(ctx, m, ...rot(1.08, 0, -0.55), 2.25, -0.6, "공극 자계 (파랑 S · 빨강 N)");
      tag(ctx, m, ...rot(0.55, 0, 3.6), -2.55, -1.0, "회전자 철심 (적층)");
      if (opt.rotor === "cage") tag(ctx, m, ...rot(0.9, 0, opt.thm + 0.4), 2.25, -1.4, "회전자 도체 바 (농형)");
      else tag(ctx, m, ...rot(0.78, 0, opt.thm + 2 * Math.PI / P), 2.25, -1.4, `매입 영구자석 (${P}극)`);
      tag(ctx, m, 0.0, -0.1, -2.55, -1.9, "축");
    }
  }

  root.ACDraw = { M, sector, poleColor, txt, arrow, vec, stator, cage, magnet, axes, realSection, PCOL, PH, DEG };
})(this);
