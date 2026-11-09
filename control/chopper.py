"""초퍼 평균값 모델.

스위칭 리플은 무시하고 한 주기 평균 전압만 다룬다 (va = d·Vdc).
- 1상한 초퍼 (강압형): 0 ≤ va ≤ Vdc, 전류도 Ia ≥ 0 만 가능 → 역회전·회생제동 불가
- 4상한 초퍼 (H-브리지): −Vdc ≤ va ≤ Vdc, 전류 양방향
"""


class Chopper:
    def __init__(self, vdc, quadrants=4):
        self.vdc = vdc
        self.quadrants = quadrants

    @property
    def v_min(self):
        return -self.vdc if self.quadrants == 4 else 0.0

    @property
    def v_max(self):
        return self.vdc

    @property
    def current_unidirectional(self):
        return self.quadrants == 1

    def limit(self, v_cmd):
        return min(max(v_cmd, self.v_min), self.v_max)
