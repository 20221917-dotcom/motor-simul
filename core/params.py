"""사이드바 입력 파라미터 정의.

각 전동기 모델이 ParamSpec 목록을 선언하면 UI가 이를 읽어
입력 위젯을 자동으로 만든다. 새 전동기를 추가할 때 UI 코드를 고칠 필요가 없다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ParamSpec:
    key: str            # 내부 이름 (SI 값의 dict 키)
    symbol: str         # 화면 기호, 예: "Ra"
    label: str          # 한국어 이름
    unit: str           # 화면 표시 단위
    default: float      # 화면 단위 기준 기본값
    group: str          # 사이드바 그룹 이름
    scale: float = 1.0  # 화면값 × scale = SI 값 (예: mH → H 는 1e-3)
    positive: bool = True    # True: 0 이하면 오류
    allow_zero: bool = False  # positive=True 이면서 0은 허용 (예: B, Rfx)
    step: float | None = None
    help: str = ""
    ui_key: str = ""          # 화면 위젯 키 (같은 기호라도 전동기마다 기본값이 다를 때 구분)
    choices: tuple = ()       # 선택형 파라미터: ((표시 이름, 값), ...)

    @property
    def widget_key(self) -> str:
        return f"p_{self.ui_key or self.key}"

    def default_label(self) -> str:
        for label, v in self.choices:
            if v == self.default:
                return label
        return self.choices[0][0]

    def to_si(self, display_value: float) -> float:
        return display_value * self.scale

    def check(self, si_value: float) -> str | None:
        """물리적으로 말이 안 되는 값이면 오류 메시지를 돌려준다."""
        if not self.positive or self.choices:
            return None
        if self.allow_zero and si_value < 0:
            return f"{self.symbol}({self.label})는 0 이상이어야 합니다."
        if not self.allow_zero and si_value <= 0:
            return f"{self.symbol}({self.label})는 0보다 커야 합니다."
        return None
