/* 블록 다이어그램 시뮬레이션 엔진.
 * 블록을 선으로 이어 만든 제어 구조를 고정 스텝 h 로 실시간 계산한다.
 *
 * 한 스텝 순서
 *   1) 상태만으로 출력이 정해지는 블록(전동기, 적분기, 1차 지연) 출력 계산
 *   2) 입력이 바로 출력에 영향을 주는 블록(게인, 합산, PID ...)을 위상 정렬 순서로 계산
 *      → 이런 블록끼리 고리를 이루면 '대수 루프' 오류
 *   3) 모든 블록의 상태 갱신 (PID 적분기, 전동기 RK4 등)
 * 연결되지 않은 입력은 0 으로 본다 (전동기 TL 입력은 블록 속성값 사용).
 */
(function (root) {
  "use strict";
  const RPM = 60 / (2 * Math.PI);
  const clip = (x, lo, hi) => Math.min(Math.max(x, lo), hi);
  const num = (v, d) => (v === undefined || !isFinite(v) ? d : v);

  // ---------------- 블록 정의 ----------------
  // params: {키: {label, type: number|bool|select|text, v: 기본값, options, unit, help}}
  const DEF = {
    const: {
      cat: "신호원", name: "상수", ins: [], outs: ["y"], ft: true,
      params: { value: { label: "값", type: "number", v: 1000 },
                rpm: { label: "rpm 으로 입력 (rad/s 로 출력)", type: "bool", v: false } },
      desc: "일정한 값을 냅니다. 실행 중에 값을 바꾸면 그 순간 계단 입력이 됩니다.",
      text: (b) => `${b.p.value}${b.p.rpm ? " rpm" : ""}`,
      out: (b) => [b.p.value * (b.p.rpm ? 1 / RPM : 1)],
    },
    step: {
      cat: "신호원", name: "계단", ins: [], outs: ["y"], ft: true,
      params: { t0: { label: "변경 시각", type: "number", v: 1.0, unit: "s" },
                v0: { label: "이전 값", type: "number", v: 0 },
                v1: { label: "이후 값", type: "number", v: 30 },
                rpm: { label: "rpm 으로 입력", type: "bool", v: false } },
      desc: "지정 시각에 값이 바뀝니다 (재시작하면 다시 0 초부터).",
      text: (b) => `${b.p.v0}→${b.p.v1} @${b.p.t0}s`,
      out: (b, s, u, t) => [(t >= b.p.t0 ? b.p.v1 : b.p.v0) * (b.p.rpm ? 1 / RPM : 1)],
    },
    square: {
      cat: "신호원", name: "사각파", ins: [], outs: ["y"], ft: true,
      params: { amp: { label: "진폭", type: "number", v: 500 },
                period: { label: "주기", type: "number", v: 1.0, unit: "s" },
                offset: { label: "오프셋", type: "number", v: 500 },
                rpm: { label: "rpm 으로 입력", type: "bool", v: false } },
      desc: "계단 응답을 반복해서 보기 좋은 사각파입니다.",
      text: (b) => `±${b.p.amp} (T=${b.p.period}s)`,
      out: (b, s, u, t) => {
        const ph = (t % b.p.period) / b.p.period;
        return [(b.p.offset + (ph < 0.5 ? b.p.amp : -b.p.amp)) * (b.p.rpm ? 1 / RPM : 1)];
      },
    },
    sine: {
      cat: "신호원", name: "사인파", ins: [], outs: ["y"], ft: true,
      params: { amp: { label: "진폭", type: "number", v: 300 },
                freq: { label: "주파수", type: "number", v: 2, unit: "Hz" },
                offset: { label: "오프셋", type: "number", v: 500 },
                rpm: { label: "rpm 으로 입력", type: "bool", v: false } },
      desc: "추종 성능(위상 지연)을 보기 좋습니다.",
      text: (b) => `${b.p.amp}·sin(2π·${b.p.freq}t)`,
      out: (b, s, u, t) => [(b.p.offset + b.p.amp * Math.sin(2 * Math.PI * b.p.freq * t)) * (b.p.rpm ? 1 / RPM : 1)],
    },
    sum: {
      cat: "연산", name: "합산점 Σ", ins: (b) => [...b.p.signs].map((c, i) => `${c}${i + 1}`), outs: ["y"], ft: true,
      params: { signs: { label: "부호 (예: +-, ++, +-+)", type: "text", v: "+-" } },
      desc: "입력에 부호를 붙여 더합니다. 오차 = 지령 − 피드백은 \"+-\".",
      text: (b) => b.p.signs,
      out: (b, s, u) => [[...b.p.signs].reduce((a, c, i) => a + (c === "-" ? -1 : 1) * num(u[i], 0), 0)],
    },
    gain: {
      cat: "연산", name: "게인 K", ins: ["u"], outs: ["y"], ft: true,
      params: { K: { label: "K", type: "number", v: 1 } },
      desc: "y = K·u. 역기전력 피드포워드(K = Kφ), 단위 변환 등에 씁니다.",
      text: (b) => `K = ${+(+b.p.K).toPrecision(4)}`,
      out: (b, s, u) => [b.p.K * num(u[0], 0)],
    },
    limit: {
      cat: "연산", name: "리미터", ins: ["u"], outs: ["y"], ft: true,
      params: { lo: { label: "하한", type: "number", v: -40 }, hi: { label: "상한", type: "number", v: 40 } },
      desc: "출력을 [하한, 상한] 으로 자릅니다 (전류 제한, 속도 지령 제한 등).",
      text: (b) => `[${b.p.lo}, ${b.p.hi}]`,
      out: (b, s, u) => [clip(num(u[0], 0), b.p.lo, b.p.hi)],
    },
    integ: {
      cat: "연산", name: "적분기 1/s", ins: ["u"], outs: ["y"], ft: false,
      params: { k: { label: "게인 k (y = k∫u dt)", type: "number", v: 1 }, x0: { label: "초기값", type: "number", v: 0 } },
      desc: "y = k∫u dt. 속도를 적분하면 회전각(위치) [rad] 이 됩니다.",
      text: (b) => `${b.p.k}/s`,
      init: (b) => ({ x: +b.p.x0 }),
      out: (b, s) => [s.x],
      update: (b, s, u, h) => { s.x += b.p.k * num(u[0], 0) * h; },
    },
    lpf: {
      cat: "연산", name: "1차 지연 필터", ins: ["u"], outs: ["y"], ft: false,
      params: { tau: { label: "시정수 τ", type: "number", v: 0.005, unit: "s" } },
      desc: "1/(τs + 1). 센서 필터나 지령 완화(램프 대신)에 씁니다.",
      text: (b) => `τ = ${b.p.tau} s`,
      init: () => ({ y: 0 }),
      out: (b, s) => [s.y],
      update: (b, s, u, h) => { const tau = Math.max(b.p.tau, h); s.y += h / tau * (num(u[0], 0) - s.y); },
    },
    pid: {
      cat: "제어기", name: "PID 제어기", ins: ["e"], outs: ["u"], ft: true,
      params: {
        mode: { label: "종류", type: "select", v: "PI", options: ["P", "PI", "PID"] },
        Kp: { label: "Kp", type: "number", v: 1 }, Ki: { label: "Ki", type: "number", v: 10 },
        Kd: { label: "Kd", type: "number", v: 0 },
        N: { label: "미분 필터 N", type: "number", v: 1000, unit: "rad/s", help: "미분항 D(s) = s/(1 + s/N)" },
        lim: { label: "출력 제한 사용", type: "bool", v: true },
        lo: { label: "출력 하한", type: "number", v: -40 }, hi: { label: "출력 상한", type: "number", v: 40 },
        aw: { label: "안티와인드업", type: "bool", v: true },
      },
      desc: "u = Kp·e + Ki∫e dt + Kd·de/dt. 종류를 P 로 두면 적분·미분 항을 쓰지 않습니다. " +
            "출력 제한이 걸린 동안 안티와인드업이 적분을 멈춥니다.",
      text: (b) => {
        const f = (x) => +(+x).toPrecision(3);
        let t = `Kp=${f(b.p.Kp)}`;
        if (b.p.mode !== "P") t += ` Ki=${f(b.p.Ki)}`;
        if (b.p.mode === "PID") t += ` Kd=${f(b.p.Kd)}`;
        return t + (b.p.lim ? `  [${f(b.p.lo)}, ${f(b.p.hi)}]` : "");
      },
      title: (b) => `${b.p.mode} 제어기`,
      init: () => ({ xi: 0, z: 0, sat: 0, e: 0 }),
      out: (b, s, u) => {
        const e = num(u[0], 0), p = b.p;
        const d = p.mode === "PID" ? p.Kd * p.N * (e - s.z) : 0;
        const ui = p.mode === "P" ? 0 : s.xi;
        const uu = p.Kp * e + ui + d;
        const y = p.lim ? clip(uu, p.lo, p.hi) : uu;
        s.sat = uu > y ? 1 : uu < y ? -1 : 0; s.e = e;
        return [y];
      },
      update: (b, s, u, h) => {
        const p = b.p, e = s.e;
        if (p.mode !== "P") {
          const blocked = p.aw && p.lim && ((s.sat > 0 && e > 0) || (s.sat < 0 && e < 0));
          if (!blocked) s.xi += p.Ki * e * h;
        } else s.xi = 0;
        if (p.mode === "PID") s.z += h * p.N * (e - s.z);
      },
    },
    chopper: {
      cat: "전력·전동기", name: "초퍼", ins: ["v*"], outs: ["va"], ft: true,
      params: { Vdc: { label: "직류 전원 Vdc", type: "number", v: 220, unit: "V" },
                quad: { label: "종류", type: "select", v: "4상한", options: ["4상한", "1상한"] } },
      desc: "평균값 모델: va = d·Vdc. 4상한은 −Vdc ~ +Vdc, 1상한은 0 ~ Vdc 이고 전류도 한 방향(Ia ≥ 0)만 흐릅니다.",
      text: (b) => `${b.p.quad}, ${b.p.Vdc} V`,
      out: (b, s, u) => [clip(num(u[0], 0), b.p.quad === "1상한" ? 0 : -b.p.Vdc, b.p.Vdc)],
    },
    motor: {
      cat: "전력·전동기", name: "DC 전동기", ins: ["va", "TL"], outs: ["ω", "n", "Ia", "E", "Te"], ft: false,
      outUnits: ["rad/s", "rpm", "A", "V", "N·m"],
      params: {
        kind: { label: "종류", type: "select", v: "", options: [] },   // 실행 환경에서 채움
        TL: { label: "부하 토크 (TL 입력이 없을 때)", type: "number", v: 0, unit: "N·m" },
        friction: { label: "마찰형 부하 (회전 반대 방향)", type: "bool", v: true },
      },
      desc: "파라미터 설정의 값으로 만든 전동기입니다. 출력: ω [rad/s], n [rpm], Ia [A], E [V], Te [N·m]. " +
            "분권·복권은 계자도 입력 전압 va 에 연결되어 있다고 봅니다.",
      text: (b) => `${b.p.kind}  TL=${b.p.TL}`,
      init: (b, env) => {
        const m = env.motors[b.p.kind] || env.motors[env.defaultMotor];
        const motor = new DCEngine.Motor(m.p, m.type, m.sigma);
        const sim = new DCEngine.MotorSim(motor, { V: m.V, Vf: m.Vf, Rfx: m.Rfx, TL: 0, Rst: 0, friction: true });
        sim.reset(); sim.set({ V: 0 });
        return { sim, kind: b.p.kind };
      },
      out: (b, s) => { const o = s.sim.out(); return [o.w, o.w * RPM, o.ia, o.E, o.Te]; },
      update: (b, s, u, h, t, env, ctx) => {
        const TL = u[1] === undefined ? +b.p.TL : u[1];
        s.sim.set({ V: num(u[0], 0), TL, friction: !!b.p.friction });
        s.sim.advance(h);
        if (ctx.diodeFor(b) && s.sim.s[0] < 0) s.sim.s[0] = 0;   // 1상한 초퍼: 전류 단방향
      },
    },
    bldc: {
      cat: "전력·전동기", name: "BLDC 전동기", ins: ["v*", "TL"], outs: ["ω", "n", "iT", "ia", "ib", "ic", "Te"], ft: false,
      outUnits: ["rad/s", "rpm", "A", "A", "A", "A", "N·m"],
      params: {
        TL: { label: "부하 토크 (TL 입력이 없을 때)", type: "number", v: 0, unit: "N·m" },
        friction: { label: "마찰형 부하 (회전 반대 방향)", type: "bool", v: true },
        hall: { label: "홀 센서 위치 오차", type: "number", v: 0, unit: "° 전기각" },
      },
      desc: "6스텝 인버터(홀 센서 120° 통전, 평균값 PWM)가 들어 있는 BLDC 전동기입니다. 입력 v* [V] 는 " +
            "−Vdc ~ +Vdc 로 잘리고 듀티 d = v*/Vdc 가 됩니다. 출력: ω [rad/s], n [rpm], " +
            "iT = Te/(2ke) 토크 전류 [A], 상전류 ia·ib·ic [A], Te [N·m]. 파라미터는 BLDC 시뮬레이터 페이지 값입니다.",
      text: (b) => `6스텝  TL=${b.p.TL}${+b.p.hall ? `  홀 ${b.p.hall}°` : ""}`,
      init: (b, env) => {
        if (!env.bldc || typeof BLDCEngine === "undefined") throw new Error("BLDC 파라미터가 없습니다");
        return { sim: new BLDCEngine.BLDCSim(env.bldc.p) };
      },
      out: (b, s) => { const o = s.sim.out(); return [o.w, o.w * RPM, o.iT, o.ia, o.ib, o.ic, o.Te]; },
      update: (b, s, u, h, t, env) => {
        const Vdc = env.bldc.p.Vdc, TL = u[1] === undefined ? +b.p.TL : u[1];
        s.sim.set({ duty: clip(num(u[0], 0) / Vdc, -1, 1), TL, friction: !!b.p.friction, hallOffset: (+b.p.hall || 0) * Math.PI / 180 });
        const n = Math.max(1, Math.ceil(h / 1e-5 - 1e-9));   // 인버터 정류를 잡도록 10 µs 이하로 나눔
        for (let i = 0; i < n; i++) s.sim.step(h / n);
      },
    },
    im: {
      cat: "전력·전동기", name: "유도전동기",
      ins: (b) => (b.p.mode === "V/f" ? ["f*", "V*", "TL"] : ["id*", "iq*", "TL"]),
      outs: ["ω", "n", "Te", "Is", "id", "iq", "f"], ft: false,
      outUnits: ["rad/s", "rpm", "N·m", "A", "A", "A", "Hz"],
      params: {
        mode: { label: "입력 방식", type: "select", v: "벡터", options: ["벡터", "V/f"],
                help: "벡터: id*·iq* [A] 를 받아 내부 전류 제어기(회전자 자속 기준)가 전압을 만듦. V/f: 주파수 f* [Hz] 와 선간 전압 V* [V] 로 바로 운전." },
        TL: { label: "부하 토크 (TL 입력이 없을 때)", type: "number", v: 0, unit: "N·m" },
        friction: { label: "마찰형 부하 (회전 반대 방향)", type: "bool", v: true },
        wci: { label: "내부 전류 제어 대역폭 ωci", type: "number", v: 1500, unit: "rad/s" },
      },
      desc: "인버터가 들어 있는 3상 농형 유도전동기입니다 (파라미터는 유도전동기 시뮬레이터 페이지 값). " +
            "벡터 방식: 간접 벡터 제어로 id*(자속분)·iq*(토크분) 전류를 따라가게 하고, 바깥 속도 루프는 블록으로 짭니다. " +
            "V/f 방식: 인버터 출력 주파수 f* 와 전압 V* 를 직접 줍니다. 출력: ω [rad/s], n [rpm], Te, 상전류 실효값 Is, id, iq, 인버터 주파수 f.",
      text: (b) => `${b.p.mode} 입력  TL=${b.p.TL}`,
      title: () => "유도전동기",
      init: (b, env) => {
        if (!env.im || typeof ACEngine === "undefined") throw new Error("유도전동기 파라미터가 없습니다");
        const m = new ACEngine.IMSim(env.im.p); m.set({ mode: "ext" });
        return { m, th: 0, xd: 0, xq: 0, f: 0, id: 0, iq: 0 };
      },
      out: (b, s) => { const o = s.m.out(); return [o.w, o.w * RPM, o.Te, o.Is, s.id, s.iq, s.f]; },
      update: (b, s, u, h, t, env) => {
        const P = env.im.p, m = s.m, pp = m.pp, Vmax = Math.sqrt(2 / 3) * P.V, o = m.out();
        let va, vb;
        if (b.p.mode === "V/f") {
          const f = num(u[0], 0), V = clip(num(u[1], 0), 0, P.V);
          s.th += 2 * Math.PI * f * h; s.f = f;
          va = Math.sqrt(2 / 3) * V * Math.cos(s.th); vb = Math.sqrt(2 / 3) * V * Math.sin(s.th);
          s.id = o.id; s.iq = o.iq;
        } else {
          const idr = Math.max(num(u[0], 0), 1e-3), iqr = num(u[1], 0);
          const tr = m.Lr / P.Rr, sig = m.Ls - P.Lm * P.Lm / m.Lr, Rsig = P.Rs + P.Rr * (P.Lm / m.Lr) ** 2;
          const we = pp * o.w + iqr / (tr * idr);
          s.th += we * h; s.f = we / (2 * Math.PI);
          const c = Math.cos(s.th), sn = Math.sin(s.th);
          const id = o.isa * c + o.isb * sn, iq = -o.isa * sn + o.isb * c;
          const kp = b.p.wci * sig, ki = b.p.wci * Rsig;
          const ed = idr - id, eq = iqr - iq;
          let vd = kp * ed + s.xd - we * sig * iq, vq = kp * eq + s.xq + we * (sig * id + P.Lm * P.Lm / m.Lr * idr);
          const vm = Math.hypot(vd, vq);
          if (vm > Vmax) { vd *= Vmax / vm; vq *= Vmax / vm; } else { s.xd += ki * ed * h; s.xq += ki * eq * h; }
          va = vd * c - vq * sn; vb = vd * sn + vq * c; s.id = id; s.iq = iq;
        }
        const TL = u[2] === undefined ? +b.p.TL : u[2];
        m.set({ va, vb, TL, friction: !!b.p.friction });
        const n = Math.max(1, Math.ceil(h / 5e-5 - 1e-9));
        for (let i = 0; i < n; i++) m.step(h / n);
      },
    },
    pmsm: {
      cat: "전력·전동기", name: "PMSM", ins: ["id*", "iq*", "TL"], outs: ["ω", "n", "Te", "id", "iq", "|v|"], ft: false,
      outUnits: ["rad/s", "rpm", "N·m", "A", "A", "V"],
      params: {
        TL: { label: "부하 토크 (TL 입력이 없을 때)", type: "number", v: 0, unit: "N·m" },
        friction: { label: "마찰형 부하 (회전 반대 방향)", type: "bool", v: true },
        wci: { label: "내부 전류 제어 대역폭 ωci", type: "number", v: 2000, unit: "rad/s" },
        ff: { label: "비간섭 보상 (−ωLq·iq, ω(Ld·id + λf))", type: "bool", v: true },
      },
      desc: "인버터와 dq 전류 제어기가 들어 있는 PMSM 입니다 (파라미터는 PMSM 시뮬레이터 페이지 값). " +
            "id*·iq* [A] 를 넣으면 내부 전류 PI 가 따라가게 하고, 전압은 Vdc/√3 원으로 제한됩니다. " +
            "출력: ω [rad/s], n [rpm], Te, id, iq, 전압 크기 |v| [V]. 속도 루프·MTPA·약계자는 블록으로 짜 보세요.",
      text: (b) => `dq 전류 입력  TL=${b.p.TL}`,
      init: (b, env) => {
        if (!env.pmsm || typeof ACEngine === "undefined") throw new Error("PMSM 파라미터가 없습니다");
        return { m: new ACEngine.PMSMSim(env.pmsm.p), xd: 0, xq: 0, v: 0 };
      },
      out: (b, s) => { const o = s.m.out(); return [o.w, o.w * RPM, o.Te, o.id, o.iq, s.v]; },
      update: (b, s, u, h, t, env) => {
        const P = env.pmsm.p, m = s.m, o = m.out(), we = m.pp * o.w, Vmax = P.Vdc / Math.sqrt(3);
        const ed = num(u[0], 0) - o.id, eq = num(u[1], 0) - o.iq;
        let vd = b.p.wci * P.Ld * ed + s.xd + (b.p.ff ? -we * P.Lq * o.iq : 0);
        let vq = b.p.wci * P.Lq * eq + s.xq + (b.p.ff ? we * (P.Ld * o.id + P.lam) : 0);
        const vm = Math.hypot(vd, vq);
        if (vm > Vmax) { vd *= Vmax / vm; vq *= Vmax / vm; } else { s.xd += b.p.wci * P.Rs * ed * h; s.xq += b.p.wci * P.Rs * eq * h; }
        s.v = Math.hypot(vd, vq);
        const TL = u[2] === undefined ? +b.p.TL : u[2];
        m.set({ vd, vq, TL, friction: !!b.p.friction });
        const n = Math.max(1, Math.ceil(h / 2e-5 - 1e-9));
        for (let i = 0; i < n; i++) m.step(h / n);
      },
    },
    scope: {
      cat: "관측", name: "스코프", ins: ["a", "b", "c"], outs: [], ft: true, sink: true,
      params: { name: { label: "그래프 제목", type: "text", v: "스코프" },
                rpm: { label: "rad/s 신호를 rpm 으로 표시 (×60/2π)", type: "bool", v: false } },
      desc: "연결한 신호(최대 3개)를 흘러가는 그래프로 보여줍니다.",
      text: (b) => b.p.name,
      out: () => [],
    },
    display: {
      cat: "관측", name: "숫자 표시", ins: ["u"], outs: [], ft: true, sink: true,
      params: { unit: { label: "단위 표시", type: "text", v: "" } },
      desc: "입력 값을 숫자로 보여줍니다 (오차 확인 등).",
      text: () => "",
      out: () => [],
    },
  };
  const insOf = (b) => (typeof DEF[b.type].ins === "function" ? DEF[b.type].ins(b) : DEF[b.type].ins);
  const outsOf = (b) => DEF[b.type].outs;
  const titleOf = (b) => b.name || (DEF[b.type].title ? DEF[b.type].title(b) : DEF[b.type].name);

  // ---------------- 다이어그램 ----------------
  class Diagram {
    constructor() { this.blocks = []; this.wires = []; this.nid = 1; this.version = 0; }
    add(type, x, y, p, name) {
      const d = DEF[type], b = { id: this.nid++, type, x, y, p: {}, name: name || "" };
      for (const [k, s] of Object.entries(d.params)) b.p[k] = s.v;
      Object.assign(b.p, p || {});
      this.blocks.push(b); this.version++;
      return b;
    }
    get(id) { return this.blocks.find((b) => b.id === id); }
    remove(id) {
      this.blocks = this.blocks.filter((b) => b.id !== id);
      this.wires = this.wires.filter((w) => w.from.b !== id && w.to.b !== id); this.version++;
    }
    connect(fb, fp, tb, tp) {
      this.wires = this.wires.filter((w) => !(w.to.b === tb && w.to.p === tp));  // 입력 하나에 선 하나
      this.wires.push({ from: { b: fb, p: fp }, to: { b: tb, p: tp } }); this.version++;
    }
    disconnect(i) { this.wires.splice(i, 1); this.version++; }
    clear() { this.blocks = []; this.wires = []; this.version++; }
    toJSON() { return { blocks: this.blocks, wires: this.wires, nid: this.nid }; }
    load(o) {
      this.blocks = o.blocks.filter((b) => DEF[b.type]).map((b) => {
        const d = DEF[b.type], p = {};
        for (const [k, s] of Object.entries(d.params)) p[k] = s.v;
        return Object.assign({}, b, { p: Object.assign(p, b.p) });
      });
      const ids = new Set(this.blocks.map((b) => b.id));
      this.wires = o.wires.filter((w) => ids.has(w.from.b) && ids.has(w.to.b));
      this.nid = Math.max(o.nid || 1, ...this.blocks.map((b) => b.id + 1), 1); this.version++;
    }
  }

  // ---------------- 실행기 ----------------
  class Runner {
    constructor(dg, env) { this.dg = dg; this.env = env; this.reset(); }
    reset() { this.t = 0; this.st = {}; this.out = {}; this.compiled = -1; this.acc = 0; }
    compile() {
      const dg = this.dg;
      this.inWire = {};   // `${b}:${p}` → wire
      for (const w of dg.wires) this.inWire[`${w.to.b}:${w.to.p}`] = w;
      // 새 블록 상태 초기화, 지워진 블록 상태 제거, 전동기 종류가 바뀌면 다시 초기화
      const live = new Set(dg.blocks.map((b) => b.id));
      for (const id of Object.keys(this.st)) if (!live.has(+id)) delete this.st[id];
      for (const b of dg.blocks) {
        const d = DEF[b.type];
        const stale = b.type === "motor" && this.st[b.id] && this.st[b.id].kind !== b.p.kind;
        if (!(b.id in this.st) || stale) this.st[b.id] = d.init ? d.init(b, this.env) : {};
        if (!(b.id in this.out)) this.out[b.id] = outsOf(b).map(() => 0);
      }
      // 직결(feedthrough) 블록 위상 정렬
      const ft = dg.blocks.filter((b) => DEF[b.type].ft);
      const ftIds = new Set(ft.map((b) => b.id));
      const indeg = {}, adj = {};
      ft.forEach((b) => { indeg[b.id] = 0; adj[b.id] = []; });
      for (const w of dg.wires) if (ftIds.has(w.from.b) && ftIds.has(w.to.b)) { adj[w.from.b].push(w.to.b); indeg[w.to.b]++; }
      const q = ft.filter((b) => indeg[b.id] === 0).map((b) => b.id), order = [];
      while (q.length) { const id = q.shift(); order.push(id); for (const n of adj[id]) if (--indeg[n] === 0) q.push(n); }
      this.loopIds = ft.filter((b) => !order.includes(b.id)).map((b) => b.id);
      this.order = order.map((id) => dg.get(id));
      this.states = dg.blocks.filter((b) => !DEF[b.type].ft);
      // 1상한 초퍼가 전압을 주는 전동기 (전류 단방향)
      this.diode = new Set();
      for (const b of dg.blocks) if (b.type === "motor") {
        const w = this.inWire[`${b.id}:0`];
        const src = w && dg.get(w.from.b);
        if (src && src.type === "chopper" && src.p.quad === "1상한") this.diode.add(b.id);
      }
      this.compiled = dg.version;
    }
    inputs(b) {
      const n = insOf(b).length, u = new Array(n);
      for (let i = 0; i < n; i++) {
        const w = this.inWire[`${b.id}:${i}`];
        u[i] = w ? (this.out[w.from.b] || [])[w.from.p] : undefined;
      }
      return u;
    }
    step(h) {
      if (this.compiled !== this.dg.version) this.compile();
      const env = this.env, t = this.t;
      for (const b of this.states) this.out[b.id] = DEF[b.type].out(b, this.st[b.id], null, t, env);
      const U = {};
      for (const b of this.order) { const u = this.inputs(b); U[b.id] = u; this.out[b.id] = DEF[b.type].out(b, this.st[b.id], u, t, env); }
      for (const id of this.loopIds) this.out[id] = outsOf(this.dg.get(id)).map(() => 0);
      const ctx = { diodeFor: (b) => this.diode.has(b.id) };
      for (const b of this.dg.blocks) {
        const d = DEF[b.type];
        if (d.update) d.update(b, this.st[b.id], U[b.id] || this.inputs(b), h, t, env, ctx);
      }
      this.t += h;
    }
    advance(dt, h) {
      this.acc += dt;
      while (this.acc >= h) { this.acc -= h; this.step(h); }
    }
    /** 오류·경고 목록 */
    check() {
      if (this.compiled !== this.dg.version) this.compile();
      const msgs = [];
      if (this.loopIds.length) msgs.push("⚠️ 대수 루프: " + this.loopIds.map((id) => titleOf(this.dg.get(id))).join(", ") +
        " 가 적분 요소 없이 고리를 이룹니다. 그 블록들의 출력은 0 으로 계산합니다.");
      for (const b of this.dg.blocks) if (["motor", "bldc", "im", "pmsm"].includes(b.type) && !this.inWire[`${b.id}:0`])
        msgs.push(`ℹ️ ${titleOf(b)} 의 ${insOf(b)[0]} 입력이 연결되지 않아 0 으로 계산합니다.`);
      return msgs;
    }
  }

  // ---------------- 템플릿 ----------------
  function templates(env) {
    const P = env.ctrl, K = P.K, Il = P.Ilim, V = P.V;
    const g = DCEngine.recommendedGains(P, K, 1000, 50);
    const r4 = (x) => +x.toPrecision(4);
    const mk = (dg) => ({
      add: (...a) => dg.add(...a),
      w: (a, ap, b, bp) => dg.connect(a.id, ap, b.id, bp),
    });
    const T = {};
    const c = (i) => 20 + 140 * i;       // 열 위치
    T["속도·전류 이중 루프 (PI-PI) + E 피드포워드"] = (dg) => {
      const m = mk(dg);
      const ref = m.add("const", c(0), 40, { value: 1000, rpm: true }, "속도 지령 ω*");
      const s1 = m.add("sum", c(1), 40, { signs: "+-" }, "속도 오차");
      const pw = m.add("pid", c(2), 40, { mode: "PI", Kp: r4(g.Kpw), Ki: r4(g.Kiw), lo: -Il, hi: Il }, "속도 PI → Ia*");
      const s2 = m.add("sum", c(3), 40, { signs: "+-" }, "전류 오차");
      const pi = m.add("pid", c(4), 40, { mode: "PI", Kp: r4(g.Kpi), Ki: r4(g.Kii), lo: -V, hi: V }, "전류 PI");
      const s3 = m.add("sum", c(5), 40, { signs: "++" }, "+ E 보상");
      const ch = m.add("chopper", c(6), 40, { Vdc: V });
      const mo = m.add("motor", c(6), 185, { kind: env.defaultMotor }, "전동기");
      const ff = m.add("gain", c(4), 215, { K: r4(K) }, "E 피드포워드 Kφ");
      const tl = m.add("step", c(4), 330, { t0: 1.0, v0: 0, v1: Math.round(P.TL) }, "부하 토크 TL");
      const sc1 = m.add("scope", c(0), 330, { name: "속도", rpm: true });
      const sc2 = m.add("scope", c(1), 330, { name: "전류 [A]" });
      const sc3 = m.add("scope", c(2), 330, { name: "전압 [V]" });
      m.w(ref, 0, s1, 0); m.w(s1, 0, pw, 0); m.w(pw, 0, s2, 0); m.w(s2, 0, pi, 0); m.w(pi, 0, s3, 0);
      m.w(s3, 0, ch, 0); m.w(ch, 0, mo, 0); m.w(mo, 0, s1, 1); m.w(mo, 2, s2, 1); m.w(mo, 0, ff, 0); m.w(ff, 0, s3, 1);
      m.w(tl, 0, mo, 1);
      m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1); m.w(pw, 0, sc2, 0); m.w(mo, 2, sc2, 1); m.w(ch, 0, sc3, 0); m.w(mo, 3, sc3, 1);
    };
    T["전류 제어만 (전류 PI)"] = (dg) => {
      const m = mk(dg);
      const ref = m.add("square", c(0), 40, { amp: Math.round(0.5 * Il), period: 0.2, offset: 0 }, "전류 지령 Ia*");
      const s = m.add("sum", c(1), 40, { signs: "+-" }, "전류 오차");
      const pi = m.add("pid", c(2), 40, { mode: "PI", Kp: r4(g.Kpi), Ki: r4(g.Kii), lo: -V, hi: V }, "전류 PI");
      const ch = m.add("chopper", c(3), 40, { Vdc: V });
      const mo = m.add("motor", c(4), 40, { kind: env.defaultMotor }, "전동기");
      const sc1 = m.add("scope", c(1), 250, { name: "전류 [A]" });
      const sc2 = m.add("scope", c(3), 250, { name: "속도", rpm: true });
      const sc3 = m.add("scope", c(5), 250, { name: "전압 [V]" });
      m.w(ref, 0, s, 0); m.w(s, 0, pi, 0); m.w(pi, 0, ch, 0); m.w(ch, 0, mo, 0); m.w(mo, 2, s, 1);
      m.w(ref, 0, sc1, 0); m.w(mo, 2, sc1, 1); m.w(mo, 0, sc2, 0); m.w(ch, 0, sc3, 0); m.w(mo, 3, sc3, 1);
    };
    T["속도 제어만 (속도 PI → 전압 직접)"] = (dg) => {
      const m = mk(dg);
      const ref = m.add("square", c(0), 40, { amp: 400, period: 1.0, offset: 600, rpm: true }, "속도 지령 ω*");
      const s = m.add("sum", c(1), 40, { signs: "+-" }, "속도 오차");
      const pv = m.add("pid", c(2), 40, { mode: "PI", Kp: 3, Ki: 30, lo: -V, hi: V }, "속도 PI → 전압");
      const ch = m.add("chopper", c(3), 40, { Vdc: V });
      const mo = m.add("motor", c(4), 40, { kind: env.defaultMotor }, "전동기");
      const sc1 = m.add("scope", c(1), 250, { name: "속도", rpm: true });
      const sc2 = m.add("scope", c(3), 250, { name: "전류 [A] (제한 없음!)" });
      m.w(ref, 0, s, 0); m.w(s, 0, pv, 0); m.w(pv, 0, ch, 0); m.w(ch, 0, mo, 0); m.w(mo, 0, s, 1);
      m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1); m.w(mo, 2, sc2, 0);
    };
    T["P 제어 속도 루프 (정상상태 오차 확인)"] = (dg) => {
      const m = mk(dg);
      const ref = m.add("const", c(0), 40, { value: 1000, rpm: true }, "속도 지령 ω*");
      const s = m.add("sum", c(1), 40, { signs: "+-" }, "속도 오차");
      const pw = m.add("pid", c(2), 40, { mode: "P", Kp: r4(g.Kpw), lo: -Il, hi: Il }, "속도 P → Ia*");
      const s2 = m.add("sum", c(3), 40, { signs: "+-" }, "전류 오차");
      const pi = m.add("pid", c(4), 40, { mode: "PI", Kp: r4(g.Kpi), Ki: r4(g.Kii), lo: -V, hi: V }, "전류 PI");
      const ch = m.add("chopper", c(5), 40, { Vdc: V });
      const mo = m.add("motor", c(5), 185, { kind: env.defaultMotor, TL: Math.round(P.TL) }, "전동기");
      const gr = m.add("gain", c(1), 215, { K: r4(RPM) }, "rad/s → rpm");
      const dp = m.add("display", c(2), 215, { unit: "rpm" }, "속도 오차");
      const sc1 = m.add("scope", c(0), 360, { name: "속도", rpm: true });
      const sc2 = m.add("scope", c(2), 360, { name: "전류 [A]" });
      m.w(ref, 0, s, 0); m.w(s, 0, pw, 0); m.w(pw, 0, s2, 0); m.w(s2, 0, pi, 0); m.w(pi, 0, ch, 0); m.w(ch, 0, mo, 0);
      m.w(mo, 0, s, 1); m.w(mo, 2, s2, 1); m.w(s, 0, gr, 0); m.w(gr, 0, dp, 0);
      m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1); m.w(pw, 0, sc2, 0); m.w(mo, 2, sc2, 1);
    };
    T["개루프 (V = Kφ·ω*)"] = (dg) => {
      const m = mk(dg);
      const ref = m.add("const", c(0), 40, { value: 1000, rpm: true }, "속도 지령 ω*");
      const k = m.add("gain", c(1), 40, { K: r4(K) }, "Kφ");
      const ch = m.add("chopper", c(2), 40, { Vdc: V });
      const mo = m.add("motor", c(3), 40, { kind: env.defaultMotor }, "전동기");
      const sc1 = m.add("scope", c(1), 250, { name: "속도", rpm: true });
      const sc2 = m.add("scope", c(3), 250, { name: "전류 [A]" });
      m.w(ref, 0, k, 0); m.w(k, 0, ch, 0); m.w(ch, 0, mo, 0); m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1); m.w(mo, 2, sc2, 0);
    };
    T["위치 제어 (위치 P → 속도 PI → 전류 PI)"] = (dg) => {
      const m = mk(dg);
      const ref = m.add("square", c(0), 40, { amp: 3.1416, period: 1.5, offset: 0 }, "위치 지령 θ* [rad]");
      const s0 = m.add("sum", c(1), 40, { signs: "+-" }, "위치 오차");
      const pp = m.add("pid", c(2), 40, { mode: "P", Kp: 20, lim: false }, "위치 P → ω*");
      const lw = m.add("limit", c(3), 40, { lo: -100, hi: 100 }, "속도 지령 제한");
      const s1 = m.add("sum", c(4), 40, { signs: "+-" }, "속도 오차");
      const pw = m.add("pid", c(5), 40, { mode: "PI", Kp: r4(g.Kpw), Ki: r4(g.Kiw), lo: -Il, hi: Il }, "속도 PI → Ia*");
      const s2 = m.add("sum", c(6), 40, { signs: "+-" }, "전류 오차");
      const pi = m.add("pid", c(7), 40, { mode: "PI", Kp: r4(g.Kpi), Ki: r4(g.Kii), lo: -V, hi: V }, "전류 PI");
      const ch = m.add("chopper", c(7), 160, { Vdc: V });
      const mo = m.add("motor", c(7), 270, { kind: env.defaultMotor }, "전동기");
      const it = m.add("integ", c(4), 300, {}, "적분 → 위치 θ");
      const sc1 = m.add("scope", c(0), 420, { name: "위치 [rad]" });
      const sc2 = m.add("scope", c(2), 420, { name: "속도 [rad/s]" });
      const sc3 = m.add("scope", c(4), 440, { name: "전류 [A]" });
      m.w(ref, 0, s0, 0); m.w(s0, 0, pp, 0); m.w(pp, 0, lw, 0); m.w(lw, 0, s1, 0); m.w(s1, 0, pw, 0); m.w(pw, 0, s2, 0);
      m.w(s2, 0, pi, 0); m.w(pi, 0, ch, 0); m.w(ch, 0, mo, 0);
      m.w(mo, 0, it, 0); m.w(it, 0, s0, 1); m.w(mo, 0, s1, 1); m.w(mo, 2, s2, 1);
      m.w(ref, 0, sc1, 0); m.w(it, 0, sc1, 1); m.w(lw, 0, sc2, 0); m.w(mo, 0, sc2, 1); m.w(pw, 0, sc3, 0); m.w(mo, 2, sc3, 1);
    };
    if (env.bldc) {
      const B = env.bldc, bp = B.p, KB = 2 * bp.ke, gb = BLDCEngine.recommendedGains(bp, 3000, 150);
      const IlB = B.Ilim, VB = bp.Vdc, wRpm = Math.round(0.6 * VB / KB * RPM / 100) * 100;
      T["BLDC: 속도·전류 이중 루프 (PI-PI) + E 피드포워드"] = (dg) => {
        const m = mk(dg);
        const ref = m.add("const", c(0), 40, { value: wRpm, rpm: true }, "속도 지령 ω*");
        const s1 = m.add("sum", c(1), 40, { signs: "+-" }, "속도 오차");
        const pw = m.add("pid", c(2), 40, { mode: "PI", Kp: r4(gb.Kpw), Ki: r4(gb.Kiw), lo: -IlB, hi: IlB }, "속도 PI → I*");
        const s2 = m.add("sum", c(3), 40, { signs: "+-" }, "전류 오차");
        const pi = m.add("pid", c(4), 40, { mode: "PI", Kp: r4(gb.Kpi), Ki: r4(gb.Kii), lo: -VB, hi: VB }, "전류 PI");
        const s3 = m.add("sum", c(5), 40, { signs: "++" }, "+ E 보상");
        const mo = m.add("bldc", c(6), 40, {}, "BLDC");
        const ff = m.add("gain", c(4), 230, { K: r4(KB) }, "E 피드포워드 2ke");
        const tl = m.add("step", c(5), 330, { t0: 0.1, v0: 0, v1: +(+B.TL).toPrecision(3) }, "부하 토크 TL");
        const sc1 = m.add("scope", c(0), 330, { name: "속도", rpm: true });
        const sc2 = m.add("scope", c(1), 330, { name: "전류 [A]" });
        const sc3 = m.add("scope", c(2), 330, { name: "토크 [N·m]" });
        m.w(ref, 0, s1, 0); m.w(s1, 0, pw, 0); m.w(pw, 0, s2, 0); m.w(s2, 0, pi, 0); m.w(pi, 0, s3, 0); m.w(s3, 0, mo, 0);
        m.w(mo, 0, s1, 1); m.w(mo, 2, s2, 1); m.w(mo, 0, ff, 0); m.w(ff, 0, s3, 1); m.w(tl, 0, mo, 1);
        m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1); m.w(pw, 0, sc2, 0); m.w(mo, 2, sc2, 1); m.w(mo, 3, sc2, 2); m.w(mo, 6, sc3, 0); m.w(tl, 0, sc3, 1);
      };
      T["BLDC: 전류 제어만 (전류 PI)"] = (dg) => {
        const m = mk(dg);
        const ref = m.add("square", c(0), 40, { amp: +(0.5 * IlB).toPrecision(2), period: 0.05, offset: 0 }, "전류 지령 I*");
        const s = m.add("sum", c(1), 40, { signs: "+-" }, "전류 오차");
        const pi = m.add("pid", c(2), 40, { mode: "PI", Kp: r4(gb.Kpi), Ki: r4(gb.Kii), lo: -VB, hi: VB }, "전류 PI");
        const mo = m.add("bldc", c(3), 40, {}, "BLDC");
        const sc1 = m.add("scope", c(1), 270, { name: "전류 [A]" });
        const sc2 = m.add("scope", c(3), 270, { name: "속도", rpm: true });
        m.w(ref, 0, s, 0); m.w(s, 0, pi, 0); m.w(pi, 0, mo, 0); m.w(mo, 2, s, 1);
        m.w(ref, 0, sc1, 0); m.w(mo, 2, sc1, 1); m.w(mo, 3, sc1, 2); m.w(mo, 0, sc2, 0);
      };
      T["BLDC: 개루프 (v* = 2ke·ω*)"] = (dg) => {
        const m = mk(dg);
        const ref = m.add("const", c(0), 40, { value: wRpm, rpm: true }, "속도 지령 ω*");
        const k = m.add("gain", c(1), 40, { K: r4(KB) }, "2ke");
        const mo = m.add("bldc", c(2), 40, { TL: +(+B.TL).toPrecision(3) }, "BLDC");
        const sc1 = m.add("scope", c(1), 270, { name: "속도", rpm: true });
        const sc2 = m.add("scope", c(3), 270, { name: "상전류 [A]" });
        m.w(ref, 0, k, 0); m.w(k, 0, mo, 0); m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1);
        m.w(mo, 3, sc2, 0); m.w(mo, 4, sc2, 1); m.w(mo, 5, sc2, 2);
      };
    }
    if (env.im) {
      const I = env.im, ip = I.p, ppI = Math.round(ip.poles / 2), idr = I.idRated;
      const gI = ACEngine.imGains(ip, 1500, 30, idr), nsI = 120 * ip.f / ip.poles;
      const iqMax = +Math.sqrt(Math.max(I.Ilim * I.Ilim - idr * idr, 1)).toPrecision(3);
      T["유도전동기: V/f 제어 (속도 지령 → 주파수·전압)"] = (dg) => {
        const m = mk(dg);
        const ref = m.add("square", c(0), 40, { amp: Math.round(0.25 * nsI), period: 2, offset: Math.round(0.6 * nsI), rpm: true }, "속도 지령 n*");
        const lp = m.add("lpf", c(1), 40, { tau: 0.15 }, "가감속 완화");
        const kf = m.add("gain", c(2), 40, { K: r4(ppI / (2 * Math.PI)) }, "f = (P/2)·ω/2π");
        const kv = m.add("gain", c(3), 150, { K: r4(ip.V / ip.f) }, "V/f 비율");
        const lv = m.add("limit", c(4), 150, { lo: 0, hi: ip.V }, "전압 제한");
        const mo = m.add("im", c(5), 40, { mode: "V/f" }, "유도전동기");
        const tl = m.add("step", c(3), 300, { t0: 1.0, v0: 0, v1: Math.round(I.TL) }, "부하 토크 TL");
        const sc1 = m.add("scope", c(0), 300, { name: "속도", rpm: true });
        const sc2 = m.add("scope", c(1), 300, { name: "토크·전류" });
        m.w(ref, 0, lp, 0); m.w(lp, 0, kf, 0); m.w(kf, 0, mo, 0); m.w(kf, 0, kv, 0); m.w(kv, 0, lv, 0); m.w(lv, 0, mo, 1); m.w(tl, 0, mo, 2);
        m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1); m.w(mo, 2, sc2, 0); m.w(mo, 3, sc2, 1); m.w(tl, 0, sc2, 2);
      };
      T["유도전동기: 벡터 제어 (속도 PI → iq*)"] = (dg) => {
        const m = mk(dg);
        const ref = m.add("const", c(0), 40, { value: Math.round(0.8 * nsI), rpm: true }, "속도 지령 n*");
        const s1 = m.add("sum", c(1), 40, { signs: "+-" }, "속도 오차");
        const pw = m.add("pid", c(2), 40, { mode: "PI", Kp: r4(gI.Kpw), Ki: r4(gI.Kiw), lo: -iqMax, hi: iqMax }, "속도 PI → iq*");
        const idc = m.add("const", c(2), 170, { value: +idr.toPrecision(3) }, "자속 전류 id*");
        const mo = m.add("im", c(4), 40, { mode: "벡터" }, "유도전동기");
        const tl = m.add("step", c(3), 300, { t0: 1.0, v0: 0, v1: Math.round(I.TL) }, "부하 토크 TL");
        const sc1 = m.add("scope", c(0), 300, { name: "속도", rpm: true });
        const sc2 = m.add("scope", c(1), 300, { name: "dq 전류 [A]" });
        const sc3 = m.add("scope", c(2), 300, { name: "토크 [N·m]" });
        m.w(ref, 0, s1, 0); m.w(s1, 0, pw, 0); m.w(idc, 0, mo, 0); m.w(pw, 0, mo, 1); m.w(mo, 0, s1, 1); m.w(tl, 0, mo, 2);
        m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1); m.w(pw, 0, sc2, 0); m.w(mo, 5, sc2, 1); m.w(mo, 4, sc2, 2); m.w(mo, 2, sc3, 0); m.w(tl, 0, sc3, 1);
      };
    }
    if (env.pmsm) {
      const Q = env.pmsm, qp = Q.p, gQ = ACEngine.pmsmGains(qp, 2000, 100);
      T["PMSM: 벡터 제어 (id = 0, 속도 PI → iq*)"] = (dg) => {
        const m = mk(dg);
        const ref = m.add("square", c(0), 40, { amp: Math.round(0.4 * Q.nBase), period: 0.6, offset: Math.round(0.5 * Q.nBase), rpm: true }, "속도 지령 n*");
        const s1 = m.add("sum", c(1), 40, { signs: "+-" }, "속도 오차");
        const pw = m.add("pid", c(2), 40, { mode: "PI", Kp: r4(gQ.Kpw), Ki: r4(gQ.Kiw), lo: -Q.Imax, hi: Q.Imax }, "속도 PI → iq*");
        const idc = m.add("const", c(2), 170, { value: 0 }, "id* = 0");
        const mo = m.add("pmsm", c(4), 40, {}, "PMSM");
        const tl = m.add("step", c(3), 300, { t0: 0.3, v0: 0, v1: +(+Q.TL).toPrecision(3) }, "부하 토크 TL");
        const sc1 = m.add("scope", c(0), 300, { name: "속도", rpm: true });
        const sc2 = m.add("scope", c(1), 300, { name: "dq 전류 [A]" });
        const sc3 = m.add("scope", c(2), 300, { name: "토크·전압" });
        m.w(ref, 0, s1, 0); m.w(s1, 0, pw, 0); m.w(idc, 0, mo, 0); m.w(pw, 0, mo, 1); m.w(mo, 0, s1, 1); m.w(tl, 0, mo, 2);
        m.w(ref, 0, sc1, 0); m.w(mo, 0, sc1, 1); m.w(pw, 0, sc2, 0); m.w(mo, 4, sc2, 1); m.w(mo, 3, sc2, 2); m.w(mo, 2, sc3, 0); m.w(mo, 5, sc3, 1);
      };
    }
    T["빈 화면"] = () => {};
    return T;
  }

  const api = { DEF, Diagram, Runner, templates, insOf, outsOf, titleOf, RPM };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Blocks = api;
})(this);
