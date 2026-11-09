"""출력 제한과 안티와인드업이 있는 이산 PI 제어기."""


class PI:
    def __init__(self, kp, ki, lo, hi, anti_windup=True):
        self.kp, self.ki = kp, ki
        self.lo, self.hi = lo, hi
        self.anti_windup = anti_windup
        self.xi = 0.0  # 적분기 상태

    def step(self, err, dt, ff=0.0):
        """한 샘플 계산. (제한된 출력, 제한 전 출력) 을 돌려준다."""
        u_unsat = self.kp * err + self.xi + ff
        u = min(max(u_unsat, self.lo), self.hi)
        if self.anti_windup:
            # 조건부 적분(clamping): 포화된 쪽으로 더 밀어붙이는 오차면 적분을 멈춘다
            saturating = (u_unsat > self.hi and err > 0) or (u_unsat < self.lo and err < 0)
            if not saturating:
                self.xi += self.ki * err * dt
        else:
            self.xi += self.ki * err * dt
        return u, u_unsat
