/* 교류 전동기 실시간 엔진: 유도전동기(αβ 동적 모델) + PMSM(dq 모델) + 제어기.
 * motors/ac/induction.py, motors/ac/pmsm.py 와 같은 식. 단위 SI, 진폭 불변 변환. */
(function (root) {
  "use strict";
  const TWO_PI = 2 * Math.PI, S23 = Math.sqrt(2 / 3), SQ3 = Math.sqrt(3);
  const clip = (x, lo, hi) => Math.min(Math.max(x, lo), hi);
  const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));
  const abc = (al, be) => [al, -0.5 * al + SQ3 / 2 * be, -0.5 * al - SQ3 / 2 * be];

  function rk4(f, x, h, n) {
    const k1 = f(x), y = new Float64Array(n);
    for (let i = 0; i < n; i++) y[i] = x[i] + h / 2 * k1[i];
    const k2 = f(y); for (let i = 0; i < n; i++) y[i] = x[i] + h / 2 * k2[i];
    const k3 = f(y); for (let i = 0; i < n; i++) y[i] = x[i] + h * k3[i];
    const k4 = f(y);
    for (let i = 0; i < n; i++) x[i] += h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]);
  }

  // PI (출력 제한 + 조건부 적분 안티와인드업)
  class PI {
    constructor() { this.x = 0; }
    step(kp, ki, e, dt, lo, hi, aw, ff) {
      const u = kp * e + this.x + (ff || 0), y = clip(u, lo, hi);
      if (!aw || !((u > y && e > 0) || (u < y && e < 0))) this.x += ki * e * dt;
      return y;
    }
  }

  // ================= 유도전동기 =================
  class IMSim {
    /* p: {V, f, Rs, Rr, Lls, Llr, Lm, poles, J, B} */
    constructor(p) {
      this.p = p; this.pp = Math.round(p.poles / 2);
      this.Ls = p.Lls + p.Lm; this.Lr = p.Llr + p.Lm; this.D = this.Ls * this.Lr - p.Lm * p.Lm;
      this.u = { mode: "grid", V: p.V, f: p.f, TL: 0, friction: false, va: 0, vb: 0 };
      this.reset();
    }
    reset() { this.t = 0; this.x = new Float64Array(7); }   // psa psb pra prb w θs θm
    set(c) { Object.assign(this.u, c); }
    cur(x) {
      const { Ls, Lr, D } = this, Lm = this.p.Lm;
      return [(Lr * x[0] - Lm * x[2]) / D, (Lr * x[1] - Lm * x[3]) / D, (Ls * x[2] - Lm * x[0]) / D, (Ls * x[3] - Lm * x[1]) / D];
    }
    volt(x) {
      const u = this.u;
      if (u.mode === "grid") { const Vm = S23 * u.V; return [Vm * Math.cos(x[5]), Vm * Math.sin(x[5])]; }
      return [u.va, u.vb];
    }
    load(w) { return this.u.friction ? this.u.TL * Math.tanh(w / 1.0) : this.u.TL; }
    f(x) {
      const p = this.p, [isa, isb, ira, irb] = this.cur(x), [va, vb] = this.volt(x), wr = this.pp * x[4];
      const Te = 1.5 * this.pp * (x[0] * isb - x[1] * isa);
      return [va - p.Rs * isa, vb - p.Rs * isb, -p.Rr * ira - wr * x[3], -p.Rr * irb + wr * x[2],
              (Te - p.B * x[4] - this.load(x[4])) / p.J, this.u.mode === "grid" ? TWO_PI * this.u.f : 0, x[4]];
    }
    step(h) { rk4((y) => this.f(y), this.x, h, 7); this.t += h; }
    out() {
      const x = this.x, [isa, isb, ira, irb] = this.cur(x), [va, vb] = this.volt(x);
      const Te = 1.5 * this.pp * (x[0] * isb - x[1] * isa), [ia, ib, ic] = abc(isa, isb);
      const thr = Math.atan2(x[3], x[2]);                       // 회전자 자속 각
      const c = Math.cos(thr), s = Math.sin(thr);
      return { t: this.t, w: x[4], thm: x[6], ths: x[5], isa, isb, ira, irb, ia, ib, ic, Te, TL: this.load(x[4]),
               va, vb, Vmag: Math.hypot(va, vb), psr: Math.hypot(x[2], x[3]), thr,
               id: isa * c + isb * s, iq: -isa * s + isb * c, Is: Math.hypot(isa, isb) / Math.SQRT2 };
    }
  }

  /* 유도전동기 구동: V/f 또는 간접 벡터 제어(IFOC) */
  class IMDrive {
    constructor(p, c) { this.m = new IMSim(p); this.m.set({ mode: "ext" }); this.c = Object.assign({}, c); this.reset(); }
    reset() { this.m.reset(); this.fcmd = 0; this.th = 0; this.slip = 0; this.spd = new PI(); this.pd = new PI(); this.pq = new PI(); this.t = 0; this.acc = 0;
              this.iqRef = NaN; this.idRef = NaN; this.vd = 0; this.vq = 0; this.fout = 0; }
    set(c) { Object.assign(this.c, c); }
    advance(dt) {
      const c = this.c, p = this.m.p, m = this.m, pp = m.pp, Ts = c.Ts, Vmax = S23 * p.V;
      m.set({ TL: c.TL, friction: c.friction });
      this.acc += dt;
      while (this.acc >= Ts) {
        this.acc -= Ts;
        const o = m.out();
        let va, vb;
        if (c.mode === "vf") {
          // 주파수 지령 = 속도 지령 + (선택) 슬립 보상, 가감속 제한
          let ftgt = pp * c.wRef / TWO_PI;
          // 슬립 추정 Δf = Te·Rr / (1.5·pp·ψr²) / 2π, 저역통과 필터 (τ = 0.1 s) 로 진동 방지
          const raw = o.psr > 1e-3 ? (o.Te * p.Rr / (1.5 * pp * o.psr * o.psr)) / TWO_PI : 0;
          this.slip += Ts / 0.1 * (raw - this.slip);
          if (c.slipComp) ftgt += this.slip;
          const df = c.ramp * Ts; this.fcmd += clip(ftgt - this.fcmd, -df, df);
          const fr = Math.abs(this.fcmd) / p.f;
          const V = Math.min(p.V, p.V * fr + c.boost * Math.max(0, 1 - fr));
          this.th += TWO_PI * this.fcmd * Ts;
          va = S23 * V * Math.cos(this.th); vb = S23 * V * Math.sin(this.th);
          this.fout = this.fcmd; this.iqRef = NaN; this.idRef = NaN;
        } else {
          // 간접 벡터 제어: θe = ∫(ωr + ωslip),  ωslip = iq*/(τr·id*)
          const tr = m.Lr / p.Rr, sigLs = m.Ls - p.Lm * p.Lm / m.Lr;
          const wb = TWO_PI * p.f / pp;
          let idr = c.idRated * Math.min(1, wb / Math.max(Math.abs(o.w), 1e-6));          // 기저 속도 위 약계자
          if (!c.fieldWeak) idr = c.idRated;
          const iqLim = Math.sqrt(Math.max(c.Ilim * c.Ilim - idr * idr, 0));
          const iqr = this.spd.step(c.Kpw, c.Kiw, c.wRef - o.w, Ts, -iqLim, iqLim, c.aw);
          const wsl = iqr / (tr * Math.max(idr, 1e-6));
          const we = pp * o.w + wsl;
          this.th += we * Ts;
          const cs = Math.cos(this.th), sn = Math.sin(this.th);
          const id = o.isa * cs + o.isb * sn, iq = -o.isa * sn + o.isb * cs;
          const Rsig = p.Rs + p.Rr * (p.Lm / m.Lr) ** 2;
          const ffd = c.ff ? -we * sigLs * iq : 0, ffq = c.ff ? we * (sigLs * id + p.Lm * p.Lm / m.Lr * idr) : 0;
          let vd = this.pd.step(c.Kpi, c.Kii, idr - id, Ts, -Vmax, Vmax, c.aw, ffd);
          let vq = this.pq.step(c.Kpi, c.Kii, iqr - iq, Ts, -Vmax, Vmax, c.aw, ffq);
          const vm = Math.hypot(vd, vq); if (vm > Vmax) { vd *= Vmax / vm; vq *= Vmax / vm; }
          this.vd = vd; this.vq = vq;
          va = vd * cs - vq * sn; vb = vd * sn + vq * cs;
          this.iqRef = iqr; this.idRef = idr; this.fout = we / TWO_PI;
          void Rsig;
        }
        m.set({ va, vb });
        const n = Math.max(1, Math.round(Ts / (c.h || 5e-5)));
        for (let i = 0; i < n; i++) m.step(Ts / n);
        this.t += Ts;
      }
    }
    out() {
      const o = this.m.out();
      if (this.c.mode === "foc") {   // 제어기 좌표계의 dq 전류
        const cs = Math.cos(this.th), sn = Math.sin(this.th);
        o.idc = o.isa * cs + o.isb * sn; o.iqc = -o.isa * sn + o.isb * cs;
      } else { o.idc = o.id; o.iqc = o.iq; }
      return Object.assign(o, { wRef: this.c.wRef, iqRef: this.iqRef, idRef: this.idRef, fout: this.fout });
    }
  }
  function imGains(p, wci, wcs, idRated) {
    const Ls = p.Lls + p.Lm, Lr = p.Llr + p.Lm, sigLs = Ls - p.Lm * p.Lm / Lr, pp = Math.round(p.poles / 2);
    const Rsig = p.Rs + p.Rr * (p.Lm / Lr) ** 2, KT = 1.5 * pp * p.Lm * p.Lm / Lr * idRated;
    const Kpw = wcs * p.J / KT;
    return { Kpi: wci * sigLs, Kii: wci * Rsig, Kpw, Kiw: Kpw * wcs / 4 };
  }
  /* 정격 자속에 해당하는 d축 전류 (V/f 정격점의 회전자 자속 / Lm) */
  function imIdRated(p) {
    const we = TWO_PI * p.f, Ls = p.Lls + p.Lm;
    return S23 * p.V / (we * Ls);
  }

  // ================= PMSM =================
  class PMSMSim {
    /* p: {Vdc, Rs, Ld, Lq, lam, poles, J, B} */
    constructor(p) { this.p = p; this.pp = Math.round(p.poles / 2); this.u = { vd: 0, vq: 0, TL: 0, friction: false }; this.reset(); }
    reset() { this.t = 0; this.x = new Float64Array(4); }     // id iq w θm
    set(c) { Object.assign(this.u, c); }
    torque(id, iq) { const p = this.p; return 1.5 * this.pp * (p.lam * iq + (p.Ld - p.Lq) * id * iq); }
    load(w) { return this.u.friction ? this.u.TL * Math.tanh(w / 1.0) : this.u.TL; }
    f(x) {
      const p = this.p, u = this.u, we = this.pp * x[2];
      return [(u.vd - p.Rs * x[0] + we * p.Lq * x[1]) / p.Ld,
              (u.vq - p.Rs * x[1] - we * (p.Ld * x[0] + p.lam)) / p.Lq,
              (this.torque(x[0], x[1]) - p.B * x[2] - this.load(x[2])) / p.J, x[2]];
    }
    step(h) { rk4((y) => this.f(y), this.x, h, 4); this.t += h; }
    out() {
      const x = this.x, the = this.pp * x[3], c = Math.cos(the), s = Math.sin(the);
      const isa = x[0] * c - x[1] * s, isb = x[0] * s + x[1] * c, [ia, ib, ic] = abc(isa, isb);
      return { t: this.t, id: x[0], iq: x[1], w: x[2], thm: x[3], the, isa, isb, ia, ib, ic,
               Te: this.torque(x[0], x[1]), TL: this.load(x[2]), vd: this.u.vd, vq: this.u.vq };
    }
  }
  function pmsmMTPA(p, I) {
    const dL = p.Lq - p.Ld, s = Math.sign(I) || 1, a = Math.abs(I);
    if (Math.abs(dL) < 1e-12) return [0, I];
    const id = (p.lam - Math.sqrt(p.lam * p.lam + 8 * dL * dL * a * a)) / (4 * dL);
    return [id, s * Math.sqrt(Math.max(a * a - id * id, 0))];
  }
  /* PMSM 벡터 제어: 속도 PI → 전류 지령 (id=0 / MTPA / MTPA+약계자) → dq 전류 PI (+비간섭) → 전압 한계 원 */
  class PMSMDrive {
    constructor(p, c) { this.m = new PMSMSim(p); this.c = Object.assign({}, c); this.reset(); }
    reset() { this.m.reset(); this.spd = new PI(); this.pd = new PI(); this.pq = new PI(); this.fw = 0; this.t = 0; this.acc = 0;
              this.idRef = 0; this.iqRef = 0; this.vmag = 0; }
    set(c) { Object.assign(this.c, c); }
    advance(dt) {
      const c = this.c, m = this.m, p = m.p, pp = m.pp, Ts = c.Ts, Vmax = p.Vdc / SQ3;
      m.set({ TL: c.TL, friction: c.friction });
      this.acc += dt;
      while (this.acc >= Ts) {
        this.acc -= Ts;
        const o = m.out(), we = pp * o.w;
        const Icmd = this.spd.step(c.Kpw, c.Kiw, c.wRef - o.w, Ts, -c.Imax, c.Imax, c.aw);   // 전류 크기 지령 (부호 = 토크 방향)
        let id, iq;
        if (c.mode === "id0") { id = c.idManual || 0; iq = Icmd; }
        else { [id, iq] = pmsmMTPA(p, Icmd); }
        if (c.mode === "fw") {
          // 약계자: 전압 여유가 없으면 id 를 음으로 더 보냄 (전압 피드백 적분)
          this.fw = clip(this.fw - c.Kfw * (this.vmag - 0.95 * Vmax) * Ts, -c.Imax, 0);
          id = Math.min(id, 0) + this.fw;
          id = Math.max(id, -c.Imax);
          const iqMax = Math.sqrt(Math.max(c.Imax * c.Imax - id * id, 0));
          iq = clip(iq, -iqMax, iqMax);
        }
        this.idRef = id; this.iqRef = iq;
        const ffd = c.ff ? -we * p.Lq * o.iq : 0, ffq = c.ff ? we * (p.Ld * o.id + p.lam) : 0;
        let vd = this.pd.step(c.Kpd, c.Kid, id - o.id, Ts, -Vmax, Vmax, c.aw, ffd);
        let vq = this.pq.step(c.Kpq, c.Kiq, iq - o.iq, Ts, -Vmax, Vmax, c.aw, ffq);
        const vm = Math.hypot(vd, vq); if (vm > Vmax) { vd *= Vmax / vm; vq *= Vmax / vm; }
        this.vmag = Math.hypot(vd, vq);
        m.set({ vd, vq });
        const n = Math.max(1, Math.round(Ts / (c.h || 2e-5)));
        for (let i = 0; i < n; i++) m.step(Ts / n);
        this.t += Ts;
      }
    }
    out() { return Object.assign(this.m.out(), { wRef: this.c.wRef, idRef: this.idRef, iqRef: this.iqRef, vmag: this.vmag, Vmax: this.m.p.Vdc / SQ3 }); }
  }
  function pmsmGains(p, wci, wcs) {
    const pp = Math.round(p.poles / 2), KT = 1.5 * pp * p.lam, Kpw = wcs * p.J / KT;
    return { Kpd: wci * p.Ld, Kid: wci * p.Rs, Kpq: wci * p.Lq, Kiq: wci * p.Rs, Kpw, Kiw: Kpw * wcs / 4 };
  }

  const api = { IMSim, IMDrive, imGains, imIdRated, PMSMSim, PMSMDrive, pmsmGains, pmsmMTPA, abc, wrap };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ACEngine = api;
})(this);
