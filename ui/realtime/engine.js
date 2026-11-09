/* DC 전동기 실시간 시뮬레이션 엔진 (브라우저에서 실행).
 * 파이썬 motors/dc 모델, control/cascade.py 와 같은 식을 쓴다. 단위는 SI.
 *
 *   E = Kφ·ω,  Te = Kφ·Ia
 *   L·dIa/dt = V − R·Ia − E
 *   J·dω/dt  = Te − B·ω − TL
 */
(function (root) {
  "use strict";

  // ---------------- 전동기 (여자 방식별) ----------------
  class Motor {
    constructor(p, type, sigma) {
      this.p = p;              // SI 파라미터
      this.type = type;        // separately | shunt | series | compound
      this.sigma = sigma >= 0 ? 1 : -1;
    }
    hasSeriesField() { return this.type === "series" || this.type === "compound"; }
    Rarm(u) { return this.p.Ra + (this.hasSeriesField() ? this.p.Rs : 0) + (u.Rst || 0); }
    Larm() { return this.p.La + (this.hasSeriesField() ? this.p.Ls : 0); }
    Rfield(u) { return this.p.Rf + u.Rfx; }
    fieldSource(u) { return this.type === "separately" ? u.Vf : u.V; }
    ifOf(s) { return this.type === "series" ? s[0] : s[1]; }
    kphi(ia, iff) {
      const p = this.p;
      switch (this.type) {
        case "series": return p.Ms * ia;
        case "compound": return p.Laf * iff + this.sigma * p.Ms * ia;
        default: return p.Laf * iff;
      }
    }
    fieldSteady(u) {
      return this.type === "series" ? 0 : this.fieldSource(u) / this.Rfield(u);
    }
    load(u, w) { return u.friction ? u.TL * Math.tanh(w / 1.0) : u.TL; }
    deriv(s, u, out) {
      const ia = s[0], w = s[2], iff = this.ifOf(s);
      const k = this.kphi(ia, iff);
      out[0] = (u.V - this.Rarm(u) * ia - k * w) / this.Larm();
      out[1] = this.type === "series" ? 0 : (this.fieldSource(u) - this.Rfield(u) * s[1]) / this.p.Lf;
      out[2] = (k * ia - this.p.B * w - this.load(u, w)) / this.p.J;
    }
    /** 가장 빠른 시정수의 1/10 이하로 적분 스텝을 정한다. */
    stepSize(u) {
      let tau = this.Larm() / this.Rarm(u);
      if (this.type !== "series") tau = Math.min(tau, this.p.Lf / this.Rfield(u));
      return Math.min(5e-5, tau / 20);
    }
  }

  function rk4(f, s, h, tmp) {
    const n = s.length;
    const k1 = tmp[0], k2 = tmp[1], k3 = tmp[2], k4 = tmp[3], y = tmp[4];
    f(s, k1);
    for (let i = 0; i < n; i++) y[i] = s[i] + h / 2 * k1[i];
    f(y, k2);
    for (let i = 0; i < n; i++) y[i] = s[i] + h / 2 * k2[i];
    f(y, k3);
    for (let i = 0; i < n; i++) y[i] = s[i] + h * k3[i];
    f(y, k4);
    for (let i = 0; i < n; i++) s[i] += h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]);
  }
  const tmpN = (n) => [0, 1, 2, 3, 4].map(() => new Float64Array(n));

  // ---------------- 개루프 전동기 시뮬레이션 (원리 탭) ----------------
  class MotorSim {
    constructor(motor, u) {
      this.m = motor;
      this.u = Object.assign({}, u);
      this.tmp = tmpN(3);
      this.d = new Float64Array(3);
      this.reset();
    }
    reset() {
      this.t = 0;
      this.s = new Float64Array([0, this.m.fieldSteady(this.u), 0]); // 계자는 미리 여자
    }
    set(changes) { Object.assign(this.u, changes); }
    advance(dt) {
      const h = this.m.stepSize(this.u);
      const n = Math.max(1, Math.ceil(dt / h));
      const hh = dt / n;
      const f = (s, out) => this.m.deriv(s, this.u, out);
      for (let i = 0; i < n; i++) {
        rk4(f, this.s, hh, this.tmp);
        if (!isFinite(this.s[2]) || Math.abs(this.s[2]) > 1e5) { this.s[2] = Math.sign(this.s[2]) * 1e5; }
      }
      this.t += dt;
    }
    out() {
      const s = this.s, m = this.m, u = this.u;
      const ia = s[0], w = s[2], iff = m.ifOf(s);
      const k = m.kphi(ia, iff);
      const E = k * w, vR = ia * m.Rarm(u);
      return { t: this.t, ia, if: iff, w, k, E, Te: k * ia, TL: m.load(u, w),
               V: u.V, vR, vL: u.V - vR - E };
    }
  }

  // ---------------- 이중 루프 속도 제어 (제어 탭) ----------------
  class PI {
    constructor() { this.xi = 0; }
    step(kp, ki, err, dt, lo, hi, aw, ff) {
      const uu = kp * err + this.xi + (ff || 0);
      const y = Math.min(Math.max(uu, lo), hi);
      const sat = (uu > hi && err > 0) || (uu < lo && err < 0);
      if (!aw || !sat) this.xi += ki * err * dt;
      return [y, uu];
    }
  }

  class CascadeSim {
    /* p: {Ra, La, J, B, V}, K: Kφ (일정), c: 설정 (실행 중 바꿔도 됨) */
    constructor(p, K, c) {
      this.p = p; this.K = K; this.c = Object.assign({}, c);
      this.tmp = tmpN(2);
      this.reset();
    }
    reset() {
      this.t = 0; this.acc = 0;
      this.s = new Float64Array([0, 0]);   // ia, ω
      this.spd = new PI(); this.cur = new PI();
      this.iaRef = 0; this.va = 0; this.vaCmd = 0;
    }
    set(changes) { Object.assign(this.c, changes); }
    load(w) { const c = this.c; return c.friction ? c.TL * Math.tanh(w / 1.0) : c.TL; }
    advance(dt) {
      const c = this.c, p = this.p, K = this.K;
      const Ts = c.Ts;
      const vmin = c.quadrants === 1 ? 0 : -p.V, vmax = p.V;
      const ilo = c.quadrants === 1 ? 0 : -c.Ilim;
      const f = (s, out) => {
        out[0] = (this.va - p.Ra * s[0] - K * s[1]) / p.La;
        out[1] = (K * s[0] - p.B * s[1] - this.load(s[1])) / p.J;
      };
      this.acc += dt;
      while (this.acc >= Ts) {
        this.acc -= Ts;
        const ia = this.s[0], w = this.s[1];
        if (c.openLoop) {
          this.iaRef = NaN;
          this.vaCmd = K * c.wRef;
        } else {
          this.iaRef = this.spd.step(c.Kpw, c.Kiw, c.wRef - w, Ts, ilo, c.Ilim, c.aw)[0];
          this.vaCmd = this.cur.step(c.Kpi, c.Kii, this.iaRef - ia, Ts, vmin, vmax, c.aw,
                                     c.ff ? K * w : 0)[0];
        }
        this.va = Math.min(Math.max(this.vaCmd, vmin), vmax);
        rk4(f, this.s, Ts, this.tmp);
        if (c.quadrants === 1 && this.s[0] < 0) this.s[0] = 0;  // 다이오드: 전류 단방향
        this.t += Ts;
      }
    }
    out() {
      const ia = this.s[0], w = this.s[1], E = this.K * w;
      const vaTerm = (this.c.quadrants === 1 && ia <= 0 && this.va < E) ? E : this.va;
      return { t: this.t, ia, w, wRef: this.c.wRef, iaRef: this.iaRef, va: vaTerm, E,
               Te: this.K * ia, TL: this.load(w) };
    }
  }

  function recommendedGains(p, K, wci, wcs) {
    const Kpi = wci * p.La, Kii = wci * p.Ra;
    const Kpw = wcs * p.J / K, Kiw = Kpw * wcs / 4;
    return { Kpw, Kiw, Kpi, Kii };
  }

  const api = { Motor, MotorSim, CascadeSim, PI, recommendedGains };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DCEngine = api;
})(this);
