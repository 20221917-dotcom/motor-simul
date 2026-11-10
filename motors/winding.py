"""3상 고정자 권선 배치 (분포권 / 집중권) — 단면 그림, 3D 구조, 권선 전개도가 함께 쓴다.

좌표 약속 (모든 그림 공통, 진폭 불변 αβ 변환과 같은 방향)
- 기계각 θ, 전기각 θe = (P/2)·θ. A상 자축 = 전기각 0°, B상 120°, C상 240°.
- 도체 전류가 지면에서 나오면(⊙) +1, 들어가면(⊗) −1.
- 한 상의 전류가 양(+)이면 그 상 자축에서 전기각 +90° 쪽 도체가 ⊙, −90° 쪽이 ⊗ (오른손 법칙으로 자축 방향 기자력).

분포권 (매극 매상 슬롯 수 q 가 정수, 60° 상대):
    슬롯 k 의 전기각 αk = (k + ½)·(P/2)·360°/S,  S = 3·P·q
    상대: [0,60) B−, [60,120) A+, [120,180) C−, [180,240) B+, [240,300) A−, [300,360) C+
    2층권 단절권(코일 피치 y < 극피치 S/P)이면 아래층은 위층을 (S/P − y) 슬롯 밀어 놓은 것과 같다.
집중권 (이빨마다 코일, S = 3·P/2 → q = ½):
    이빨 k 의 전기각 = k·(P/2)·360°/S 에 가장 가까운 상 자축(± 부호)을 고른다 (슬롯 별 그림 star of slots).
"""
from dataclasses import dataclass, field
import math

BELTS = [(1, -1), (0, 1), (2, -1), (1, 1), (0, -1), (2, 1)]   # (상, 부호): B−, A+, C−, B+, A−, C+
PHASE_NAMES = ["A", "B", "C"]


@dataclass
class Conductor:
    slot: int          # 슬롯 번호 (0 부터)
    angle: float       # 기계각 [rad] (그림 위치)
    layer: int         # 분포권: 0 = 위층(공극 쪽), 1 = 아래층 / 집중권: 0 = 슬롯 왼쪽, 1 = 오른쪽
    phase: int         # 0 = A, 1 = B, 2 = C
    sign: int          # +1: 상전류 > 0 일 때 ⊙, −1: ⊗


@dataclass
class Coil:
    phase: int
    sign: int          # 코일 '들어가는 변' 의 부호
    slot_a: int        # 들어가는 변 슬롯
    slot_b: int        # 나오는 변 슬롯
    pole: int          # 몇 번째 극 (그룹)


@dataclass
class Winding:
    kind: str                  # "distributed" | "concentrated"
    poles: int
    slots: int
    q: float
    pitch: int                 # 코일 피치 [슬롯 수]
    conductors: list = field(default_factory=list)
    coils: list = field(default_factory=list)
    kd: float = 1.0            # 분포계수
    kp: float = 1.0            # 단절(피치)계수

    @property
    def kw(self):
        return self.kd * self.kp

    @property
    def pole_pitch(self):
        return self.slots / self.poles

    @property
    def slot_pitch_elec_deg(self):
        return (self.poles / 2) * 360.0 / self.slots

    def to_js(self):
        """실시간 그림용 간단 표현."""
        return {"kind": self.kind, "poles": self.poles, "slots": self.slots,
                "cond": [[round(c.angle, 6), c.layer, c.phase, c.sign] for c in self.conductors]}


def _belt(alpha_deg):
    return BELTS[int((alpha_deg % 360.0) // 60.0)]


def distributed(poles: int, q: int = 2, pitch: int | None = None) -> Winding:
    pp = poles // 2
    S = 3 * poles * q
    tau = S // poles                             # 극피치 [슬롯]
    y = tau if pitch is None else max(1, min(int(pitch), tau))
    w = Winding("distributed", poles, S, float(q), y)
    gam = pp * 2 * math.pi / S                   # 슬롯 피치 [전기 rad]
    half = (tau - y) * gam / 2                   # 단절권: 두 층을 반씩 반대로 밀어 자축을 그대로 둠
    top = [_belt(math.degrees((k + 0.5) * gam - half)) for k in range(S)]
    bot = [_belt(math.degrees((k + 0.5) * gam + half)) for k in range(S)]
    for k in range(S):
        ang = (k + 0.5) * 2 * math.pi / S
        w.conductors.append(Conductor(k, ang, 0, *top[k]))
        w.conductors.append(Conductor(k, ang, 1, *bot[k]))
    # 코일: 위층 슬롯 j → 아래층 슬롯 j + y (되돌아오는 변은 반대 부호)
    for k in range(S):
        ph, sg = top[k]
        w.coils.append(Coil(ph, sg, k, (k + y) % S, int(k // tau)))
    w.kp = math.sin(y / tau * math.pi / 2)
    _finish(w)
    return w


def _finish(w: Winding):
    """권선계수 = A상 도체 전기각 벡터 합의 크기 / 도체 수 (기본파). 분포계수 = 권선계수 / 피치계수."""
    pp = w.poles // 2
    cs = [c for c in w.conductors if c.phase == 0]
    s = sum(c.sign * complex(math.cos(pp * c.angle), math.sin(pp * c.angle)) for c in cs)
    kw = abs(s) / max(len(cs), 1)
    w.kd = kw / w.kp if w.kp > 0 else 0.0


def concentrated(poles: int, slots: int | None = None) -> Winding:
    pp = poles // 2
    S = slots or (3 * poles // 2)
    w = Winding("concentrated", poles, S, S / (3 * poles), 1)
    axes = [(0, 1, 0.0), (0, -1, 180.0), (1, 1, 120.0), (1, -1, 300.0), (2, 1, 240.0), (2, -1, 60.0)]
    teeth = []
    for k in range(S):
        e = (k * pp * 360.0 / S) % 360.0
        ph, sg, _ = min(axes, key=lambda a: abs(((e - a[2] + 180) % 360) - 180))
        teeth.append((ph, sg))
    for k in range(S):                           # 슬롯 k: 이빨 k 와 k+1 사이
        ang = (k + 0.5) * 2 * math.pi / S
        ph, sg = teeth[k]
        w.conductors.append(Conductor(k, ang, 0, ph, sg))          # 이빨 k 코일의 (+90° 쪽) 변
        ph2, sg2 = teeth[(k + 1) % S]
        w.conductors.append(Conductor(k, ang, 1, ph2, -sg2))       # 이빨 k+1 코일의 반대 변
        w.coils.append(Coil(ph, sg, (k - 1) % S, k, k))            # 이빨 k 를 감는 코일 (슬롯 k−1 ↔ k)
    w.kp = abs(math.sin(pp * math.pi / S))       # 코일 폭 = 이빨 하나 (전기각 pp·2π/S)
    _finish(w)
    return w


def make(kind: str, poles: int, q: int = 2, pitch: int | None = None) -> Winding:
    return concentrated(poles) if kind.startswith("conc") or kind == "집중권" else distributed(poles, q, pitch)


def phase_current_at(w: Winding, i3, conductor: Conductor):
    """도체 전류 (⊙ 양수)."""
    return conductor.sign * i3[conductor.phase]
