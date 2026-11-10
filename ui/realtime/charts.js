/* 오실로스코프처럼 흘러가는 실시간 그래프 (canvas, 외부 라이브러리 없음). */
(function (root) {
  "use strict";

  function setupCanvas(cv) {
    const dpr = window.devicePixelRatio || 1;
    const r = cv.getBoundingClientRect();
    if (cv.width !== Math.round(r.width * dpr) || cv.height !== Math.round(r.height * dpr)) {
      cv.width = Math.round(r.width * dpr);
      cv.height = Math.round(r.height * dpr);
    }
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // 숨겨진 탭 안에서는 크기가 0 이 되므로 그림 계산이 음수 반지름을 만들지 않도록 최소 크기로 계산
    return [ctx, Math.max(r.width, 160), Math.max(r.height, 120)];
  }

  function niceStep(span, n) {
    const raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / p;
    return (m < 1.5 ? 1 : m < 3 ? 2 : m < 7 ? 5 : 10) * p;
  }

  class Strip {
    /* series: [{name, color, dash, width}], opts: {title, unit, minSpan} */
    constructor(canvas, series, opts) {
      this.cv = canvas; this.series = series; this.o = Object.assign({ minSpan: 1 }, opts);
      this.N = 6000; this.t = new Float64Array(this.N);
      this.v = series.map(() => new Float64Array(this.N));
      this.head = 0; this.count = 0;
      this.hlines = [];   // [{y, color, label}]
    }
    clear() { this.head = 0; this.count = 0; }
    push(t, vals) {
      const i = this.head;
      this.t[i] = t;
      for (let k = 0; k < vals.length; k++) this.v[k][i] = vals[k];
      this.head = (i + 1) % this.N;
      this.count = Math.min(this.count + 1, this.N);
    }
    draw(tNow, win) {
      const [ctx, W, H] = setupCanvas(this.cv);
      const L = 48, R = 8, T = 22, B = 18;
      const pw = W - L - R, ph = H - T - B;
      ctx.clearRect(0, 0, W, H);
      const t0 = Math.max(0, tNow - win), t1 = Math.max(win, tNow);
      // 보이는 구간의 y 범위
      let lo = Infinity, hi = -Infinity;
      const idx = [];
      for (let j = 0; j < this.count; j++) {
        const i = (this.head - this.count + j + this.N) % this.N;
        if (this.t[i] >= t0) idx.push(i);
      }
      for (const i of idx) for (const arr of this.v) {
        const y = arr[i]; if (isFinite(y)) { lo = Math.min(lo, y); hi = Math.max(hi, y); }
      }
      for (const h of this.hlines) { lo = Math.min(lo, h.y); hi = Math.max(hi, h.y); }
      if (!isFinite(lo)) { lo = 0; hi = 1; }
      lo = Math.min(lo, 0); hi = Math.max(hi, 0);
      if (hi - lo < this.o.minSpan) { const c = (hi + lo) / 2; lo = Math.min(lo, c - this.o.minSpan / 2); hi = Math.max(hi, c + this.o.minSpan / 2); }
      const pad = 0.08 * (hi - lo); lo -= pad; hi += pad;
      const X = (t) => L + (t - t0) / (t1 - t0) * pw;
      const Y = (y) => T + (hi - y) / (hi - lo) * ph;

      // 격자와 눈금
      ctx.font = "11px system-ui, sans-serif"; ctx.fillStyle = "#666"; ctx.strokeStyle = "#eee";
      ctx.lineWidth = 1;
      const ys = niceStep(hi - lo, 4);
      ctx.textAlign = "right"; ctx.textBaseline = "middle";
      for (let y = Math.ceil(lo / ys) * ys; y <= hi; y += ys) {
        ctx.beginPath(); ctx.moveTo(L, Y(y)); ctx.lineTo(W - R, Y(y)); ctx.stroke();
        ctx.fillText(Math.abs(y) < 1e-9 ? "0" : +y.toPrecision(4), L - 4, Y(y));
      }
      const xs = niceStep(t1 - t0, 5);
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      for (let t = Math.ceil(t0 / xs) * xs; t <= t1; t += xs) {
        ctx.beginPath(); ctx.moveTo(X(t), T); ctx.lineTo(X(t), T + ph); ctx.stroke();
        ctx.fillText(t.toFixed(xs < 0.1 ? 2 : 1) + " s", X(t), T + ph + 3);
      }
      ctx.strokeStyle = "#bbb"; ctx.beginPath(); ctx.moveTo(L, Y(0)); ctx.lineTo(W - R, Y(0)); ctx.stroke();
      // 기준선 (전류 제한 등)
      for (const h of this.hlines) {
        ctx.save(); ctx.strokeStyle = h.color; ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.moveTo(L, Y(h.y)); ctx.lineTo(W - R, Y(h.y)); ctx.stroke(); ctx.restore();
      }
      // 데이터
      ctx.save(); ctx.beginPath(); ctx.rect(L, T, pw, ph); ctx.clip();
      this.series.forEach((s, k) => {
        ctx.strokeStyle = s.color; ctx.lineWidth = s.width || 2;
        ctx.setLineDash(s.dash ? [6, 4] : []);
        ctx.beginPath(); let pen = false;
        for (const i of idx) {
          const y = this.v[k][i];
          if (!isFinite(y)) { pen = false; continue; }
          if (!pen) { ctx.moveTo(X(this.t[i]), Y(y)); pen = true; } else ctx.lineTo(X(this.t[i]), Y(y));
        }
        ctx.stroke();
      });
      ctx.restore();
      // 제목·범례
      ctx.setLineDash([]); ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.font = "bold 12px system-ui, sans-serif"; ctx.fillStyle = "#333";
      ctx.fillText(this.o.title, L, 4);
      let x = L + ctx.measureText(this.o.title).width + 14;
      ctx.font = "11px system-ui, sans-serif";
      this.series.forEach((s) => {
        ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.setLineDash(s.dash ? [4, 3] : []);
        ctx.beginPath(); ctx.moveTo(x, 10); ctx.lineTo(x + 16, 10); ctx.stroke();
        ctx.setLineDash([]); ctx.fillStyle = "#444"; ctx.fillText(s.name, x + 20, 4);
        x += 28 + ctx.measureText(s.name).width;
      });
    }
  }

  /* '재생 속도' 목록(select#spd)을 퍼센트 슬라이더로 바꾼다 (로그 눈금, 오른쪽 끝 = 100 % 실제 속도).
   * 목록의 가장 작은 값이 최솟값, 원래 선택값이 시작값이 된다. 다른 코드는 그대로 $("spd").value 를 읽는다. */
  function upgradeSpeed() {
    const sel = document.getElementById("spd");
    if (!sel || sel.tagName !== "SELECT") return;
    const vals = [...sel.options].map((o) => +o.value).filter((v) => v > 0);
    const lo = Math.log10(Math.min(...vals, 1)), hi = 0, def = +sel.value || 1;
    const toPos = (v) => Math.round((Math.log10(v) - lo) / (hi - lo) * 1000);
    const toVal = (p) => (p >= 995 ? 1 : Math.pow(10, lo + (hi - lo) * p / 1000));
    const fmt = (v) => {
      const pct = v * 100, n = pct >= 10 ? pct.toFixed(0) : pct >= 1 ? pct.toFixed(1) : pct.toFixed(2);
      return v >= 0.999 ? `${n} % (실제 속도)` : `${n} % (1/${(1 / v) >= 10 ? (1 / v).toFixed(0) : (1 / v).toFixed(1)} 배)`;
    };
    const wrap = document.createElement("span");
    wrap.style.cssText = "display:flex; align-items:center; gap:6px; width:100%";
    const range = document.createElement("input");
    range.type = "range"; range.min = 0; range.max = 1000; range.step = 1; range.value = toPos(def);
    range.style.cssText = "flex:1; min-width:90px"; range.title = "오른쪽 끝 = 실제 속도 100 %, 왼쪽으로 갈수록 느리게 (로그 눈금)";
    const btn = document.createElement("button");
    btn.type = "button"; btn.textContent = "100%"; btn.title = "실제 속도로"; btn.style.cssText = "padding:2px 6px; font-size:11px";
    const hidden = document.createElement("input");
    hidden.type = "hidden"; hidden.id = "spd"; hidden.value = def;
    const lab = document.createElement("b"); lab.textContent = fmt(def); lab.style.whiteSpace = "nowrap";
    const set = (v) => { hidden.value = v; lab.textContent = fmt(v); hidden.dispatchEvent(new Event("input", { bubbles: true })); };
    range.addEventListener("input", (ev) => { ev.stopPropagation(); set(toVal(+range.value)); });
    btn.addEventListener("click", () => { range.value = 1000; set(1); });
    sel.replaceWith(wrap);
    wrap.append(range, btn, hidden);
    const ctl = wrap.closest(".ctl"), L = ctl && ctl.querySelector("label");
    if (ctl) { ctl.style.maxWidth = "none"; ctl.style.minWidth = "220px"; }
    if (L && L.contains(wrap)) { L.insertBefore(lab, wrap); L.style.display = "inline-flex"; L.style.gap = "6px"; L.style.alignItems = "center"; wrap.style.width = "200px"; }
    else if (L) { L.style.display = "flex"; L.style.justifyContent = "space-between"; L.appendChild(lab); }
    else wrap.prepend(lab);
  }
  upgradeSpeed();

  root.RTCharts = { Strip, setupCanvas, upgradeSpeed };
})(this);
