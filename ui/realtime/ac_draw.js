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
  root.ACDraw = { M, sector, poleColor, txt, arrow, vec, stator, cage, magnet, axes, PCOL, PH, DEG };
})(this);
