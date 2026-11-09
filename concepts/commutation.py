"""코일·정류자에 따른 토크 파형.

균일 자계 B(+x 방향, N극→S극) 안에서 각도 θ 위치의 코일 변이 받는 토크는
    T ∝ cos θ        (θ = 0 : 코일 변이 자극 정면, θ = ±90° : 중성축)
- 정류자 없음 : 전류 방향이 고정 → T ∝ cos θ, 한 바퀴 평균 0 (진동만 함)
- 코일 1개 + 정류자 : 중성축에서 전류가 반전 → T ∝ |cos θ|, 평균 2/π, 리플 100 %
- 코일 N개 (π/N 간격) + 정류자 : T ∝ (1/N)·Σ|cos(θ − kπ/N)|, 리플이 급격히 감소
"""
import numpy as np


def torque_waveforms(theta, n_coils):
    no_comm = np.cos(theta)
    single = np.abs(np.cos(theta))
    multi = np.mean([np.abs(np.cos(theta - k * np.pi / n_coils)) for k in range(n_coils)],
                    axis=0)
    return {"no_comm": no_comm, "single": single, "multi": multi}


def ripple_percent(x):
    m = np.mean(x)
    return float((np.max(x) - np.min(x)) / m * 100.0) if m > 1e-12 else float("inf")


def conductor_sign(phi):
    """각도 phi 위치 도체의 전류 방향: +1 = ⊙(지면에서 나옴), −1 = ⊗(지면으로 들어감).
    + 브러시(오른쪽)에 닿은 정류자편에 연결된 도체 = 오른쪽 반 → ⊙."""
    return np.where(np.cos(phi) >= 0, 1.0, -1.0)
