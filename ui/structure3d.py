"""전동기 3D 구조 (Plotly). 마우스로 돌려 보고, 부품 이름·역할을 확인하고, 분해·조립 애니메이션을 본다.

모델 좌표: 축 = z, 단면 = (x, y), 길이 단위는 임의 (고정자 바깥 반지름 ≈ 1.1).
그림 좌표: 축이 화면 가로가 되도록 (X, Y, Z) = (z, x, y) 로 바꿔 그린다.
"""
from dataclasses import dataclass
import math
import numpy as np
import plotly.graph_objects as go

from motors.winding import Winding

PCOL = ["#d62828", "#2a9d3a", "#1d4ed8"]
TAU = 2 * math.pi


# ---------------------------------------------------------------- 형상 도구
class Mesh:
    def __init__(self):
        self.v = []      # (x, y, z)
        self.f = []      # (i, j, k)

    def add(self, verts, faces):
        o = len(self.v)
        self.v.extend(verts)
        self.f.extend([(a + o, b + o, c + o) for a, b, c in faces])
        return self

    def __bool__(self):
        return bool(self.v)


def _quad(a, b, c, d):
    return [(a, b, c), (a, c, d)]


def ring(mesh, r0, r1, z0, z1, a0=0.0, a1=TAU, n=None):
    """원통 고리 (각도 a0~a1 의 부채꼴 고리, r0 = 0 이면 원기둥)."""
    full = abs(a1 - a0 - TAU) < 1e-9
    n = n or max(6, int(48 * (a1 - a0) / TAU))
    th = np.linspace(a0, a1, n + 1)
    V, F = [], []
    for t in th:
        c, s = math.cos(t), math.sin(t)
        V += [(r1 * c, r1 * s, z0), (r1 * c, r1 * s, z1), (r0 * c, r0 * s, z0), (r0 * c, r0 * s, z1)]
    for i in range(n):
        a, b = 4 * i, 4 * (i + 1)
        F += _quad(a, b, b + 1, a + 1)            # 바깥면
        F += _quad(a + 2, a + 3, b + 3, b + 2)    # 안쪽면
        F += _quad(a, a + 2, b + 2, b)            # 아랫면
        F += _quad(a + 1, b + 1, b + 3, a + 3)    # 윗면
    if not full:
        e = 4 * n
        F += _quad(0, 1, 3, 2) + _quad(e, e + 2, e + 3, e + 1)
    mesh.add(V, F)


def box(mesh, theta, r0, r1, t0, t1, z0, z1):
    """반지름 방향으로 놓인 상자 (각 theta, 반지름 r0~r1, 접선 t0~t1, 축 z0~z1)."""
    c, s = math.cos(theta), math.sin(theta)
    pts = []
    for r, t in ((r0, t0), (r1, t0), (r1, t1), (r0, t1)):
        pts.append((r * c - t * s, r * s + t * c))
    V = [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
    F = _quad(0, 1, 2, 3) + _quad(4, 7, 6, 5) + _quad(0, 4, 5, 1) + _quad(1, 5, 6, 2) + _quad(2, 6, 7, 3) + _quad(3, 7, 4, 0)
    mesh.add(V, F)


def in_cut(theta, cut):
    if not cut:
        return False
    c0, c1 = cut
    t = (theta - c0) % TAU
    return t < (c1 - c0) % TAU


def ring_cut(mesh, r0, r1, z0, z1, cut, n=None):
    if cut:
        ring(mesh, r0, r1, z0, z1, cut[1], cut[0] + TAU, n)
    else:
        ring(mesh, r0, r1, z0, z1, n=n)


# ---------------------------------------------------------------- 부품
@dataclass
class Part:
    name: str
    desc: str
    color: str
    mesh: Mesh = None
    lines: list = None                 # [(xs, ys, zs)] 폴리라인 (None 으로 구분)
    width: float = 6
    opacity: float = 1.0
    explode: tuple = (0.0, 0.0)        # (축 방향 이동, 반지름 방향 이동)
    label: tuple = None                # 이름표 위치 (x, y, z)
    group: str = ""


def _xyz(points, explode, e):
    """모델 좌표 → 그림 좌표 (분해 적용)."""
    dz, dr = explode[0] * e, explode[1] * e
    out = []
    for x, y, z in points:
        if dr:
            r = math.hypot(x, y)
            if r > 1e-9:
                x, y = x * (1 + dr / r), y * (1 + dr / r)
        out.append((z + dz, x, y))
    return out


def _traces(parts, e, labels):
    tr = []
    for p in parts:
        hover = f"<b>{p.name}</b><br>{p.desc}<extra></extra>"
        if p.mesh:
            P = np.array(_xyz(p.mesh.v, p.explode, e))
            F = np.array(p.mesh.f)
            tr.append(go.Mesh3d(x=P[:, 0], y=P[:, 1], z=P[:, 2], i=F[:, 0], j=F[:, 1], k=F[:, 2], color=p.color,
                                opacity=p.opacity, name=p.name, legendgroup=p.name, showlegend=True, flatshading=True,
                                lighting=dict(ambient=0.55, diffuse=0.7, specular=0.25, roughness=0.6), hovertemplate=hover))
        if p.lines:
            xs, ys, zs = [], [], []
            for seg in p.lines:
                pts = _xyz(seg, p.explode, e)
                xs += [q[0] for q in pts] + [None]; ys += [q[1] for q in pts] + [None]; zs += [q[2] for q in pts] + [None]
            tr.append(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=p.color, width=p.width),
                                   name=p.name, legendgroup=p.name, showlegend=not p.mesh, hovertemplate=hover))
    if labels:
        lx, ly, lz, lt = [], [], [], []
        for p in parts:
            if p.label:
                (X, Y, Z), = _xyz([p.label], p.explode, e)
                lx.append(X); ly.append(Y); lz.append(Z); lt.append(p.name)
        tr.append(go.Scatter3d(x=lx, y=ly, z=lz, mode="markers+text", text=lt, textposition="top center",
                               marker=dict(size=3, color="#111"), textfont=dict(size=12, color="#111"),
                               name="이름표", showlegend=False, hoverinfo="skip"))
    return tr


def figure(parts, labels=True, n_frames=12, height=640):
    """분해 슬라이더·조립 애니메이션이 들어 있는 3D 그림."""
    es = [k / (n_frames - 1) for k in range(n_frames)]
    fig = go.Figure(data=_traces(parts, 0.0, labels))
    fig.frames = [go.Frame(data=_traces(parts, e, labels), name=f"{e:.2f}") for e in es]
    names = [f"{e:.2f}" for e in es]
    anim = lambda seq: [seq, dict(frame=dict(duration=120, redraw=True), transition=dict(duration=0), fromcurrent=False, mode="immediate")]
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="white",
        scene=dict(aspectmode="data", xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                   camera=dict(eye=dict(x=1.15, y=-1.55, z=0.75), up=dict(x=0, y=0, z=1))),
        legend=dict(itemclick="toggle", itemdoubleclick="toggleothers", font=dict(size=11), title=dict(text="부품 (클릭: 숨기기/보이기)")),
        updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.0, xanchor="left", yanchor="top", pad=dict(t=4, l=4),
                          buttons=[dict(label="▶ 분해", method="animate", args=anim(names)),
                                   dict(label="▶ 조립", method="animate", args=anim(names[::-1]))])],
        sliders=[dict(active=0, x=0.25, y=0.02, len=0.5, currentvalue=dict(prefix="분해 정도 ", font=dict(size=12)),
                      steps=[dict(label=f"{int(e * 100)}%", method="animate",
                                  args=[[n], dict(frame=dict(duration=0, redraw=True), mode="immediate")]) for e, n in zip(es, names)])],
    )
    return fig


# ---------------------------------------------------------------- 공통 부품
CUT = (math.radians(105), math.radians(205))     # 절개할 각도 범위 (기본 카메라를 향한 쪽)


def _common(parts, cut, L=0.6, R_frame=(1.12, 1.22), shaft=(-1.7, 1.35), bearing_z=0.95, fins=0):
    m = Mesh(); ring_cut(m, R_frame[0], R_frame[1], -L - 0.3, L + 0.3, cut)
    for k in range(fins):
        a = k * TAU / fins
        if not in_cut(a, cut):
            box(m, a, R_frame[1], R_frame[1] + 0.12, -0.015, 0.015, -L - 0.25, L + 0.25)
    parts.append(Part("프레임 (외함)" + (" · 냉각 핀" if fins else ""), "전동기 몸체. 고정자를 붙잡고 열을 바깥으로 내보냅니다.",
                      "#8a929b", m, opacity=1.0, label=(0, -R_frame[1] - (0.12 if fins else 0), 0.25)))
    for side, zz, ex in ((1, L + 0.3, 1.0), (-1, -L - 0.38, -1.0)):
        m = Mesh(); ring_cut(m, 0.2, R_frame[1], min(zz, zz + 0.08), max(zz, zz + 0.08), cut)
        parts.append(Part("엔드 브래킷 (" + ("앞" if side > 0 else "뒤") + ")",
                          "프레임 양 끝을 막는 덮개. 가운데에 베어링이 들어가 축을 받칩니다.", "#a3abb4", m,
                          explode=(ex, 0), label=(0, -0.8, zz + 0.04)))
    m = Mesh(); ring(m, 0, 0.1, shaft[0], shaft[1])
    parts.append(Part("축 (샤프트)", "회전자에 박혀 함께 도는 강철 축. 부하(팬, 펌프, 바퀴 등)에 토크를 전합니다.",
                      "#5c5c5c", m, explode=(2.2, 0), label=(0, 0, shaft[0] + 0.15)))
    m = Mesh()
    for zb in (bearing_z, -bearing_z - 0.02):
        ring(m, 0.1, 0.2, zb - 0.05, zb + 0.05)
    parts.append(Part("베어링 (2개)", "축을 매끄럽게 돌도록 받치는 구름 베어링. 엔드 브래킷에 끼워집니다.",
                      "#c0c4c8", m, explode=(2.2, 0), label=(0, 0.2, bearing_z)))


def _terminal_box(parts, text="단자함", desc="전원선이 들어와 권선 끝(단자)에 연결되는 상자.", r=1.22):
    m = Mesh(); box(m, math.pi / 2, r, r + 0.22, -0.25, 0.25, -0.2, 0.25)
    parts.append(Part(text, desc, "#6c757d", m, explode=(0, 0.5), label=(0, r + 0.25, 0.0)))


def _stator_core(parts, S, cut, kind, L=0.6, r_in=0.62, r_y=(0.9, 1.12)):
    m = Mesh(); ring_cut(m, r_y[0], r_y[1], -L, L, cut)
    sp = TAU / S
    for k in range(S):
        a = k * sp                      # 이빨 k 중심 (슬롯은 (k + ½)·sp)
        if in_cut(a, cut):
            continue
        hw = 0.42 * sp * 0.76 if kind == "distributed" else 0.32 * sp * 0.76
        box(m, a, r_in + 0.03, r_y[0] + 0.01, -hw, hw, -L, L)
        if kind == "concentrated":       # 이빨 끝 (극편)
            ring(m, r_in, r_in + 0.035, -L, L, a - 0.42 * sp, a + 0.42 * sp, 4)
    parts.append(Part("고정자 철심 (이빨·계철)", f"얇은 규소강판을 쌓은 철심. 이빨 사이 슬롯 {S}개에 권선이 들어가고, 바깥쪽 계철은 자속이 돌아가는 길입니다.",
                      "#9aa3ad", m, label=(0, -r_y[1], L * 0.6)))


def _stator_winding(parts, w: Winding, cut, L=0.6, r_slot=(0.7, 0.82)):
    """상별 코일: 슬롯 안 직선부 + 코일 끝(엔드 턴)."""
    sp = TAU / w.slots
    segs = {0: [], 1: [], 2: []}
    for c in w.coils:
        a = (c.slot_a + 0.5) * sp
        b = (c.slot_b + 0.5) * sp
        if w.kind == "concentrated":                  # 이빨 하나를 감는 코일: 슬롯 a 의 오른쪽, 슬롯 b 의 왼쪽
            a += 0.2 * sp; b -= 0.2 * sp
            ra = rb = 0.76
        else:
            ra, rb = r_slot[0], r_slot[1]             # 위층 → 아래층
        if in_cut((a + b) / 2 if abs(b - a) < math.pi else a, cut) and in_cut(a, cut):
            continue
        span = (b - a) % TAU
        ts = np.linspace(a, a + span, 14)
        lift = 0.1 + 0.05 * span
        top = [(ra * math.cos(a), ra * math.sin(a), -L), (ra * math.cos(a), ra * math.sin(a), L)]
        top += [((ra + (rb - ra) * f) * math.cos(t), (ra + (rb - ra) * f) * math.sin(t), L + lift * math.sin(math.pi * f))
                for f, t in zip(np.linspace(0, 1, 14), ts)]
        top += [(rb * math.cos(b), rb * math.sin(b), L), (rb * math.cos(b), rb * math.sin(b), -L)]
        top += [((rb + (ra - rb) * f) * math.cos(t), (rb + (ra - rb) * f) * math.sin(t), -L - lift * math.sin(math.pi * f))
                for f, t in zip(np.linspace(0, 1, 14), ts[::-1])]
        segs[c.phase].append(top)
    kind = "분포권" if w.kind == "distributed" else "집중권"
    for ph in range(3):
        parts.append(Part(f"{'ABC'[ph]}상 권선 ({kind})",
                          f"{'ABC'[ph]}상 코일. 슬롯 안 직선부는 토크를 만드는 부분, 양 끝 굽은 부분은 코일 끝(엔드 턴)입니다. "
                          + ("코일 하나가 극피치 근처 여러 슬롯을 건너 감깁니다." if w.kind == "distributed" else "코일 하나가 이빨 하나만 감습니다."),
                          PCOL[ph], lines=segs[ph], width=5,
                          label=((0.78 * math.cos((w.coils[[c.phase for c in w.coils].index(ph)].slot_a + 0.5) * sp),
                                  0.78 * math.sin((w.coils[[c.phase for c in w.coils].index(ph)].slot_a + 0.5) * sp), L + 0.2)
                                 if ph in [c.phase for c in w.coils] else None)))


def _rotor_core(parts, r=(0.2, 0.58), L=0.6, opacity=1.0, name="회전자 철심", desc="규소강판을 쌓은 회전자. 축에 끼워져 함께 돕니다."):
    m = Mesh(); ring(m, r[0], r[1], -L, L)
    parts.append(Part(name, desc, "#b9c0c8", m, opacity=opacity, explode=(2.2, 0), label=(0, r[1] * 0.7, -L)))


# ---------------------------------------------------------------- 전동기별 조립
def build_induction(w: Winding, cut=True, labels=True):
    parts = []
    _common(parts, CUT if cut else None, fins=28)
    _stator_core(parts, w.slots, CUT if cut else None, w.kind)
    _stator_winding(parts, w, CUT if cut else None)
    _rotor_core(parts, opacity=0.55)
    Nb = 7 * w.poles if w.poles <= 4 else 5 * w.poles
    m = Mesh()
    for k in range(Nb):
        box(m, k * TAU / Nb + 0.1, 0.5, 0.565, -0.025, 0.025, -0.66, 0.66)
    parts.append(Part(f"회전자 도체 바 ({Nb}개)", "알루미늄·구리 막대. 회전자계가 지나가면 전류가 유도되어 토크를 만듭니다 (다람쥐 쳇바퀴 모양 = 농형).",
                      "#d4a05a", m, explode=(2.2, 0), label=(0, 0.53, 0.3)))
    m = Mesh(); ring(m, 0.44, 0.58, 0.6, 0.68); ring(m, 0.44, 0.58, -0.68, -0.6)
    parts.append(Part("단락환 (엔드 링)", "양 끝에서 모든 도체 바를 하나로 이어 회로를 닫습니다.", "#c98a3e", m,
                      explode=(2.2, 0), label=(0, 0.58, 0.66)))
    m = Mesh(); ring(m, 0.1, 0.18, -1.3, -1.12)
    for k in range(9):
        box(m, k * TAU / 9, 0.18, 0.95, -0.02, 0.02, -1.3, -1.14)
    parts.append(Part("냉각 팬", "축 뒤쪽에 달려 함께 돌며 프레임 바깥으로 바람을 보냅니다 (전폐 외선형).", "#6b7280", m,
                      explode=(-1.4, 0), label=(0, 0.95, -1.22)))
    m = Mesh(); ring(m, 1.04, 1.1, -1.55, -0.98)
    ring(m, 0.12, 1.1, -1.58, -1.54)
    parts.append(Part("팬 커버", "팬을 감싸 손이 닿지 않게 하고 바람을 프레임 쪽으로 모읍니다.", "#9ca3af", m, opacity=0.45,
                      explode=(-2.2, 0), label=(0, -1.1, -1.3)))
    _terminal_box(parts, "단자함 (U·V·W)", "전원 3상이 들어오는 상자. 안의 연결판 배치로 Y 결선 또는 Δ 결선을 고릅니다.")
    return parts


def build_pmsm(w: Winding, cut=True, labels=True):
    parts = []
    _common(parts, CUT if cut else None)
    _stator_core(parts, w.slots, CUT if cut else None, w.kind)
    _stator_winding(parts, w, CUT if cut else None)
    _rotor_core(parts, opacity=0.4, desc="규소강판 회전자. 자석이 철심 속에 묻혀 있어(매입형) 고속에서도 튀어나가지 않습니다.")
    P = w.poles
    for pol, col in ((0, "#e05a55"), (1, "#4a86d8")):
        m = Mesh()
        for j in range(P):
            if j % 2 != pol:
                continue
            c = j * TAU / P
            hl = 0.49 * math.sin(math.pi / P) * 0.8
            box(m, c, 0.45, 0.52, -hl, hl, -0.6, 0.6)
        parts.append(Part(f"영구자석 ({'N' if pol == 0 else 'S'}극)", "네오디뮴 자석. 회전자 자계를 만들며 N·S 가 번갈아 놓입니다 (총 %d극)." % P,
                          col, m, explode=(2.2, 0), label=(0, 0.5 * math.cos(pol * TAU / P), 0.5 * math.sin(pol * TAU / P))))
    m = Mesh(); ring(m, 0.1, 0.32, -1.08, -0.98); ring(m, 0.36, 0.55, -1.1, -0.96)
    parts.append(Part("레졸버 (위치 센서)", "회전자 각도를 재는 센서. 벡터 제어에서 d·q 축을 맞추는 데 씁니다.", "#7c3aed", m,
                      explode=(-1.5, 0), label=(0, 0.55, -1.03)))
    _terminal_box(parts, "커넥터 (U·V·W)", "인버터에서 오는 3상 전원선이 연결되는 곳.")
    return parts


def build_bldc(w: Winding, cut=True, labels=True):
    parts = []
    _common(parts, CUT if cut else None)
    _stator_core(parts, w.slots, CUT if cut else None, w.kind)
    _stator_winding(parts, w, CUT if cut else None)
    _rotor_core(parts, r=(0.2, 0.5), desc="회전자 철심 (요크). 표면 자석의 자속이 지나가는 길입니다.")
    P = w.poles
    for pol, col in ((0, "#e05a55"), (1, "#4a86d8")):
        m = Mesh()
        for j in range(P):
            if j % 2 == pol:
                c = j * TAU / P
                ring(m, 0.5, 0.58, -0.6, 0.6, c - 0.45 * TAU / P, c + 0.45 * TAU / P, 6)
        parts.append(Part(f"표면 자석 ({'N' if pol == 0 else 'S'}극)", f"회전자 표면에 붙인 자석 (총 {P}극). 사다리꼴 역기전력을 만듭니다.",
                          col, m, explode=(2.2, 0), label=(0, 0.58, 0.0) if pol == 0 else None))
    m = Mesh(); ring(m, 0.25, 0.86, 0.72, 0.76)
    for k in range(3):
        box(m, (k * 120 / (P / 2) + 60 / (P / 2)) * math.pi / 180, 0.6, 0.66, -0.03, 0.03, 0.62, 0.72)
    parts.append(Part("홀 센서 기판", "홀 센서 3개(전기각 120° 간격)가 자석 극을 읽어 인버터에 정류 순서를 알려줍니다.", "#2f855a", m,
                      explode=(1.2, 0), label=(0, 0.86, 0.74)))
    _terminal_box(parts, "리드선 (U·V·W·홀)", "3상 전원선과 홀 센서 신호선이 나오는 곳.")
    return parts


def build_dc(poles=2, slots=24, cut=True, labels=True, field_kind="separately"):
    parts = []
    cutw = CUT if cut else None
    L = 0.5
    _common(parts, cutw, L=L, R_frame=(1.0, 1.15), shaft=(-1.6, 1.6), bearing_z=0.95)
    parts[0].name = "계철 (요크·프레임)"
    parts[0].desc = "주극을 붙잡고 자속이 돌아가는 길이 되는 강철 몸체."
    P = poles
    m_core, m_shoe = Mesh(), Mesh()
    for k in range(P):
        a = k * TAU / P
        if in_cut(a, cutw):
            continue
        box(m_core, a, 0.68, 1.0, -0.17, 0.17, -L, L)
        ring(m_shoe, 0.62, 0.68, -L, L, a - 0.55 * math.pi / P, a + 0.55 * math.pi / P, 8)
    parts.append(Part(f"주극 철심 ({P}극)", "계자 코일을 감는 철심. 끝의 극편이 공극 자속을 고르게 퍼뜨립니다.", "#9aa3ad", m_core,
                      explode=(0, 0.45), label=(0, 0.85, L)))
    parts.append(Part("극편", "주극 끝을 넓힌 부분. 자속을 전기자 표면에 고르게 분포시킵니다.", "#7b8794", m_shoe,
                      explode=(0, 0.45)))
    coil = []
    for k in range(P):
        a = k * TAU / P
        if in_cut(a, cutw):
            continue
        c, s = math.cos(a), math.sin(a)
        for turn in range(3):
            r = 0.74 + 0.07 * turn
            t = 0.21; z = L + 0.06
            pts = [(r * c - (-t) * s, r * s + (-t) * c, -z), (r * c - (-t) * s, r * s + (-t) * c, z),
                   (r * c - t * s, r * s + t * c, z), (r * c - t * s, r * s + t * c, -z), (r * c - (-t) * s, r * s + (-t) * c, -z)]
            coil.append(pts)
    fname = {"series": "직권 계자 코일", "compound": "계자 코일 (분권 + 직권)"}.get(field_kind, "계자 코일")
    parts.append(Part(fname, "주극에 감은 코일. 전류가 흐르면 N·S 극이 번갈아 생깁니다 (자속 φ 를 만드는 쪽).",
                      "#c77d3a", lines=coil, width=7, explode=(0, 0.45), label=(0, 0.95, -0.3)))
    m = Mesh()
    for k in range(P):
        a = (k + 0.5) * TAU / P
        if not in_cut(a, cutw):
            box(m, a, 0.66, 1.0, -0.06, 0.06, -L * 0.8, L * 0.8)
    parts.append(Part("보극", "주극 사이(중성축)에 있는 작은 극. 정류 중인 코일에 정류 기전력을 넣어 불꽃을 줄입니다.",
                      "#c3c9cf", m, explode=(0, 0.45)))
    m = Mesh(); ring(m, 0.2, 0.6, -L, L)
    parts.append(Part("전기자 철심", f"슬롯 {slots}개가 있는 회전자 철심. 전기자 코일이 들어갑니다.", "#b9c0c8", m, opacity=0.55,
                      explode=(2.2, 0), label=(0, 0.42, -L)))
    arm = []
    sp, y = TAU / slots, slots // P
    for k in range(slots):           # 중권 코일: 슬롯 k(위층) → 슬롯 k + y(아래층), 정류자편 k → k+1
        a, b = (k + 0.5) * sp, (k + 0.5 + y) * sp
        ts = np.linspace(a, b, 10)
        pts = [(0.56 * math.cos(a), 0.56 * math.sin(a), 0.62)] + [(0.56 * math.cos(a), 0.56 * math.sin(a), -L)]
        pts += [(0.5 * math.cos(t), 0.5 * math.sin(t), -L - 0.1 * math.sin(math.pi * f)) for f, t in zip(np.linspace(0, 1, 10), ts)]
        pts += [(0.48 * math.cos(b), 0.48 * math.sin(b), L), (0.4 * math.cos(b), 0.4 * math.sin(b), 0.62)]
        arm.append(pts)
    parts.append(Part("전기자 코일 (중권)", "슬롯에 들어간 코일. 양 끝이 정류자편에 연결되어 브러시로 전류를 받습니다.",
                      "#d97706", lines=arm, width=3, explode=(2.2, 0), label=(0, 0.56, 0.0)))
    m = Mesh()
    for k in range(slots):
        ring(m, 0.22, 0.34, 0.66, 0.95, k * sp + 0.02, (k + 1) * sp - 0.02, 2)
    parts.append(Part(f"정류자 ({slots}편)", "구리 조각(정류자편)을 운모로 절연해 원통으로 묶은 것. 회전하며 코일 전류 방향을 바꿉니다.",
                      "#c98a3e", m, explode=(2.2, 0), label=(0, 0.34, 0.8)))
    m_b, m_h = Mesh(), Mesh()
    for k in range(P):
        a = (k + 0.5) * TAU / P
        box(m_b, a, 0.34, 0.47, -0.05, 0.05, 0.72, 0.9)
        box(m_h, a, 0.47, 0.62, -0.07, 0.07, 0.7, 0.92)
    parts.append(Part(f"브러시 ({P}개)", "탄소 덩어리. 스프링으로 정류자에 눌려 외부 전원과 회전하는 전기자를 잇습니다.",
                      "#2f2f2f", m_b, explode=(0.4, 0.5), label=(0, 0.5, 0.9)))
    parts.append(Part("브러시 홀더 · 스프링", "브러시를 붙잡고 일정한 힘으로 정류자에 누릅니다.", "#9ca3af", m_h, explode=(0.4, 0.5)))
    _terminal_box(parts, "단자함 (A1·A2·F1·F2)", "전기자 단자(A1·A2)와 계자 단자(F1·F2)가 있는 상자. 결선에 따라 타여자·분권·직권·복권이 됩니다.", r=1.15)
    return parts
