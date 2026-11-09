/* 전동기 그림: 단순 모형(코일 1개), 실제 구조 단면, 실제 구조 측면.
 * 모든 함수는 (ctx, 영역 x, y, w, h, 상태 o, 회전각 th, 옵션) 을 받는다.
 * 좌표계: 수학 좌표 (x 오른쪽, y 위), 각도는 반시계 방향 양수.
 * 자계 방향: 2극에서 N극 왼쪽 → S극 오른쪽 (B = +x). Ia > 0 이면 반시계 방향 토크.
 */
(function (root) {
  "use strict";
  const COPPER = "#c77d3a", STEEL = "#9aa3ad", STEEL_D = "#7d8590", CORE = "#b9c0c8";
  const N_COL = "#d9534f", S_COL = "#3b7dd8", BG = "#f6f7f9", GREEN = "#2a9d3a";

  function mapper(x0, y0, w, h, halfW, halfH) {
    const S = Math.min(w / (2 * halfW), h / (2 * halfH));
    const cx = x0 + w / 2, cy = y0 + h / 2;
    return { S, cx, cy, P: (x, y) => [cx + x * S, cy - y * S] };
  }
  // 극좌표 (반지름 r, 각도 a 방향, 접선 오프셋 t) → 수학 좌표
  const rot = (r, t, a) => [r * Math.cos(a) - t * Math.sin(a), r * Math.sin(a) + t * Math.cos(a)];

  function poly(ctx, M, pts, fill, stroke) {
    ctx.beginPath();
    pts.forEach(([x, y], i) => { const [X, Y] = M.P(x, y); i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); });
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
  }
  function disk(ctx, M, x, y, r, fill, stroke, lw) {
    const [X, Y] = M.P(x, y);
    ctx.beginPath(); ctx.arc(X, Y, r * M.S, 0, 2 * Math.PI);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw || 1; ctx.stroke(); }
  }
  // 전류 방향 기호: +1 = ⊙ (지면에서 나옴), −1 = ⊗ (들어감)
  function sym(ctx, X, Y, rad, sgn, color) {
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = Math.max(1.2, rad / 4);
    if (sgn > 0) { ctx.beginPath(); ctx.arc(X, Y, Math.max(1.5, rad * 0.32), 0, 2 * Math.PI); ctx.fill(); }
    else if (sgn < 0) {
      const d = rad * 0.55;
      ctx.beginPath(); ctx.moveTo(X - d, Y - d); ctx.lineTo(X + d, Y + d); ctx.moveTo(X + d, Y - d); ctx.lineTo(X - d, Y + d); ctx.stroke();
    }
  }
  function arrow(ctx, X1, Y1, X2, Y2, color, w) {
    const L = Math.hypot(X2 - X1, Y2 - Y1); if (L < 3) return;
    const ux = (X2 - X1) / L, uy = (Y2 - Y1) / L, hd = Math.min(9, 0.45 * L + 3);
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = w || 2;
    ctx.beginPath(); ctx.moveTo(X1, Y1); ctx.lineTo(X2 - ux * hd * 0.8, Y2 - uy * hd * 0.8); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(X2, Y2);
    ctx.lineTo(X2 - ux * hd - uy * hd * 0.5, Y2 - uy * hd + ux * hd * 0.5);
    ctx.lineTo(X2 - ux * hd + uy * hd * 0.5, Y2 - uy * hd - ux * hd * 0.5); ctx.closePath(); ctx.fill();
  }
  function label(ctx, M, tx, ty, lx, ly, text, align) {
    const [X1, Y1] = M.P(tx, ty), [X2, Y2] = M.P(lx, ly);
    ctx.strokeStyle = "rgba(40,40,40,0.55)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(X1, Y1); ctx.lineTo(X2, Y2); ctx.stroke();
    ctx.beginPath(); ctx.arc(X1, Y1, 2, 0, 2 * Math.PI); ctx.fillStyle = "#333"; ctx.fill();
    ctx.font = "11.5px system-ui, sans-serif"; ctx.textBaseline = "middle";
    ctx.textAlign = align || (lx < tx ? "right" : "left");
    const pad = ctx.textAlign === "right" ? -3 : 3;
    const tw = ctx.measureText(text).width;
    let bx = ctx.textAlign === "right" ? X2 + pad - tw - 2 : X2 + pad - 2;
    // 캔버스 밖으로 나가지 않게 이름표 위치를 안쪽으로 당김
    const cw = ctx.canvas.width / (ctx.getTransform().a || 1);
    bx = Math.max(2, Math.min(bx, cw - tw - 6));
    ctx.fillStyle = "rgba(255,255,255,0.88)"; ctx.fillRect(bx, Y2 - 8, tw + 4, 16);
    ctx.textAlign = "left"; ctx.fillStyle = "#222"; ctx.fillText(text, bx + 2, Y2);
  }
  const torqueSign = (o) => Math.sign(o.k * o.ia) || 0;

  // ------------------------------------------------------------------
  // 1) 단순 모형: 코일 1개 + 정류자편 2개
  // ------------------------------------------------------------------
  function drawSimple(ctx, x0, y0, w, h, o, th, opt) {
    const M = mapper(x0, y0 + 14, w, h - 14, 1.95, 1.55);
    const { S } = M;
    [[-1, N_COL, "N"], [1, S_COL, "S"]].forEach(([sd, col, txt]) => {
      const half = 42 * Math.PI / 180, c = sd > 0 ? 0 : Math.PI, pts = [];
      for (let i = 0; i <= 20; i++) { const a = c - half + 2 * half * i / 20; pts.push([1.05 * Math.cos(a), 1.05 * Math.sin(a)]); }
      const ys = 1.05 * Math.sin(half);
      if (sd > 0) pts.push([1.8, ys], [1.8, -ys]); else pts.push([-1.8, -ys], [-1.8, ys]);
      poly(ctx, M, pts, col);
      ctx.fillStyle = "#fff"; ctx.font = "bold 22px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(txt, ...M.P(sd * 1.45, 0));
    });
    ctx.strokeStyle = `rgba(120,80,200,${Math.min(0.85, 0.12 + 0.55 * opt.fieldRatio).toFixed(2)})`; ctx.lineWidth = 2;
    [0.55, 0, -0.55].forEach((y) => { ctx.beginPath(); ctx.moveTo(...M.P(-1.0, y)); ctx.lineTo(...M.P(1.0, y)); ctx.stroke(); });
    disk(ctx, M, 0, 0, 0.95, "rgba(160,160,160,0.22)", "#888", 1.5);
    [[1, "+"], [-1, "−"]].forEach(([sd, t]) => {
      const [bx, by] = M.P(sd > 0 ? 0.23 : -0.38, 0.06);
      ctx.fillStyle = "#333"; ctx.fillRect(bx, by, 0.15 * S, 0.12 * S);
      ctx.font = "bold 16px system-ui"; ctx.textAlign = "center"; ctx.fillText(t, ...M.P(sd * 0.5, 0));
    });
    const gap = 8 * Math.PI / 180, [cx, cy] = M.P(0, 0);
    ctx.lineWidth = 9;
    ctx.strokeStyle = "#f0a020"; ctx.beginPath(); ctx.arc(cx, cy, 0.22 * S, -(th - Math.PI / 2 + gap), -(th + Math.PI / 2 - gap), true); ctx.stroke();
    ctx.strokeStyle = "#20a39e"; ctx.beginPath(); ctx.arc(cx, cy, 0.22 * S, -(th + Math.PI / 2 + gap), -(th + 1.5 * Math.PI - gap), true); ctx.stroke();
    const fLen = 0.55 * Math.min(Math.abs(o.k * o.ia) / (opt.forceRef || 1), 1.6);
    [[th, "#f0a020"], [th + Math.PI, "#20a39e"]].forEach(([ph, col]) => {
      const x = 0.78 * Math.cos(ph), y = 0.78 * Math.sin(ph);
      const sgn = (Math.cos(ph) >= 0 ? 1 : -1) * (Math.abs(o.ia) > 1e-3 ? Math.sign(o.ia) : 0);
      ctx.setLineDash([3, 3]); ctx.strokeStyle = "#777"; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(...M.P(0.22 * Math.cos(ph), 0.22 * Math.sin(ph))); ctx.lineTo(...M.P(x, y)); ctx.stroke();
      ctx.setLineDash([]);
      const [px, py] = M.P(x, y);
      ctx.beginPath(); ctx.arc(px, py, 12, 0, 2 * Math.PI); ctx.fillStyle = "#fff"; ctx.fill();
      ctx.lineWidth = 3; ctx.strokeStyle = col; ctx.stroke();
      sym(ctx, px, py, 12, sgn, "#333");
      if (sgn !== 0 && fLen > 0.02) {
        const dir = sgn * Math.sign(o.k || 1);
        const [ax, ay] = M.P(x, y + 0.12 * dir), [bx, by] = M.P(x, y + 0.12 * dir + dir * fLen);
        arrow(ctx, ax, ay, bx, by, GREEN, 4);
      }
    });
    if (opt.labels) {
      label(ctx, M, -1.5, 0.5, -1.7, 1.35, "계자 자극 (N)", "left");
      label(ctx, M, 0.78 * Math.cos(th), 0.78 * Math.sin(th), 1.25, 1.35, "코일 변", "left");
      label(ctx, M, 0.0, -0.22, 0.6, -1.35, "정류자편 2개", "left");
      label(ctx, M, -0.3, -0.06, -1.0, -1.35, "브러시", "right");
    }
  }

  // ------------------------------------------------------------------
  // 2) 실제 구조 단면
  // ------------------------------------------------------------------
  function drawReal(ctx, x0, y0, w, h, o, th, opt) {
    const P = opt.poles || 2, pp = P / 2, NS = opt.slots || 24;
    const M = mapper(x0, y0 + 14, w, h - 14, opt.labels ? 2.75 : 2.05, 2.05);
    // 계철(요크)
    disk(ctx, M, 0, 0, 1.95, STEEL_D, "#555", 1.5);
    disk(ctx, M, 0, 0, 1.62, BG);
    const fr = Math.min(1.3, opt.fieldRatio);
    // 주극과 계자 권선
    for (let k = 0; k < P; k++) {
      const a = k * 2 * Math.PI / P, isS = k % 2 === 0;     // 0° 가 S극 (2극: 오른쪽 S, 왼쪽 N)
      const wc = P === 2 ? 0.22 : 0.17, span = 0.55 * Math.PI / P;
      poly(ctx, M, [rot(1.64, -wc, a), rot(1.18, -wc, a), rot(1.18, wc, a), rot(1.64, wc, a)], STEEL, "#666");
      const shoe = [];
      for (let i = 0; i <= 16; i++) { const d = -span + 2 * span * i / 16; shoe.push([1.2 * Math.cos(a + d), 1.2 * Math.sin(a + d)]); }
      for (let i = 16; i >= 0; i--) { const d = -span + 2 * span * i / 16; shoe.push([1.03 * Math.cos(a + d), 1.03 * Math.sin(a + d)]); }
      poly(ctx, M, shoe, isS ? "#6f97d8" : "#d98a87", "#666");
      // 계자 코일 (극 철심 양옆), 진하기 = 계자 세기
      const fsgn = (isS ? 1 : -1) * (Math.sign(o.if) || 1);
      [-1, 1].forEach((side) => {
        const t0 = side * wc, t1 = side * (wc + 0.17);
        ctx.globalAlpha = 0.35 + 0.65 * Math.min(1, fr);
        poly(ctx, M, [rot(1.58, t0, a), rot(1.24, t0, a), rot(1.24, t1, a), rot(1.58, t1, a)], COPPER, "#7a4a1f");
        ctx.globalAlpha = 1;
        const [sx, sy] = M.P(...rot(1.41, (t0 + t1) / 2, a));
        ctx.beginPath(); ctx.arc(sx, sy, 6, 0, 2 * Math.PI); ctx.fillStyle = "#fff"; ctx.fill();
        sym(ctx, sx, sy, 6, side * fsgn, "#333");
      });
      ctx.fillStyle = "#fff"; ctx.font = "bold 15px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(isS ? "S" : "N", ...M.P(...rot(1.105, 0, a)));
    }
    // 보극 (중성축)
    for (let k = 0; k < P; k++) {
      const a = (k + 0.5) * 2 * Math.PI / P;
      poly(ctx, M, [rot(1.64, -0.07, a), rot(1.28, -0.07, a), rot(1.28, 0.07, a), rot(1.64, 0.07, a)], "#c3c9cf", "#777");
      poly(ctx, M, [rot(1.58, 0.07, a), rot(1.36, 0.07, a), rot(1.36, 0.14, a), rot(1.58, 0.14, a)], COPPER, null);
      poly(ctx, M, [rot(1.58, -0.14, a), rot(1.36, -0.14, a), rot(1.36, -0.07, a), rot(1.58, -0.07, a)], COPPER, null);
    }
    // 자속 경로 (점선 화살표, 계자 세기에 비례한 진하기)
    ctx.save(); ctx.setLineDash([5, 5]); ctx.globalAlpha = Math.min(0.8, 0.15 + 0.5 * fr);
    for (let k = 0; k < P; k++) {
      const a = k * 2 * Math.PI / P, isS = k % 2 === 0;
      const [X1, Y1] = M.P(...rot(isS ? 0.6 : 1.25, 0, a)), [X2, Y2] = M.P(...rot(isS ? 1.25 : 0.6, 0, a));
      arrow(ctx, X1, Y1, X2, Y2, "#7b52c7", 1.5);
    }
    ctx.restore();
    // 전기자 철심 + 슬롯
    disk(ctx, M, 0, 0, 0.98, CORE, "#6b737c", 1.2);
    disk(ctx, M, 0, 0, 0.5, BG, "#6b737c", 1);
    const fRef = opt.forceRef || 1;
    const fLen = 0.16 * Math.min(Math.abs(o.k * o.ia) / fRef, 1.6), tsg = torqueSign(o);
    const commZone = Math.sin(Math.PI / NS) * pp * 1.15;
    for (let k = 0; k < NS; k++) {
      const phi = th + k * 2 * Math.PI / NS;
      poly(ctx, M, [rot(0.98, -0.055, phi), rot(0.70, -0.055, phi), rot(0.70, 0.055, phi), rot(0.98, 0.055, phi)], "#4b525a", null);
      const c = Math.cos(pp * phi), commutating = Math.abs(c) < commZone;
      const sgn = commutating || Math.abs(o.ia) < 1e-3 ? 0 : Math.sign(c) * Math.sign(o.ia);
      [0.90, 0.78].forEach((r) => {
        const [X, Y] = M.P(r * Math.cos(phi), r * Math.sin(phi)), rad = 0.047 * M.S;
        ctx.beginPath(); ctx.arc(X, Y, rad, 0, 2 * Math.PI);
        ctx.fillStyle = commutating ? "#9e9e9e" : COPPER; ctx.fill();
        sym(ctx, X, Y, rad, sgn, "#fff");
      });
      // 힘 (접선 방향, 바깥층 도체에만 표시)
      if (sgn !== 0 && fLen > 0.01 && k % 2 === 0) {
        const r = 1.0, [X1, Y1] = M.P(r * Math.cos(phi), r * Math.sin(phi));
        const tx = -Math.sin(phi) * tsg, ty = Math.cos(phi) * tsg;
        const [X2, Y2] = M.P(r * Math.cos(phi) + tx * fLen, r * Math.sin(phi) + ty * fLen);
        arrow(ctx, X1, Y1, X2, Y2, GREEN, 2);
      }
    }
    // 정류자 (실제로는 축 끝에 있지만 겹쳐 그림)
    const [cx, cy] = M.P(0, 0), S = M.S;
    for (let k = 0; k < NS; k++) {
      const a0 = th + k * 2 * Math.PI / NS + 0.02, a1 = th + (k + 1) * 2 * Math.PI / NS - 0.02;
      ctx.beginPath(); ctx.arc(cx, cy, 0.36 * S, -a0, -a1, true); ctx.arc(cx, cy, 0.22 * S, -a1, -a0, false); ctx.closePath();
      ctx.fillStyle = k === 0 ? "#e0a050" : "#c98a3e"; ctx.fill();
    }
    // 브러시 (전기적 중성축)
    for (let k = 0; k < P; k++) {
      const a = (k + 0.5) * 2 * Math.PI / P;
      poly(ctx, M, [rot(0.36, -0.06, a), rot(0.49, -0.06, a), rot(0.49, 0.06, a), rot(0.36, 0.06, a)], "#2f2f2f", null);
      ctx.fillStyle = "#222"; ctx.font = "bold 13px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(k % 2 === 0 ? "+" : "−", ...M.P(...rot(0.43, 0.13, a)));
    }
    disk(ctx, M, 0, 0, 0.13, "#3d3d3d");
    const [kx, ky] = M.P(0.1 * Math.cos(th), 0.1 * Math.sin(th));
    ctx.beginPath(); ctx.arc(kx, ky, 2.5, 0, 2 * Math.PI); ctx.fillStyle = "#ddd"; ctx.fill();
    // 회전 방향 표시
    if (Math.abs(o.w) > 0.5) {
      const dir = Math.sign(o.w), r = 0.6 * S;
      ctx.strokeStyle = "rgba(30,30,30,0.5)"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI * 0.55, -Math.PI * 0.95, true); ctx.stroke();
      const ae = dir > 0 ? Math.PI * 0.95 : Math.PI * 0.55;
      const ex = cx + r * Math.cos(-ae), ey = cy + r * Math.sin(-ae);
      const tx = -Math.sin(-ae) * dir * -1, ty = Math.cos(-ae) * dir * -1;
      arrow(ctx, ex - tx * 8, ey - ty * 8, ex + tx * 4, ey + ty * 4, "rgba(30,30,30,0.6)", 2);
    }
    if (opt.labels) {
      const L = [
        [-1.38, 1.38, -2.05, 1.85, "계철 (요크, 자속 귀로)"],
        [...rot(1.45, 0, Math.PI), -2.1, 0.95, "주극 철심"],
        [...rot(1.41, -(P === 2 ? 0.3 : 0.25), Math.PI), -2.1, 0.45, "계자 권선"],
        [...rot(1.12, 0.3, Math.PI), -2.1, -0.15, "극편 (공극 자속 분포)"],
        [...rot(1.46, 0, Math.PI / P), 2.0, 1.85, "보극 (정류 개선)"],
        [...rot(0.84, 0, th + 3 * 2 * Math.PI / NS), 2.05, 0.95, "전기자 도체 (슬롯 안)"],
        [0.62, -0.62, 2.05, 0.35, "전기자 철심 (적층)"],
        [...rot(0.29, 0, -Math.PI / 4), 2.05, -0.95, "정류자 (실제는 축 끝)"],
        [...rot(0.45, 0, -Math.PI / 2), 1.2, -1.95, "브러시 (전기적 중성축)"],
        [0, -0.08, -1.3, -1.95, "축"],
        [...rot(0.9, 0, -Math.PI / 2), -2.15, -1.25, "정류 중 도체 (회색)"],
      ];
      L.forEach(([tx, ty, lx, ly, t]) => label(ctx, M, tx, ty, lx, ly, t));
    }
  }

  // ------------------------------------------------------------------
  // 3) 실제 구조 측면 (축 방향 단면)
  // ------------------------------------------------------------------
  function cylinderStripes(ctx, M, x1, x2, R, n, th, color, lw) {
    for (let k = 0; k < n; k++) {
      const a = th + k * 2 * Math.PI / n, vis = Math.sin(a);
      if (vis <= 0) continue;
      const y = R * Math.cos(a);
      ctx.strokeStyle = color; ctx.globalAlpha = 0.25 + 0.75 * vis; ctx.lineWidth = lw;
      ctx.beginPath(); ctx.moveTo(...M.P(x1, y)); ctx.lineTo(...M.P(x2, y)); ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  function shade(ctx, M, x1, x2, R, c1, c2) {
    const [X1, Y1] = M.P(x1, R), [X2, Y2] = M.P(x2, -R);
    const g = ctx.createLinearGradient(0, Y1, 0, Y2);
    g.addColorStop(0, c2); g.addColorStop(0.35, c1); g.addColorStop(1, c2);
    ctx.fillStyle = g; ctx.fillRect(X1, Y1, X2 - X1, Y2 - Y1);
  }
  function drawSide(ctx, x0, y0, w, h, o, th, opt) {
    const NS = opt.slots || 24;
    const M = mapper(x0, y0 + 14, w, h - 14, 2.35, 1.3);
    const R = (x1, y1, x2, y2, fill, stroke) => poly(ctx, M, [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], fill, stroke);
    // 프레임과 엔드 브래킷
    R(-1.3, 1.08, 1.3, 0.95, STEEL_D, "#555"); R(-1.3, -0.95, 1.3, -1.08, STEEL_D, "#555");
    poly(ctx, M, [[-1.3, 1.08], [-1.6, 0.45], [-1.6, -0.45], [-1.3, -1.08], [-1.22, -1.08], [-1.5, -0.45], [-1.5, 0.45], [-1.22, 1.08]], STEEL, "#666");
    poly(ctx, M, [[1.3, 1.08], [1.68, 0.45], [1.68, -0.45], [1.3, -1.08], [1.22, -1.08], [1.58, -0.45], [1.58, 0.45], [1.22, 1.08]], STEEL, "#666");
    // 주극 + 계자 권선 (위: N, 아래: S 로 단면 표시)
    const fr = Math.min(1.3, opt.fieldRatio);
    [[1, "#d98a87", "N"], [-1, "#6f97d8", "S"]].forEach(([sd, col, t]) => {
      R(-0.75, sd * 0.95, 0.75, sd * 0.66, STEEL, "#666");
      R(-0.85, sd * 0.66, 0.85, sd * 0.6, col, "#666");
      ctx.globalAlpha = 0.35 + 0.65 * Math.min(1, fr);
      R(-1.05, sd * 0.93, -0.77, sd * 0.69, COPPER, "#7a4a1f"); R(0.77, sd * 0.93, 1.05, sd * 0.69, COPPER, "#7a4a1f");
      ctx.globalAlpha = 1;
      ctx.fillStyle = "#fff"; ctx.font = "bold 13px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(t, ...M.P(0, sd * 0.8));
    });
    // 축
    R(-2.3, 0.1, 1.95, -0.1, "#5c5c5c", "#333");
    cylinderStripes(ctx, M, -2.3, -1.8, 0.1, 1, th, "#ddd", 3);           // 키 홈
    // 베어링
    [-1.55, 1.63].forEach((x) => { R(x - 0.09, 0.22, x + 0.09, 0.1, "#888", "#444"); R(x - 0.09, -0.1, x + 0.09, -0.22, "#888", "#444"); });
    // 전기자 철심 (회전: 슬롯 줄무늬가 흐름)
    shade(ctx, M, -0.8, 0.8, 0.56, "#cfd5db", "#8a929b");
    cylinderStripes(ctx, M, -0.8, 0.8, 0.56, NS, th, "#4b525a", 2);
    // 전기자 권선 끝단 (엔드 와인딩)
    [[-1.0, -0.8], [0.8, 1.0]].forEach(([a, b]) => { shade(ctx, M, a, b, 0.48, "#e0a35f", "#9c6128"); cylinderStripes(ctx, M, a, b, 0.48, NS, th, "#7a4a1f", 1.2); });
    // 정류자 + 라이저
    shade(ctx, M, 1.05, 1.4, 0.3, "#e6ad6a", "#a86a2c");
    cylinderStripes(ctx, M, 1.05, 1.4, 0.3, NS, th, "#5a3a18", 1.5);
    // 브러시 + 스프링
    [[1, "+"], [-1, "−"]].forEach(([sd, t]) => {
      R(1.13, sd * 0.31, 1.32, sd * 0.5, "#2f2f2f", null);
      ctx.strokeStyle = "#666"; ctx.lineWidth = 1.2; ctx.beginPath();
      for (let i = 0; i <= 8; i++) { const yy = sd * (0.5 + i * 0.02), xx = 1.225 + (i % 2 ? 0.05 : -0.05); const [X, Y] = M.P(xx, yy); i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); }
      ctx.stroke();
      ctx.fillStyle = "#222"; ctx.font = "bold 13px system-ui"; ctx.textAlign = "left"; ctx.fillText(t, ...M.P(1.36, sd * 0.42));
    });
    if (opt.labels) {
      const L = [
        [-0.9, 1.02, -1.5, 1.25, "프레임 (계철)"],
        [-0.9, 0.8, -2.1, 0.95, "계자 권선"],
        [0.3, 0.8, 0.45, 1.25, "주극"],
        [0.1, -0.35, -0.5, -1.25, "전기자 철심 (회전)"],
        [-0.9, -0.3, -2.1, -0.75, "전기자 권선 끝단"],
        [1.2, -0.15, 2.0, -0.85, "정류자"],
        [1.25, 0.45, 2.05, 0.85, "브러시 (스프링으로 압착)"],
        [1.63, -0.16, 2.1, -1.2, "베어링"],
        [-2.0, 0.05, -2.2, 0.5, "축 (부하 쪽)"],
      ];
      L.forEach(([tx, ty, lx, ly, t]) => label(ctx, M, tx, ty, lx, ly, t));
    }
  }

  root.MotorDraw = { drawSimple, drawReal, drawSide };
})(this);
