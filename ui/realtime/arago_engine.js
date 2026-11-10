/* 아라고의 원판 (와전류 토크) 엔진.
 * 원판 아래에서 자석 2개(N, S)가 반지름 rm 위치에서 ωm 으로 돈다. 원판 속도 ωd.
 * 자석 아래 원판의 상대 속도 Δv = rm·(ωm − ωd) → 와전류 J ≈ σ·Δv·B → 끌림 힘.
 * 얇은 도체판의 와전류 제동 모델:  F = σ·t·A·B²·Δv / (1 + (Δv/vc)²),  vc = 2/(μ0·σ·t)
 * (속도 차가 작으면 비례, vc 근처에서 최대 — 유도전동기 토크–슬립 곡선과 같은 꼴)
 * 토크 T = 2·rm·F (자석 2개),   J·dωd/dt = T − Tb·sign(ωd) − b·ωd
 */
(function (root) {
  "use strict";
  const MU0 = 4e-7 * Math.PI;
  const MATERIALS = {
    "구리": { sigma: 5.8e7, rho: 8960, color: "#c77d3a" },
    "알루미늄": { sigma: 3.5e7, rho: 2700, color: "#b9c0c8" },
    "황동": { sigma: 1.5e7, rho: 8500, color: "#d4a93c" },
    "스테인리스강": { sigma: 1.4e6, rho: 8000, color: "#8d949c" },
    "홈 판 구리 (방사형 홈)": { sigma: 5.8e7 * 0.12, rho: 8960 * 0.9, color: "#c77d3a", slotted: true },
    "플라스틱 (부도체)": { sigma: 0, rho: 1200, color: "#e8e3d8" },
  };

  class Arago {
    constructor(c) {
      this.c = Object.assign({ R: 0.1, t: 0.002, rm: 0.07, a: 0.02, B0: 0.25, g0: 0.006, gap: 0.004,
                               mat: "구리", wm: 2 * Math.PI, magnetOn: true, Tb: 0, b: 5e-4 }, c);
      this.reset();
    }
    reset() { this.t = 0; this.wd = 0; this.thm = 0; this.thd = 0; }
    set(c) { Object.assign(this.c, c); }
    mat() { return MATERIALS[this.c.mat] || MATERIALS["구리"]; }
    B() { return this.c.magnetOn ? this.c.B0 * Math.exp(-this.c.gap / this.c.g0) : 0; }
    J() { const c = this.c, m = this.mat(); return 0.5 * m.rho * Math.PI * c.R * c.R * c.t * c.R * c.R; }
    vc() { const s = this.mat().sigma; return s > 0 ? 2 / (MU0 * s * this.c.t) : Infinity; }
    /** 상대 각속도 dw = ωm − ωd 에서의 와전류 토크 */
    torque(dw) {
      const c = this.c, s = this.mat().sigma, B = this.B();
      if (s === 0 || B === 0) return 0;
      const dv = c.rm * dw, vc = this.vc();
      const F = s * c.t * c.a * c.a * B * B * dv / (1 + (dv / vc) ** 2);
      return 2 * c.rm * F;
    }
    step(h) {
      const c = this.c, wm = c.magnetOn ? c.wm : 0;
      const f = (wd) => (this.torque(wm - wd) - c.Tb * Math.tanh(wd / 0.5) - c.b * wd) / this.J();
      const k1 = f(this.wd), k2 = f(this.wd + h / 2 * k1), k3 = f(this.wd + h / 2 * k2), k4 = f(this.wd + h * k3);
      this.wd += h / 6 * (k1 + 2 * k2 + 2 * k3 + k4);
      this.thm += wm * h; this.thd += this.wd * h; this.t += h;
    }
    out() {
      const c = this.c, wm = c.magnetOn ? c.wm : 0, dw = wm - this.wd;
      return { t: this.t, wm, wd: this.wd, thm: this.thm, thd: this.thd, T: this.torque(dw),
               Tb: c.Tb * Math.tanh(this.wd / 0.5), slip: Math.abs(wm) > 1e-6 ? dw / wm : NaN,
               B: this.B(), J: this.J(), vc: this.vc(), dw };
    }
  }
  const api = { Arago, MATERIALS, MU0 };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.AragoEngine = api;
})(this);
