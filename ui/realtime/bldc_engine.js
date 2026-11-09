/* BLDC 실시간 엔진 (motors/ac/bldc.py 와 같은 식). 단위 SI.
 * 3상 Y결선, 사다리꼴 역기전력, 홀 센서 6스텝 정류, 평균값 PWM, 환류 다이오드 정류 과정 포함. */
(function (root) {
  "use strict";
  const TWO_PI = 2 * Math.PI;
  const SHIFT = [0, TWO_PI / 3, -TWO_PI / 3];
  const COMM = { 4: [0, 1], 6: [0, 2], 2: [1, 2], 3: [1, 0], 1: [2, 0], 5: [2, 1] };
  const mod = (x, m) => ((x % m) + m) % m;

  function trap(th) {
    const x = mod(th, TWO_PI), a = Math.PI / 6;
    if (x < a) return x / a;
    if (x < 5 * a) return 1;
    if (x < 7 * a) return 1 - (x - 5 * a) / a;
    if (x < 11 * a) return -1;
    return -1 + (x - 11 * a) / a;
  }
  function hallCode(te, off) {
    let c = 0;
    for (let k = 0; k < 3; k++) if (mod(te + off + Math.PI / 6 - SHIFT[k], TWO_PI) < Math.PI) c |= 1 << (2 - k);
    return c;
  }

  class BLDCSim {
    /* p: {Vdc, R, L, ke, poles, J, B} */
    constructor(p) { this.p = p; this.pp = Math.round(p.poles / 2); this.u = { duty: 1, TL: 0, hallOffset: 0, friction: false }; this.reset(); }
    reset() { this.t = 0; this.x = new Float64Array(5); }
    set(c) { Object.assign(this.u, c); }
    inverter(x) {
      const u = this.u, code = hallCode(this.pp * x[4], u.hallOffset);
      let [H, L] = COMM[code];
      if (u.duty < 0) [H, L] = [L, H];
      const F = 3 - H - L, v = [0, 0, 0];
      v[H] = Math.min(Math.abs(u.duty), 1) * this.p.Vdc;
      let mode = "two";
      if (Math.abs(x[F]) > 1e-9) { v[F] = x[F] > 0 ? 0 : this.p.Vdc; mode = "three"; }
      return { v, mode, H, L, F, code };
    }
    deriv(x, inf, out) {
      const p = this.p, u = this.u, w = x[3], te = this.pp * x[4];
      const f0 = trap(te - SHIFT[0]), f1 = trap(te - SHIFT[1]), f2 = trap(te - SHIFT[2]);
      const e = [p.ke * w * f0, p.ke * w * f1, p.ke * w * f2], v = inf.v;
      if (inf.mode === "three") {
        const vn = (v[0] + v[1] + v[2] - e[0] - e[1] - e[2]) / 3;
        for (let k = 0; k < 3; k++) out[k] = (v[k] - vn - p.R * x[k] - e[k]) / p.L;
      } else {
        const { H, L, F } = inf;
        const d = (v[H] - v[L] - p.R * (x[H] - x[L]) - (e[H] - e[L])) / (2 * p.L);
        out[H] = d; out[L] = -d; out[F] = 0;
      }
      const Te = p.ke * (f0 * x[0] + f1 * x[1] + f2 * x[2]);
      const TL = u.friction ? u.TL * Math.tanh(w / 1.0) : u.TL;
      out[3] = (Te - p.B * w - TL) / p.J;
      out[4] = w;
    }
    step(h) {
      const x = this.x, inf = this.inverter(x);
      const k = [0, 1, 2, 3].map(() => new Float64Array(5)), y = new Float64Array(5);
      this.deriv(x, inf, k[0]);
      for (let i = 0; i < 5; i++) y[i] = x[i] + h / 2 * k[0][i]; this.deriv(y, inf, k[1]);
      for (let i = 0; i < 5; i++) y[i] = x[i] + h / 2 * k[1][i]; this.deriv(y, inf, k[2]);
      for (let i = 0; i < 5; i++) y[i] = x[i] + h * k[2][i]; this.deriv(y, inf, k[3]);
      const old = x[inf.F];
      for (let i = 0; i < 5; i++) x[i] += h / 6 * (k[0][i] + 2 * k[1][i] + 2 * k[2][i] + k[3][i]);
      const { H, L, F } = inf;
      if (inf.mode === "three" && Math.sign(x[F]) !== Math.sign(old)) {
        x[F] = 0; const m = (x[H] - x[L]) / 2; x[H] = m; x[L] = -m;
      }
      if (inf.mode === "two") { x[F] = 0; x[L] = -x[H]; }
      this.t += h;
    }
    advance(dt, h) { const n = Math.max(1, Math.round(dt / h)); for (let i = 0; i < n; i++) this.step(dt / n); }
    out() {
      const p = this.p, x = this.x, w = x[3], te = this.pp * x[4], inf = this.inverter(x);
      const f = SHIFT.map((s) => trap(te - s));
      const Te = p.ke * (f[0] * x[0] + f[1] * x[1] + f[2] * x[2]);
      return { t: this.t, ia: x[0], ib: x[1], ic: x[2], w, thm: x[4], te: mod(te, TWO_PI),
               ea: p.ke * w * f[0], eb: p.ke * w * f[1], ec: p.ke * w * f[2], f, Te,
               TL: this.u.friction ? this.u.TL * Math.tanh(w) : this.u.TL,
               iT: Te / (2 * p.ke), code: inf.code, H: inf.H, L: inf.L, F: inf.F, mode: inf.mode,
               duty: this.u.duty };
    }
  }

  /* 속도 PI → 토크 전류 제한 → 전류 PI (+ 역기전력 FF) → 듀티 → 6스텝 인버터 → BLDC */
  class BLDCCascade {
    constructor(p, c) { this.sim = new BLDCSim(p); this.c = Object.assign({}, c); this.reset(); }
    reset() { this.sim.reset(); this.xs = 0; this.xc = 0; this.iRef = 0; this.vCmd = 0; this.acc = 0; this.t = 0; }
    set(c) { Object.assign(this.c, c); this.sim.set({ TL: this.c.TL, friction: this.c.friction, hallOffset: this.c.hallOffset || 0 }); }
    advance(dt) {
      const c = this.c, p = this.sim.p, K = 2 * p.ke, Ts = c.Ts, h = c.h || 1e-5;
      this.sim.set({ TL: c.TL, friction: c.friction, hallOffset: c.hallOffset || 0 });
      this.acc += dt;
      while (this.acc >= Ts) {
        this.acc -= Ts;
        const o = this.sim.out();
        if (c.openLoop) { this.iRef = NaN; this.vCmd = K * c.wRef; }
        else {
          const e = c.wRef - o.w;
          let uu = c.Kpw * e + this.xs, y = Math.min(Math.max(uu, -c.Ilim), c.Ilim);
          if (!c.aw || !((uu > y && e > 0) || (uu < y && e < 0))) this.xs += c.Kiw * e * Ts;
          this.iRef = y;
          const ei = this.iRef - o.iT;
          uu = c.Kpi * ei + this.xc + (c.ff ? K * o.w : 0);
          y = Math.min(Math.max(uu, -p.Vdc), p.Vdc);
          if (!c.aw || !((uu > y && ei > 0) || (uu < y && ei < 0))) this.xc += c.Kii * ei * Ts;
          this.vCmd = y;
        }
        this.sim.set({ duty: Math.min(Math.max(this.vCmd / p.Vdc, -1), 1) });
        const n = Math.max(1, Math.round(Ts / h));
        for (let i = 0; i < n; i++) this.sim.step(Ts / n);
        this.t += Ts;
      }
    }
    out() { return Object.assign(this.sim.out(), { wRef: this.c.wRef, iRef: this.iRef, v: this.vCmd }); }
  }

  function recommendedGains(p, wci, wcs) {
    const K = 2 * p.ke;
    const Kpi = wci * 2 * p.L, Kii = wci * 2 * p.R;      // 선간 회로 2R, 2L
    const Kpw = wcs * p.J / K, Kiw = Kpw * wcs / 4;
    return { Kpw, Kiw, Kpi, Kii };
  }

  const api = { BLDCSim, BLDCCascade, trap, hallCode, recommendedGains, COMM };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.BLDCEngine = api;
})(this);
