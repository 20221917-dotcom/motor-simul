"""단위 변환과 표시용 포맷 함수. 내부 계산은 항상 SI 단위."""
import math

RAD_S_TO_RPM = 60.0 / (2.0 * math.pi)
RPM_TO_RAD_S = 1.0 / RAD_S_TO_RPM


def to_rpm(omega):
    """rad/s → rpm (numpy 배열도 가능)"""
    return omega * RAD_S_TO_RPM


def to_rad_s(rpm):
    """rpm → rad/s"""
    return rpm * RPM_TO_RAD_S


def fmt(value, unit="", digits=3):
    """유효숫자 기준으로 값 + 단위 문자열을 만든다."""
    if value is None:
        return "—"
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return "∞" if math.isinf(value) else "—"
    a = abs(value)
    if a != 0 and (a >= 1e5 or a < 1e-3):
        s = f"{value:.{digits - 1}e}"
    elif a >= 100:
        s = f"{value:,.1f}"
    elif a >= 10:
        s = f"{value:.2f}"
    else:
        s = f"{value:.3f}"
    return f"{s} {unit}".strip()
