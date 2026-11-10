/* 회로 시뮬레이터 엔진: 격자 위 회로도 → 절점(노드) 해석 → 시간 영역 계산.
 *
 * 회로도 좌표는 격자 단위 정수. 부품은 단자 a → b 방향으로 SPAN 칸 길이 (rot 0 오른쪽, 1 아래, 2 왼쪽, 3 위).
 * 해석은 수정 절점 해석(MNA) + 후진 오일러 동반 모델. 다이오드·스위치는 구간 선형(켜짐/꺼짐)으로 두고
 * 상태가 맞을 때까지 반복합니다. 전선은 0 Ω 이라 같은 절점으로 합치고, 전선마다 흐르는 전류는
 * 절점 안의 전선 그래프에서 KCL 로 따로 구합니다 (화면의 전류 흐름 표시용).
 *
 * 부호 약속: 모든 2단자 부품의 전류 i 는 "부품 안에서 a → b" 방향.
 *  - 수동 소자·전동기·전류계: a 로 들어가 b 로 나옴. 전압 v = Va − Vb (전압 강하).
 *  - 전원 (직류·교류 전압원, 전류원): a = −, b = +. 안에서 − → + 로 흐르므로 전력을 내보내면 i > 0, 전압 = Vb − Va.
 */
(function (root) {
  "use strict";
  const SPAN = 4;
  const GMIN = 1e-12;           // 모든 절점 → 접지 (떠 있는 회로도 풀리게)
  const GOFF = 1e-12;           // 열린 스위치·꺼진 다이오드
  const DIR = [[1, 0], [0, 1], [-1, 0], [0, -1]];

  // ---------------- 부품 정의 ----------------
  const MOTOR_DEF = { Ra: 0.5, La: 0.01, K: 1.8, J: 0.1, B: 0.005, TL: 0 };
  const DEF = {
    resistor: { name: "저항", params: { R: { label: "저항 R", v: 100, unit: "Ω", min: 1e-6 } } },
    lamp: { name: "전구", params: { Vr: { label: "정격 전압", v: 12, unit: "V", min: 1e-3 }, Pr: { label: "정격 전력", v: 10, unit: "W", min: 1e-6 } },
            desc: "저항 R = V정격²/P정격 인 전구입니다. 소비 전력이 정격에 가까울수록 밝게 빛납니다." },
    inductor: { name: "인덕터", params: { L: { label: "인덕턴스 L", v: 0.1, unit: "H", min: 1e-9 }, R: { label: "권선 저항", v: 0, unit: "Ω", min: 0 } },
                desc: "전류가 갑자기 바뀌지 못합니다 (v = L·di/dt). 스위치를 끊으면 높은 전압이 생길 수 있습니다." },
    capacitor: { name: "커패시터", params: { C: { label: "정전용량 C", v: 100e-6, unit: "F", min: 1e-15 } },
                 desc: "전압이 갑자기 바뀌지 못합니다 (i = C·dv/dt). 직류는 충전이 끝나면 전류가 0 이 됩니다." },
    vdc: { name: "직류 전압원", params: { V: { label: "전압 V", v: 12, unit: "V" } }, src: true,
           desc: "+ 표시 단자가 V 만큼 높은 전압입니다 (내부 저항 없음)." },
    vac: { name: "교류 전압원", params: { Vm: { label: "최댓값 Vm", v: 10, unit: "V" }, f: { label: "주파수 f", v: 60, unit: "Hz", min: 0 },
                                     ph: { label: "위상", v: 0, unit: "°" }, Vo: { label: "직류 성분", v: 0, unit: "V" } }, src: true,
           desc: "v(t) = Vo + Vm·sin(2πft + 위상). 실효값은 Vm/√2 입니다." },
    idc: { name: "전류원", params: { I: { label: "전류 I", v: 0.1, unit: "A" } }, src: true,
           desc: "화살표 방향으로 일정한 전류 I 를 밀어냅니다." },
    switch: { name: "스위치", params: { on: { label: "닫힘 (ON)", type: "bool", v: false }, Ron: { label: "닫힘 저항", v: 0.001, unit: "Ω", min: 1e-6 } },
              desc: "실행 중에 회로도에서 스위치를 클릭하면 열고 닫을 수 있습니다." },
    pwm: { name: "PWM 스위치", params: { f: { label: "스위칭 주파수", v: 1000, unit: "Hz", min: 1e-3 }, D: { label: "듀티비 D", v: 0.5, unit: "", min: 0, max: 1 },
                                      Ron: { label: "닫힘 저항", v: 0.001, unit: "Ω", min: 1e-6 } },
           desc: "한 주기 중 앞쪽 D 만큼 닫히는 전자 스위치 (트랜지스터·IGBT 를 이상화). 초퍼·인버터를 만들 때 씁니다." },
    diode: { name: "다이오드", params: { Vf: { label: "순방향 전압", v: 0.7, unit: "V", min: 0 }, Ron: { label: "도통 저항", v: 0.01, unit: "Ω", min: 1e-6 } },
             desc: "삼각형 방향(애노드 → 캐소드)으로만 전류가 흐릅니다. 켜지면 Vf + Ron·i 만큼 전압이 떨어집니다." },
    motor: { name: "DC 전동기", params: {
               Ra: { label: "전기자 저항 Ra", v: MOTOR_DEF.Ra, unit: "Ω", min: 1e-6 }, La: { label: "전기자 인덕턴스 La", v: MOTOR_DEF.La, unit: "H", min: 1e-9 },
               K: { label: "역기전력 상수 Kφ", v: MOTOR_DEF.K, unit: "V·s/rad", min: 1e-6 }, J: { label: "관성 J", v: MOTOR_DEF.J, unit: "kg·m²", min: 1e-9 },
               B: { label: "점성 마찰 B", v: MOTOR_DEF.B, unit: "N·m·s", min: 0 }, TL: { label: "부하 토크 TL", v: MOTOR_DEF.TL, unit: "N·m", min: 0 } },
             desc: "타여자(자속 일정) DC 전동기의 전기자 회로: v = Ra·i + La·di/dt + Kφ·ω,  J·dω/dt = Kφ·i − Bω − TL. " +
                   "부하 토크는 회전을 막는 방향으로 걸립니다." },
    ammeter: { name: "전류계", params: {}, desc: "내부 저항 0. 화살표(a → b) 방향 전류를 재고, 순시값과 실효값을 보여 줍니다." },
    voltmeter: { name: "전압계", params: {}, desc: "내부 저항 무한대. + 단자와 − 단자 사이 전압을 재고, 순시값과 실효값을 보여 줍니다." },
    ground: { name: "접지", params: {}, one: true, desc: "전압 0 V 기준점입니다. 회로마다 하나씩 두면 전압 색이 알기 쉬워집니다." },
  };
  const BRANCH = new Set(["inductor", "vdc", "vac", "motor", "ammeter"]);   // 전류를 미지수로 두는 부품

  function terminals(e) {
    if (DEF[e.type].one) return [[e.x, e.y]];
    const d = DIR[((e.rot || 0) % 4 + 4) % 4];
    return [[e.x, e.y], [e.x + SPAN * d[0], e.y + SPAN * d[1]]];
  }
  const key = (p) => p[0] + "," + p[1];
  function defaults(type) {
    const p = {};
    for (const [k, s] of Object.entries(DEF[type].params)) p[k] = s.v;
    return p;
  }

  // ---------------- 회로도 ----------------
  class Schematic {
    constructor() { this.elems = []; this.wires = []; this.nid = 1; this.version = 0; }
    add(type, x, y, rot = 0, p = {}) {
      const e = { id: this.nid++, type, x, y, rot, p: Object.assign(defaults(type), p) };
      this.elems.push(e); this.version++; return e;
    }
    wire(x1, y1, x2, y2) {
      if (x1 === x2 && y1 === y2) return null;
      const w = { id: this.nid++, x1, y1, x2, y2 }; this.wires.push(w); this.version++; return w;
    }
    // 두 점을 잇는 전선 (가로·세로가 아니면 ㄱ자로 꺾어 두 토막)
    path(x1, y1, x2, y2, hFirst = true) {
      if (x1 === x2 || y1 === y2) return [this.wire(x1, y1, x2, y2)].filter(Boolean);
      return hFirst ? [this.wire(x1, y1, x2, y1), this.wire(x2, y1, x2, y2)] : [this.wire(x1, y1, x1, y2), this.wire(x1, y2, x2, y2)];
    }
    get(id) { return this.elems.find((e) => e.id === id) || this.wires.find((w) => w.id === id); }
    remove(id) {
      const n = this.elems.length + this.wires.length;
      this.elems = this.elems.filter((e) => e.id !== id); this.wires = this.wires.filter((w) => w.id !== id);
      if (this.elems.length + this.wires.length !== n) this.version++;
    }
    clear() { this.elems = []; this.wires = []; this.version++; }
    toJSON() { return { elems: this.elems, wires: this.wires }; }
    load(j) {
      this.elems = (j.elems || []).filter((e) => DEF[e.type]).map((e) => Object.assign({}, e, { p: Object.assign(defaults(e.type), e.p) }));
      this.wires = (j.wires || []).map((w) => Object.assign({}, w));
      this.nid = 1 + Math.max(0, ...this.elems.map((e) => e.id), ...this.wires.map((w) => w.id)); this.version++;
    }
  }

  // ---------------- 연결 해석 (netlist) ----------------
  function netlist(sc) {
    const pts = new Map();                 // key → 점 번호
    const P = [];
    const pid = (p) => { const k = key(p); if (!pts.has(k)) { pts.set(k, P.length); P.push(p); } return pts.get(k); };
    for (const e of sc.elems) for (const t of terminals(e)) pid(t);
    for (const w of sc.wires) { pid([w.x1, w.y1]); pid([w.x2, w.y2]); }
    // 전선 위에 놓인 다른 점(T 연결)으로 전선을 쪼갬 → 토막
    const segs = [];                       // {w, a, b} 점 번호
    for (const w of sc.wires) {
      const on = [];
      const horiz = w.y1 === w.y2, vert = w.x1 === w.x2;
      P.forEach((p, i) => {
        if (horiz && p[1] === w.y1 && p[0] >= Math.min(w.x1, w.x2) && p[0] <= Math.max(w.x1, w.x2)) on.push(i);
        else if (vert && !horiz && p[0] === w.x1 && p[1] >= Math.min(w.y1, w.y2) && p[1] <= Math.max(w.y1, w.y2)) on.push(i);
      });
      if (!horiz && !vert) on.push(pid([w.x1, w.y1]), pid([w.x2, w.y2]));
      const s = (i) => (horiz ? (P[i][0] - w.x1) * Math.sign(w.x2 - w.x1 || 1) : (P[i][1] - w.y1) * Math.sign(w.y2 - w.y1 || 1));
      on.sort((i, j) => s(i) - s(j));
      for (let k = 0; k + 1 < on.length; k++) segs.push({ w: w.id, a: on[k], b: on[k + 1] });
    }
    // 점 → 절점 (union-find)
    const par = P.map((_, i) => i);
    const find = (i) => (par[i] === i ? i : (par[i] = find(par[i])));
    for (const s of segs) par[find(s.a)] = find(s.b);
    const grounds = new Set(sc.elems.filter((e) => e.type === "ground").map((e) => find(pid(terminals(e)[0]))));
    const nodeOf = new Map();               // 루트 → 절점 번호 (0 = 접지)
    let nn = 1;
    P.forEach((_, i) => { const r = find(i); if (!nodeOf.has(r)) nodeOf.set(r, grounds.has(r) ? 0 : nn++); });
    const node = P.map((_, i) => nodeOf.get(find(i)));
    const elems = sc.elems.filter((e) => e.type !== "ground").map((e) => {
      const t = terminals(e).map(pid);
      return { e, pa: t[0], pb: t[1], a: node[t[0]], b: node[t[1]] };
    });
    return { P, segs, node, nNodes: nn, elems, pid };
  }

  // ---------------- 선형 방정식 (가우스 소거, 부분 피벗) ----------------
  function solve(A, z, n) {
    for (let c = 0; c < n; c++) {
      let piv = c, mx = Math.abs(A[c * n + c]);
      for (let r = c + 1; r < n; r++) { const v = Math.abs(A[r * n + c]); if (v > mx) { mx = v; piv = r; } }
      if (mx < 1e-300) return false;
      if (piv !== c) {
        for (let k = 0; k < n; k++) { const t = A[c * n + k]; A[c * n + k] = A[piv * n + k]; A[piv * n + k] = t; }
        const t = z[c]; z[c] = z[piv]; z[piv] = t;
      }
      const d = A[c * n + c];
      for (let r = c + 1; r < n; r++) {
        const f = A[r * n + c] / d; if (f === 0) continue;
        for (let k = c; k < n; k++) A[r * n + k] -= f * A[c * n + k];
        z[r] -= f * z[c];
      }
    }
    for (let r = n - 1; r >= 0; r--) {
      let s = z[r];
      for (let k = r + 1; k < n; k++) s -= A[r * n + k] * z[k];
      z[r] = s / A[r * n + r];
    }
    return true;
  }

  // ---------------- 시뮬레이터 ----------------
  class Sim {
    constructor(sc) { this.sc = sc; this.compiled = -1; this.reset(); }
    reset() {
      this.t = 0; this.st = {};             // 부품 id → 상태 (커패시터 전압, 인덕터 전류, 전동기 ω·θ, 다이오드 켜짐 ...)
      this.V = []; this.I = {}; this.err = ""; this.compiled = -1;
    }
    compile() {
      this.net = netlist(this.sc); this.compiled = this.sc.version;
      const nb = this.net.elems.filter((x) => BRANCH.has(x.e.type));
      this.bIdx = new Map(nb.map((x, k) => [x.e.id, k]));
      this.N = this.net.nNodes - 1 + nb.length;
      for (const x of this.net.elems) if (!this.st[x.e.id]) this.st[x.e.id] = { vc: 0, il: 0, w: 0, th: 0, on: false, ms: 0, ms2: 0 };
      this.V = new Array(this.net.nNodes).fill(0);
    }
    switchOn(x, t) {
      const e = x.e;
      if (e.type === "switch") return !!e.p.on;
      if (e.type === "pwm") { const ph = (t * e.p.f) % 1; return ph < e.p.D; }
      return false;
    }
    srcV(e, t) {
      if (e.type === "vdc") return +e.p.V;
      return +e.p.Vo + e.p.Vm * Math.sin(2 * Math.PI * e.p.f * t + e.p.ph * Math.PI / 180);
    }
    // 한 걸음 (후진 오일러)
    step(h) {
      if (this.compiled !== this.sc.version) this.compile();
      const net = this.net, n1 = net.nNodes - 1, N = this.N, t = this.t + h;
      if (N === 0) { this.t = t; return; }
      const ix = (nd) => nd - 1;           // 절점 → 행 (접지 = −1)
      let A, z, ok = true;
      const diodes = net.elems.filter((x) => x.e.type === "diode");
      for (let it = 0; it < 12; it++) {
        A = new Float64Array(N * N); z = new Float64Array(N);
        const G = (a, b, g) => {
          const i = ix(a), j = ix(b);
          if (i >= 0) A[i * N + i] += g; if (j >= 0) A[j * N + j] += g;
          if (i >= 0 && j >= 0) { A[i * N + j] -= g; A[j * N + i] -= g; }
        };
        const Iin = (a, b, I) => { const i = ix(a), j = ix(b); if (i >= 0) z[i] -= I; if (j >= 0) z[j] += I; };   // a → b 로 I
        for (let k = 0; k < n1; k++) A[k * N + k] += GMIN;
        for (const x of net.elems) {
          const e = x.e, p = e.p, s = this.st[e.id], a = x.a, b = x.b;
          switch (e.type) {
            case "resistor": G(a, b, 1 / Math.max(p.R, 1e-6)); break;
            case "lamp": G(a, b, p.Pr / (p.Vr * p.Vr)); break;
            case "capacitor": { const g = p.C / h; G(a, b, g); Iin(a, b, -g * s.vc); break; }
            case "idc": Iin(a, b, p.I); break;      // 전류원: 부품 안 a → b 로 I (b 쪽으로 밀어냄)
            case "switch": case "pwm": G(a, b, this.switchOn(x, t) ? 1 / p.Ron : GOFF); break;
            case "diode": if (s.on) { G(a, b, 1 / p.Ron); Iin(a, b, -p.Vf / p.Ron); } else G(a, b, GOFF); break;
            case "voltmeter": break;
            default: {   // 가지 전류 미지수: Va − Vb − Z·i = r
              const k = n1 + this.bIdx.get(e.id), i = ix(a), j = ix(b);
              if (i >= 0) { A[i * N + k] += 1; A[k * N + i] += 1; }
              if (j >= 0) { A[j * N + k] -= 1; A[k * N + j] -= 1; }
              if (e.type === "inductor") { A[k * N + k] = -(p.R + p.L / h); z[k] = -p.L / h * s.il; }
              else if (e.type === "motor") { A[k * N + k] = -(p.Ra + p.La / h); z[k] = p.K * s.w - p.La / h * s.il; }
              else if (e.type === "ammeter") { A[k * N + k] = 0; z[k] = 0; }
              else { A[k * N + k] = 0; z[k] = -this.srcV(e, t); }   // 전원: Va − Vb = −V (b 가 +)
            }
          }
        }
        ok = solve(A, z, N);
        if (!ok) break;
        // 다이오드 상태 점검
        let changed = false;
        for (const x of diodes) {
          const s = this.st[x.e.id], va = x.a ? z[x.a - 1] : 0, vb = x.b ? z[x.b - 1] : 0, v = va - vb;
          const i = s.on ? (v - x.e.p.Vf) / x.e.p.Ron : 0;
          if (!s.on && v > x.e.p.Vf + 1e-9) { s.on = true; changed = true; }
          else if (s.on && i < -1e-12) { s.on = false; changed = true; }
        }
        if (!changed) break;
      }
      if (!ok) {
        this.err = "회로를 풀 수 없습니다: 전압원끼리 바로 이어졌거나 (단락), 전압원·전류계만으로 된 고리가 있습니다.";
        this.t = t; return;
      }
      this.err = "";
      const V = this.V; V[0] = 0;
      for (let k = 1; k < net.nNodes; k++) V[k] = z[k - 1];
      // 부품 전류·상태 갱신
      for (const x of net.elems) {
        const e = x.e, p = e.p, s = this.st[e.id], v = V[x.a] - V[x.b];
        let i = 0;
        switch (e.type) {
          case "resistor": i = v / Math.max(p.R, 1e-6); break;
          case "lamp": i = v * p.Pr / (p.Vr * p.Vr); break;
          case "capacitor": i = p.C / h * (v - s.vc); s.vc = v; break;
          case "idc": i = p.I; break;
          case "switch": case "pwm": s.on = this.switchOn(x, t); i = v * (s.on ? 1 / p.Ron : GOFF); break;
          case "diode": i = s.on ? (v - p.Vf) / p.Ron : v * GOFF; break;
          case "voltmeter": i = 0; break;
          default: i = z[n1 + this.bIdx.get(e.id)];
        }
        if (e.type === "inductor") s.il = i;
        if (e.type === "motor") {
          s.il = i;
          const TL = p.TL * Math.tanh(s.w / 0.5);      // 회전을 막는 방향 (정지 근처는 부드럽게)
          s.Te = p.K * i;
          s.w = (s.w + h * (s.Te - TL) / p.J) / (1 + h * p.B / p.J);
          s.th += s.w * h; s.E = p.K * s.w;
        }
        this.I[e.id] = i;
        // 계기용 실효값 (지수 평균, 시정수 0.1 s)
        const meas = e.type === "voltmeter" ? v : i, a = Math.min(1, h / 0.1);
        s.ms2 += a * (meas * meas - s.ms2); s.ms += a * (meas - s.ms);
      }
      this.t = t;
    }
    // 화면용: 부품의 전압 (전원은 + 단자 기준)
    volt(id) {
      const x = this.net && this.net.elems.find((q) => q.e.id === id);
      if (!x) return 0;
      const v = this.V[x.a] - this.V[x.b];
      return DEF[x.e.type].src ? -v : v;
    }
    nodeV(pointIdx) { return this.net ? this.V[this.net.node[pointIdx]] || 0 : 0; }
    // 전선 토막마다 흐르는 전류 (a → b 방향 +). 절점 안의 전선 그래프를 단위 저항망으로 보고 KCL 로 품.
    wireCurrents() {
      const net = this.net; if (!net) return [];
      const inj = new Float64Array(net.P.length);       // 점으로 들어오는 전류
      for (const x of net.elems) {
        const i = this.I[x.e.id] || 0;
        inj[x.pa] -= i; if (x.pb !== undefined) inj[x.pb] += i;
      }
      const out = new Array(net.segs.length).fill(0);
      // 토막 연결 성분별로 라플라시안 풀기
      const adj = new Map();
      net.segs.forEach((s, k) => {
        if (!adj.has(s.a)) adj.set(s.a, []); if (!adj.has(s.b)) adj.set(s.b, []);
        adj.get(s.a).push(k); adj.get(s.b).push(k);
      });
      const seen = new Set();
      for (const start of adj.keys()) {
        if (seen.has(start)) continue;
        const comp = [start]; seen.add(start);
        for (let q = 0; q < comp.length; q++) for (const k of adj.get(comp[q])) {
          const o = net.segs[k].a === comp[q] ? net.segs[k].b : net.segs[k].a;
          if (!seen.has(o)) { seen.add(o); comp.push(o); }
        }
        const m = comp.length - 1; if (m <= 0) continue;
        const loc = new Map(comp.map((p, i) => [p, i - 1]));   // 첫 점을 기준(φ=0)
        const A = new Float64Array(m * m), z = new Float64Array(m);
        const segK = new Set();
        for (const p of comp) for (const k of adj.get(p)) segK.add(k);
        for (const k of segK) {
          const i = loc.get(net.segs[k].a), j = loc.get(net.segs[k].b);
          if (i >= 0) A[i * m + i] += 1; if (j >= 0) A[j * m + j] += 1;
          if (i >= 0 && j >= 0) { A[i * m + j] -= 1; A[j * m + i] -= 1; }
        }
        comp.forEach((p, i) => { if (i > 0) z[i - 1] = inj[p]; });
        if (!solve(A, z, m)) continue;
        const phi = (p) => (loc.get(p) < 0 ? 0 : z[loc.get(p)]);
        for (const k of segK) out[k] = phi(net.segs[k].a) - phi(net.segs[k].b);
      }
      return out;
    }
  }

  // ---------------- 템플릿 ----------------
  const TEMPLATES = {
    "RL 회로: 스위치를 닫으면 전류가 서서히 오름": (sc) => {
      sc.add("vdc", 4, 10, 3, { V: 12 });
      sc.add("switch", 4, 6, 0);
      sc.add("resistor", 8, 6, 0, { R: 10 });
      sc.add("ammeter", 12, 6, 0);
      sc.add("inductor", 16, 6, 1, { L: 0.5 });
      sc.add("diode", 20, 10, 3);                  // 환류 다이오드: 스위치를 열 때 인덕터 전류의 길
      sc.wire(16, 6, 20, 6); sc.wire(20, 10, 4, 10);
      sc.add("ground", 10, 10);
    },
    "RC 회로: 충전과 방전": (sc) => {
      sc.add("vdc", 4, 10, 3, { V: 10 });
      sc.add("switch", 4, 6, 0, { on: true });
      sc.add("resistor", 8, 6, 0, { R: 1000 });
      sc.add("capacitor", 12, 6, 1, { C: 100e-6 });
      sc.wire(12, 6, 16, 6);
      sc.add("voltmeter", 16, 6, 1);
      sc.add("switch", 16, 6, 0);
      sc.add("resistor", 20, 6, 1, { R: 1000 });
      sc.wire(20, 10, 4, 10);
      sc.add("ground", 8, 10);
    },
    "직렬 회로: 전압이 나뉨 (전압 분배)": (sc) => {
      sc.add("vdc", 4, 12, 3, { V: 12 });
      sc.wire(4, 8, 4, 4);
      sc.add("resistor", 4, 4, 0, { R: 100 });
      sc.add("resistor", 8, 4, 0, { R: 200 });
      sc.add("resistor", 12, 4, 0, { R: 300 });
      sc.wire(16, 4, 20, 4);
      sc.add("ammeter", 20, 4, 1);
      sc.wire(20, 8, 20, 12); sc.wire(20, 12, 4, 12);
      sc.add("voltmeter", 8, 8, 0);
      sc.wire(8, 4, 8, 8); sc.wire(12, 4, 12, 8);
      sc.add("ground", 12, 12);
    },
    "병렬 회로: 전구마다 전류가 나뉨": (sc) => {
      sc.add("vdc", 4, 10, 3, { V: 12 });
      sc.add("ammeter", 4, 6, 0);
      sc.wire(8, 6, 20, 6);
      sc.add("lamp", 8, 6, 1, { Vr: 12, Pr: 5 });
      sc.add("lamp", 14, 6, 1, { Vr: 12, Pr: 10 });
      sc.add("switch", 20, 6, 1, { on: true });
      sc.add("lamp", 20, 10, 1, { Vr: 12, Pr: 20 });
      sc.wire(20, 14, 4, 14); sc.wire(4, 14, 4, 10);
      sc.wire(8, 10, 8, 14); sc.wire(14, 10, 14, 14);
      sc.add("ground", 4, 14);
    },
    "RLC 직렬 공진 (교류)": (sc) => {
      sc.add("vac", 4, 10, 3, { Vm: 10, f: 159 });
      sc.add("ammeter", 4, 6, 0);
      sc.add("resistor", 8, 6, 0, { R: 10 });
      sc.add("inductor", 12, 6, 0, { L: 0.01 });
      sc.add("capacitor", 16, 6, 1, { C: 100e-6 });
      sc.wire(16, 10, 4, 10);
      sc.add("voltmeter", 20, 6, 1);
      sc.wire(16, 6, 20, 6); sc.wire(20, 10, 16, 10);
      sc.add("ground", 10, 10);
    },
    "반파 정류: 다이오드 1개": (sc) => {
      sc.add("vac", 4, 10, 3, { Vm: 10, f: 60 });
      sc.add("diode", 4, 6, 0);
      sc.wire(8, 6, 12, 6);
      sc.add("resistor", 12, 6, 1, { R: 100 });
      sc.add("voltmeter", 16, 6, 1);
      sc.wire(12, 6, 16, 6); sc.wire(16, 10, 4, 10);
      sc.add("ground", 8, 10);
    },
    "전파 정류: 다이오드 브리지 + 평활 커패시터": (sc) => {
      sc.add("vac", 10, 8, 0, { Vm: 15, f: 60 });
      sc.wire(6, 8, 10, 8); sc.wire(14, 8, 18, 8);
      sc.add("diode", 6, 8, 3); sc.add("diode", 6, 12, 3);
      sc.add("diode", 18, 8, 3); sc.add("diode", 18, 12, 3);
      sc.wire(6, 4, 30, 4); sc.wire(6, 12, 30, 12);
      sc.add("switch", 24, 4, 1, { on: false });
      sc.add("capacitor", 24, 8, 1, { C: 470e-6 });
      sc.add("ammeter", 30, 4, 1);
      sc.add("resistor", 30, 8, 1, { R: 100 });
      sc.add("ground", 12, 12);
    },
    "DC 전동기 기동: 기동 저항으로 돌입 전류 줄이기": (sc) => {
      sc.add("vdc", 4, 12, 3, { V: 220 });
      sc.add("switch", 4, 8, 0);
      sc.add("resistor", 8, 8, 0, { R: 5 });
      sc.wire(8, 8, 8, 4); sc.add("switch", 8, 4, 0); sc.wire(12, 4, 12, 8);
      sc.add("ammeter", 12, 8, 0);
      sc.add("motor", 16, 8, 1, { TL: 30 });
      sc.wire(16, 12, 4, 12);
      sc.add("ground", 10, 12);
    },
    "강압 초퍼: PWM 으로 DC 전동기 속도 바꾸기": (sc) => {
      sc.add("vdc", 4, 12, 3, { V: 220 });
      sc.add("pwm", 4, 8, 0, { f: 1000, D: 0.5 });
      sc.add("diode", 8, 12, 3);
      sc.wire(8, 8, 12, 8);
      sc.add("ammeter", 12, 8, 0);
      sc.add("motor", 16, 8, 1, { TL: 20 });
      sc.wire(16, 12, 4, 12);
      sc.add("ground", 12, 12);
    },
    "빈 화면": () => {},
  };

  const api = { SPAN, DEF, Schematic, Sim, netlist, terminals, defaults, TEMPLATES };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Circuit = api;
})(this);
