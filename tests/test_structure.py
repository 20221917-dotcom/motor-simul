"""권선 배치·권선계수·3D 구조·전개도 검증."""
import math

import numpy as np
import pytest

from motors.winding import concentrated, distributed
from ui import structure3d as s3
from ui import winding_diagrams as wd


def _axes(w):
    pp = w.poles // 2
    out = []
    for ph in range(3):
        s = sum(c.sign * np.exp(1j * pp * c.angle) for c in w.conductors if c.phase == ph)
        out.append(np.degrees(np.angle(s)) % 360)
    return out


@pytest.mark.parametrize("w", [distributed(2, 2), distributed(4, 2), distributed(4, 3, 7), distributed(8, 1),
                               concentrated(4), concentrated(8)])
def test_three_phases_are_balanced_120_deg_apart(w):
    ax = _axes(w)
    assert ax == pytest.approx([90, 210, 330], abs=1e-6)      # ⊙ 도체 무게중심 = 자축 + 90°
    assert w.slots == (3 * w.poles * int(w.q) if w.kind == "distributed" else 3 * w.poles // 2)
    for ph in range(3):                                          # 상마다 도체 수 같음
        assert sum(1 for c in w.conductors if c.phase == ph) == len(w.conductors) // 3


@pytest.mark.parametrize("q,kd", [(1, 1.0), (2, 0.9659), (3, 0.9598)])
def test_distribution_factor_textbook(q, kd):
    assert distributed(4, q).kd == pytest.approx(kd, abs=1e-4)


def test_short_pitch_factor_and_concentrated_factor():
    w = distributed(4, 3, 7)
    assert w.kp == pytest.approx(math.sin(7 / 9 * math.pi / 2))
    assert w.kw == pytest.approx(w.kd * w.kp)
    assert concentrated(8).kw == pytest.approx(math.sqrt(3) / 2)


@pytest.mark.parametrize("build", [lambda: s3.build_induction(distributed(4, 2)), lambda: s3.build_pmsm(concentrated(8)),
                                   lambda: s3.build_bldc(concentrated(8)), lambda: s3.build_dc(4)])
def test_3d_models_have_named_parts_and_explode_frames(build):
    parts = build()
    assert len(parts) >= 10 and all(p.name and p.desc for p in parts)
    fig = s3.figure(parts)
    assert len(fig.frames) == 12
    # 분해하면 회전자 쪽 부품(축)이 축 방향으로 빠져나옴
    shaft0 = next(t for t in fig.data if t.name.startswith("축"))
    shaft1 = next(t for t in fig.frames[-1].data if getattr(t, "name", "").startswith("축"))
    assert min(shaft1.x) > min(shaft0.x) + 2.0


def test_diagrams_build():
    for f in (wd.development(distributed(4, 2)), wd.development(concentrated(8)), wd.connection(distributed(4, 2), "Y"),
              wd.connection(distributed(4, 2), "D"), wd.terminal_box("Y"), wd.terminal_box("D"), wd.bldc_connection(),
              wd.dc_armature(4, 12, "lap"), wd.dc_armature(4, 13, "wave")):
        assert f.to_json()
