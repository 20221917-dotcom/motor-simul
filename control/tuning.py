"""대역폭으로 PI 게인 추천값 계산.

전류 루프: 플랜트 1/(La·s + Ra) 의 극을 PI 영점으로 상쇄
    Kp_i = ωci·La,  Ki_i = ωci·Ra  →  폐루프 ≈ ωci/(s + ωci)
속도 루프: 전류 루프를 1 로 보고 플랜트 Kφ/(J·s)
    Kp_ω = ωcs·J/Kφ,  Ki_ω = Kp_ω·ωcs/m  (영점을 교차주파수의 1/m 에 둠, m=4 → 위상여유 약 76°)
"""


def current_gains(La, Ra, wci):
    return wci * La, wci * Ra


def speed_gains(J, kphi, wcs, m=4.0):
    kp = wcs * J / kphi
    return kp, kp * wcs / m
