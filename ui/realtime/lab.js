/* 강의 실습 탭 공통 틀: 브라우저에서 계산하고 Plotly 로 그림 (슬라이더를 끄는 동안에도 바로 다시 그림).
 *
 * 탭 하나 = Tab, 그 안의 묶음 = Section. 컨트롤은 값이 바뀌면 자기 Section 만(또는 all 옵션이면 탭 전체를)
 * 다음 화면 프레임에 다시 계산합니다. 컨트롤 값은 브라우저에 저장되어 다시 열어도 유지됩니다.
 */
(function (root) {
  "use strict";

  // ------------------------------------------------------------------ 수학
  const M = {
    linspace(a, b, n) { const o = new Array(n); for (let i = 0; i < n; i++) o[i] = n === 1 ? a : a + (b - a) * i / (n - 1); return o; },
    range(n, f) { const o = new Array(n); for (let i = 0; i < n; i++) o[i] = f(i); return o; },
    clip(v, a, b) { return Math.min(Math.max(v, a), b); },
    sum(a) { let s = 0; for (const v of a) s += v; return s; },
    mean(a) { return a.length ? M.sum(a) / a.length : NaN; },
    max(a) { let m = -Infinity; for (const v of a) if (v > m) m = v; return m; },
    min(a) { let m = Infinity; for (const v of a) if (v < m) m = v; return m; },
    ptp(a) { return M.max(a) - M.min(a); },
    trapz(y, x) { let s = 0; for (let i = 1; i < y.length; i++) s += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1]); return s; },
    gradient(y, x) {
      const n = y.length, g = new Array(n);
      for (let i = 0; i < n; i++) {
        if (i === 0) g[i] = (y[1] - y[0]) / (x[1] - x[0]);
        else if (i === n - 1) g[i] = (y[n - 1] - y[n - 2]) / (x[n - 1] - x[n - 2]);
        else g[i] = (y[i + 1] - y[i - 1]) / (x[i + 1] - x[i - 1]);
      }
      return g;
    },
    interp(x, xp, fp) {            // xp 증가 순
      if (x <= xp[0]) return fp[0];
      if (x >= xp[xp.length - 1]) return fp[fp.length - 1];
      let lo = 0, hi = xp.length - 1;
      while (hi - lo > 1) { const m = (lo + hi) >> 1; if (xp[m] <= x) lo = m; else hi = m; }
      const a = (x - xp[lo]) / (xp[hi] - xp[lo]); return fp[lo] + a * (fp[hi] - fp[lo]);
    },
    rad: (d) => d * Math.PI / 180, deg: (r) => r * 180 / Math.PI,
    RPM: 60 / (2 * Math.PI),
    /* 고정 간격 RK4. f(t, x) → dx. 반환 [t 배열, x 배열들] */
    rk4(f, x0, t0, t1, n) {
      const h = (t1 - t0) / n, T = [t0], X = [x0.slice()];
      let x = x0.slice(), t = t0;
      for (let k = 0; k < n; k++) {
        const k1 = f(t, x), xa = x.map((v, i) => v + h / 2 * k1[i]);
        const k2 = f(t + h / 2, xa), xb = x.map((v, i) => v + h / 2 * k2[i]);
        const k3 = f(t + h / 2, xb), xc = x.map((v, i) => v + h * k3[i]);
        const k4 = f(t + h, xc);
        x = x.map((v, i) => v + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]));
        t += h; T.push(t); X.push(x);
      }
      return [T, X];
    },
    /* 다항식 비 num/den (높은 차수부터) 의 계단 응답 (가제어 정준형 + RK4). */
    stepTF(num, den, t) {
      const a0 = den[0], d = den.map((v) => v / a0), nn = num.map((v) => v / a0);
      const n = d.length - 1;
      const b = new Array(n + 1).fill(0); for (let i = 0; i < nn.length; i++) b[n + 1 - nn.length + i] = nn[i];
      const D = b[0];                      // 직달 항
      const c = M.range(n, (i) => b[n - i] - b[0] * d[n - i]);   // c[0] = b_n − b0·d_n ...
      const f = (tt, x) => { const dx = new Array(n); for (let i = 0; i < n - 1; i++) dx[i] = x[i + 1];
        let s = 1; for (let i = 0; i < n; i++) s -= d[n - i] * x[i]; dx[n - 1] = s; return dx; };
      const y = new Array(t.length); let x = new Array(n).fill(0);
      const sub = 8;
      y[0] = D + M.sum(c.map((ci, i) => ci * x[i]));
      for (let k = 1; k < t.length; k++) {
        const h = (t[k] - t[k - 1]) / sub;
        for (let s = 0; s < sub; s++) {
          const k1 = f(0, x), xa = x.map((v, i) => v + h / 2 * k1[i]);
          const k2 = f(0, xa), xb = x.map((v, i) => v + h / 2 * k2[i]);
          const k3 = f(0, xb), xc = x.map((v, i) => v + h * k3[i]);
          const k4 = f(0, xc);
          x = x.map((v, i) => v + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]));
        }
        y[k] = D + c.reduce((s, ci, i) => s + ci * x[i], 0);
        if (!isFinite(y[k]) || Math.abs(y[k]) > 1e6) { for (let j = k; j < t.length; j++) y[j] = NaN; break; }
      }
      return y;
    },
    roots2(a, b, c) {                      // a s² + b s + c = 0 → [[re, im], [re, im]]
      const D = b * b - 4 * a * c;
      if (D >= 0) return [[(-b + Math.sqrt(D)) / (2 * a), 0], [(-b - Math.sqrt(D)) / (2 * a), 0]];
      return [[-b / (2 * a), Math.sqrt(-D) / (2 * a)], [-b / (2 * a), -Math.sqrt(-D) / (2 * a)]];
    },
  };

  // 복소수
  class C {
    constructor(re, im = 0) { this.re = re; this.im = im; }
    add(o) { o = cx(o); return new C(this.re + o.re, this.im + o.im); }
    sub(o) { o = cx(o); return new C(this.re - o.re, this.im - o.im); }
    mul(o) { o = cx(o); return new C(this.re * o.re - this.im * o.im, this.re * o.im + this.im * o.re); }
    div(o) { o = cx(o); const d = o.re * o.re + o.im * o.im; return new C((this.re * o.re + this.im * o.im) / d, (this.im * o.re - this.re * o.im) / d); }
    inv() { return new C(1, 0).div(this); }
    abs() { return Math.hypot(this.re, this.im); }
    arg() { return Math.atan2(this.im, this.re); }
    conj() { return new C(this.re, -this.im); }
    scale(k) { return new C(this.re * k, this.im * k); }
    static polar(r, a) { return new C(r * Math.cos(a), r * Math.sin(a)); }
  }
  const cx = (v) => (v instanceof C ? v : new C(v, 0));
  const par = (a, b) => cx(a).mul(b).div(cx(a).add(b));       // 병렬

  // ------------------------------------------------------------------ 숫자 표시
  const fmt = {
    f(v, d = 2) { return isFinite(v) ? (+v).toFixed(d) : "—"; },
    p(v, d = 3) { return isFinite(v) ? (+(+v).toPrecision(d)).toString() : "—"; },
  };

  // ------------------------------------------------------------------ DOM
  function el(tag, attrs, parent) {
    const e = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (k === "html") e.innerHTML = v; else if (k === "text") e.textContent = v; else if (k === "style") e.style.cssText = v; else e.setAttribute(k, v);
    }
    if (parent) parent.appendChild(e);
    return e;
  }

  let STORE = "lab";
  function loadSaved() { try { return JSON.parse(localStorage.getItem(STORE) || "{}"); } catch (e) { return {}; } }
  function saveVal(k, v) { try { const s = loadSaved(); s[k] = v; localStorage.setItem(STORE, JSON.stringify(s)); } catch (e) {} }

  class Tab {
    constructor(rootEl, id) { this.root = rootEl; this.v = {}; this.sections = []; STORE = "lab-" + id; this.saved = loadSaved(); }
    section(build) { const s = new Section(this); build(s); this.sections.push(s); s.schedule(); return s; }
    scheduleAll() { for (const s of this.sections) s.schedule(); }
  }

  class Section {
    constructor(tab) {
      this.tab = tab; this.v = tab.v;
      this.el = el("div", { class: "sec" }, tab.root);
      this.cur = this.el; this.fn = null; this.pending = false;
    }
    into(e) { this.cur = e || this.el; return this; }
    h(text) { return el("h5", { html: text }, this.cur); }
    note(html) { return el("div", { class: "note", html: html || "" }, this.cur); }
    html(html) { return el("div", { html: html || "" }, this.cur); }
    row() { const r = el("div", { class: "row" }, this.cur); this.cur = r; return r; }
    end() { this.cur = this.el; return this; }
    cols(ws) {
      const r = el("div", { class: "cols" }, this.cur);
      const cs = ws.map((w) => el("div", { class: "col", style: `flex:${w} 1 0` }, r));
      return cs;
    }
    _ctl(key, def, opt) {
      const saved = this.tab.saved[key];
      const v = saved !== undefined && (opt.valid ? opt.valid(saved) : true) ? saved : def;
      this.v[key] = v;
      const wrap = el("div", { class: "ctl" + (opt.wide ? " wide" : "") }, this.cur);
      return [wrap, v];
    }
    _changed(key, v, all) {
      this.v[key] = v; saveVal(key, v);
      if (all) this.tab.scheduleAll(); else this.schedule();
    }
    slider(key, label, min, max, step, val, opt = {}) {
      const [w, v0] = this._ctl(key, val, Object.assign({ valid: (x) => typeof x === "number" && x >= min && x <= max }, opt));
      const lab = el("label", {}, w);
      el("span", { text: label }, lab);
      const out = el("b", {}, lab);
      const inp = el("input", { type: "range", min, max, step, value: v0 }, w);
      const show = (x) => (out.textContent = opt.fmt ? opt.fmt(x) : (+x).toFixed(Math.max(0, -Math.floor(Math.log10(step) + 1e-9))));
      show(v0);
      inp.addEventListener("input", () => { const x = +inp.value; show(x); this._changed(key, x, opt.all); });
      return inp;
    }
    options(key, label, options, val, opt = {}) {   // 이산 값 슬라이더 (select_slider)
      const idx0 = Math.max(0, options.indexOf(val));
      const [w, v0] = this._ctl(key, options[idx0], Object.assign({ valid: (x) => options.includes(x) }, opt));
      const lab = el("label", {}, w); el("span", { text: label }, lab); const out = el("b", {}, lab);
      const inp = el("input", { type: "range", min: 0, max: options.length - 1, step: 1, value: options.indexOf(v0) }, w);
      const show = (x) => (out.textContent = opt.fmt ? opt.fmt(x) : String(x)); show(v0);
      inp.addEventListener("input", () => { const x = options[+inp.value]; show(x); this._changed(key, x, opt.all); });
      return inp;
    }
    select(key, label, options, val, opt = {}) {
      const [w, v0] = this._ctl(key, val, Object.assign({ valid: (x) => options.map(String).includes(String(x)) }, opt));
      el("label", { text: label }, w);
      const s = el("select", {}, w);
      for (const o of options) { const e = el("option", { text: opt.fmt ? opt.fmt(o) : String(o) }, s); e.value = String(o); if (String(o) === String(v0)) e.selected = true; }
      s.addEventListener("change", () => { const x = options.find((o) => String(o) === s.value); this._changed(key, x, opt.all); });
      return s;
    }
    radio(key, label, options, val, opt = {}) {
      const [w, v0] = this._ctl(key, val, Object.assign({ valid: (x) => options.includes(x) }, opt));
      if (label) el("label", { text: label }, w);
      const g = el("div", { class: "radio" + (opt.horiz ? " horiz" : "") }, w);
      const name = "r" + Math.random().toString(36).slice(2);
      for (const o of options) {
        const l = el("label", {}, g);
        const r = el("input", { type: "radio", name }, l); r.checked = o === v0;
        el("span", { text: o }, l);
        r.addEventListener("change", () => { if (r.checked) this._changed(key, o, opt.all); });
      }
      return g;
    }
    check(key, label, val, opt = {}) {
      const [w, v0] = this._ctl(key, val, Object.assign({ valid: (x) => typeof x === "boolean" }, opt));
      const l = el("label", { class: "chk" }, w);
      const c = el("input", { type: "checkbox" }, l); c.checked = v0;
      el("span", { text: label }, l);
      c.addEventListener("change", () => this._changed(key, c.checked, opt.all));
      return c;
    }
    num(key, label, min, max, step, val, opt = {}) {
      const [w, v0] = this._ctl(key, val, Object.assign({ valid: (x) => typeof x === "number" }, opt));
      el("label", { text: label }, w);
      const inp = el("input", { type: "number", min, max, step, value: v0 }, w);
      inp.addEventListener("input", () => { const x = parseFloat(inp.value); if (isFinite(x)) this._changed(key, M.clip(x, min, max), opt.all); });
      return inp;
    }
    plot(height) { const d = el("div", { class: "plot" }, this.cur); d.style.height = height + "px"; d.dataset.h = height; return d; }
    svg(height) { const d = el("div", { class: "svgbox" }, this.cur); d.style.height = height + "px"; return d; }
    metrics(n) { const r = el("div", { class: "metrics" }, this.cur); return M.range(n, () => el("div", { class: "metric" }, r)); }
    table() { return el("div", { class: "tbl" }, this.cur); }
    on(fn) { this.fn = fn; return this; }
    schedule() {
      if (this.pending || !this.fn) return;
      this.pending = true;
      requestAnimationFrame(() => {
        this.pending = false;
        try { this.fn(this.v, this); } catch (e) { console.error(e); this.el.dataset.err = e.message; }
      });
    }
  }

  function metric(cell, label, value, sub) {
    cell.innerHTML = `<div class="ml">${label}</div><div class="mv">${value}</div>` + (sub ? `<div class="ms">${sub}</div>` : "");
  }
  function table(div, headers, rows) {
    div.innerHTML = "<table><tr>" + headers.map((h) => `<th>${h}</th>`).join("") + "</tr>" +
      rows.map((r) => "<tr>" + r.map((c) => `<td>${c}</td>`).join("") + "</tr>").join("") + "</table>";
  }

  // ------------------------------------------------------------------ 그래프
  const COL = ["#1d4ed8", "#d62828", "#2a9d8f", "#e9c46a", "#7c3aed", "#e76f51", "#264653", "#94a3b8"];
  const AX = { showgrid: true, gridcolor: "#eee", zeroline: true, zerolinecolor: "#ccc", linecolor: "#ccc", automargin: true };

  /* 서브플롯 레이아웃. opt: {titles, colw, rowh, xgap, ygap, sharex} */
  function sub(rows, cols, opt = {}) {
    const xgap = opt.xgap ?? 0.08, ygap = opt.ygap ?? (opt.sharex ? 0.06 : 0.14);
    const colw = opt.colw || M.range(cols, () => 1), rowh = opt.rowh || M.range(rows, () => 1);
    const cw = M.sum(colw), rh = M.sum(rowh);
    const W = 1 - xgap * (cols - 1), H = 1 - ygap * (rows - 1);
    const lay = { annotations: [] };
    let y1 = 1;
    for (let r = 0; r < rows; r++) {
      const hh = H * rowh[r] / rh, y0 = y1 - hh;
      let x0 = 0;
      for (let c = 0; c < cols; c++) {
        const ww = W * colw[c] / cw, n = r * cols + c + 1, s = n === 1 ? "" : String(n);
        lay["xaxis" + s] = Object.assign({}, AX, { domain: [x0, x0 + ww], anchor: "y" + s });
        lay["yaxis" + s] = Object.assign({}, AX, { domain: [y0, y1], anchor: "x" + s });
        if (opt.sharex && r < rows - 1) { lay["xaxis" + s].showticklabels = false; }
        if (opt.sharex && n > c + 1) lay["xaxis" + s].matches = "x" + (c + 1 === 1 ? "" : String(c + 1));
        const t = opt.titles && opt.titles[r * cols + c];
        if (t) lay.annotations.push({ text: t, x: x0 + ww / 2, y: y1, xref: "paper", yref: "paper", xanchor: "center", yanchor: "bottom",
          showarrow: false, font: { size: 12, color: "#555" } });
        x0 += ww + xgap;
      }
      y1 = y0 - ygap;
    }
    return lay;
  }
  const ax = (n) => (n <= 1 ? { xaxis: "x", yaxis: "y" } : { xaxis: "x" + n, yaxis: "y" + n });
  const axn = (n) => (n <= 1 ? "" : String(n));
  const hline = (y, n = 1, line = {}) => ({ type: "line", xref: `x${axn(n)} domain`, x0: 0, x1: 1, yref: `y${axn(n)}`, y0: y, y1: y, line: Object.assign({ dash: "dot", color: "#999", width: 1.2 }, line) });
  const vline = (x, n = 1, line = {}) => ({ type: "line", yref: `y${axn(n)} domain`, y0: 0, y1: 1, xref: `x${axn(n)}`, x0: x, x1: x, line: Object.assign({ dash: "dot", color: "#999", width: 1.2 }, line) });
  const vrect = (x0, x1, n = 1, color = "rgba(42,157,143,0.10)") => ({ type: "rect", yref: `y${axn(n)} domain`, y0: 0, y1: 1, xref: `x${axn(n)}`, x0, x1, fillcolor: color, line: { width: 0 }, layer: "below" });
  const rect = (x0, x1, y0, y1, n = 1, color = "rgba(42,157,143,0.10)") => ({ type: "rect", xref: `x${axn(n)}`, yref: `y${axn(n)}`, x0, x1, y0, y1, fillcolor: color, line: { width: 0 }, layer: "below" });
  const label = (x, y, text, n = 1, extra = {}) => Object.assign({ x, y, xref: `x${axn(n)}`, yref: `y${axn(n)}`, text, showarrow: false, font: { size: 11, color: "#444" } }, extra);
  const topLabel = (x, text, n = 1) => ({ x, y: 1, xref: `x${axn(n)}`, yref: `y${axn(n)} domain`, text, showarrow: false, yanchor: "bottom", font: { size: 11, color: "#444" } });

  function line(x, y, name, o = {}) {
    const t = { type: "scatter", mode: "lines", x, y, name, line: { width: 2 } };
    if (o.color) t.line.color = o.color;
    if (o.width) t.line.width = o.width;
    if (o.dash) t.line.dash = o.dash;
    if (o.shape) t.line.shape = o.shape;
    if (o.n) Object.assign(t, ax(o.n));
    if (o.legend === false) t.showlegend = false;
    if (o.fill) { t.fill = o.fill; t.fillcolor = o.fillcolor; }
    if (o.legendgroup) t.legendgroup = o.legendgroup;
    return t;
  }
  function pts(x, y, name, o = {}) {
    const t = { type: "scatter", mode: o.text ? "markers+text" : "markers", x, y, name, marker: { size: o.size || 11, color: o.color || "#d62828", symbol: o.symbol || "circle" } };
    if (o.text) { t.text = o.text; t.textposition = o.textpos || "top left"; }
    if (o.n) Object.assign(t, ax(o.n));
    if (o.legend === false) t.showlegend = false;
    return t;
  }

  function draw(div, traces, layout = {}) {
    if (typeof Plotly === "undefined") { div.innerHTML = '<div class="note">그래프 라이브러리를 불러오지 못했습니다.</div>'; return; }
    const h = +div.dataset.h || 320;
    const base = {
      height: h, margin: { l: 55, r: 15, t: 28, b: 40 }, plot_bgcolor: "white", paper_bgcolor: "white",
      font: { family: "Source Sans Pro, system-ui, sans-serif", size: 11, color: "#333" },
      legend: { orientation: "h", y: -0.22, x: 0, yanchor: "top", font: { size: 11 } }, hovermode: "x unified",
      xaxis: Object.assign({}, AX), yaxis: Object.assign({}, AX), colorway: COL,
    };
    const baseLegend = base.legend, baseMargin = base.margin;
    const lay = Object.assign(base, layout);
    for (const k of Object.keys(layout)) if (/^[xy]axis\d*$/.test(k)) lay[k] = Object.assign({}, AX, layout[k]);
    if (layout.legend) lay.legend = Object.assign({}, baseLegend, layout.legend);
    if (layout.margin) lay.margin = Object.assign({}, baseMargin, layout.margin);
    const nl = (lay.showlegend !== false) && traces.some((t) => t.showlegend !== false && t.name);
    if (nl && !layout.legend) lay.margin.b = Math.max(lay.margin.b, 70);
    // 숨겨진 탭(폭 0)에서 그리면 글자 폭을 0 으로 재서 범례가 겹침 → 보일 때 그림
    if (!div.offsetWidth) { HIDDEN.set(div, [traces, lay]); return; }
    HIDDEN.delete(div);
    Plotly.react(div, traces, lay, { displayModeBar: false, responsive: true });
  }
  const HIDDEN = new Map();
  function flushHidden() { for (const [d, a] of [...HIDDEN]) if (d.offsetWidth) { HIDDEN.delete(d); Plotly.react(d, a[0], a[1], { displayModeBar: false, responsive: true }); } }
  if (typeof window !== "undefined" && window.addEventListener) {
    window.addEventListener("resize", flushHidden);
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(flushHidden).observe(document.documentElement);
  }
  const tx = (title) => ({ title: { text: title, font: { size: 11 } } });

  // ------------------------------------------------------------------ SVG 회로 그림
  const svg = {
    start(w, h) { return [`<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%" font-family="system-ui, sans-serif">`]; },
    line(o, x1, y1, x2, y2, c = "#333", w = 2, dash = "") { o.push(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="${w}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`); },
    poly(o, pts, c = "#333", w = 2, fill = "none") { o.push(`<polyline points="${pts.map((p) => p.join(",")).join(" ")}" stroke="${c}" stroke-width="${w}" fill="${fill}"/>`); },
    rect(o, x, y, w, h, fill = "#fff", c = "#333", sw = 1.5, rx = 3) { o.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${c}" stroke-width="${sw}"/>`); },
    circle(o, x, y, r, fill = "none", c = "#333", w = 2) { o.push(`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${c}" stroke-width="${w}"/>`); },
    text(o, x, y, s, size = 12, c = "#222", anchor = "middle", weight = "normal") { o.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${c}" text-anchor="${anchor}" font-weight="${weight}" dominant-baseline="middle">${s}</text>`); },
    resistor(o, x1, y1, x2, y2, c = "#333") {
      const n = 6, L = Math.hypot(x2 - x1, y2 - y1), ux = (x2 - x1) / L, uy = (y2 - y1) / L, px = -uy, py = ux, lead = 0.2 * L, body = L - 2 * lead;
      const P = [[x1, y1], [x1 + lead * ux, y1 + lead * uy]];
      for (let i = 0; i < n; i++) { const d = lead + body * (i + 0.5) / n, a = 6 * (i % 2 ? -1 : 1); P.push([x1 + d * ux + a * px, y1 + d * uy + a * py]); }
      P.push([x2 - lead * ux, y2 - lead * uy], [x2, y2]); svg.poly(o, P, c);
    },
    inductor(o, x1, y1, x2, y2, c = "#333", loops = 4) {
      const L = Math.hypot(x2 - x1, y2 - y1), ux = (x2 - x1) / L, uy = (y2 - y1) / L, px = -uy, py = ux, lead = 0.15 * L, r = (L - 2 * lead) / loops / 2;
      const P = [[x1, y1]];
      for (let i = 0; i < loops; i++) { const cc = lead + r * (2 * i + 1); for (let k = 0; k <= 12; k++) { const a = Math.PI - Math.PI * k / 12; const d = cc + r * Math.cos(a), hh = r * Math.sin(a) * 1.2; P.push([x1 + d * ux + hh * px, y1 + d * uy + hh * py]); } }
      P.push([x2, y2]); svg.poly(o, P, c);
    },
    arrow(o, x1, y1, x2, y2, c = "#d62828", w = 2.2) {
      const a = Math.atan2(y2 - y1, x2 - x1), s = 8;
      svg.line(o, x1, y1, x2, y2, c, w);
      o.push(`<polygon points="${x2},${y2} ${x2 - s * Math.cos(a - 0.4)},${y2 - s * Math.sin(a - 0.4)} ${x2 - s * Math.cos(a + 0.4)},${y2 - s * Math.sin(a + 0.4)}" fill="${c}"/>`);
    },
    sw(o, x, y, on, lab, w = 26, h = 34) {     // 스위치 (켜지면 초록) + 역병렬 다이오드
      svg.rect(o, x - w / 2, y - h / 2, w, h, on ? "#4ade80" : "#fff");
      svg.text(o, x, y, lab, 11, "#111", "middle", "bold");
      const dx = w / 2 + 9;
      svg.poly(o, [[x + w / 2, y - h / 2 + 3], [x + dx, y - h / 2 + 3], [x + dx, y + h / 2 - 3], [x + w / 2, y + h / 2 - 3]], "#333", 1.2);
      o.push(`<polygon points="${x + dx - 5},${y + 4} ${x + dx + 5},${y + 4} ${x + dx},${y - 4}" fill="#333"/>`);
      svg.line(o, x + dx - 5, y - 4, x + dx + 5, y - 4, "#333", 1.2);
    },
    source(o, x, y, r, lab) { svg.circle(o, x, y, r); svg.text(o, x, y - r * 0.45, "+", 14); svg.text(o, x, y + r * 0.45, "−", 14); svg.text(o, x - r - 6, y, lab, 13, "#222", "end"); },
    done(o) { o.push("</svg>"); return o.join(""); },
  };

  root.Lab = { M, C, cx, par, fmt, el, Tab, Section, metric, table, sub, ax, axn, hline, vline, vrect, rect, label, topLabel, line, pts, draw, tx, svg, COL };
  if (typeof module !== "undefined" && module.exports) module.exports = root.Lab;
})(typeof window !== "undefined" ? window : globalThis);
