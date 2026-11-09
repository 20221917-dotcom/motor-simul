"""모든 전동기 모델이 따르는 공통 인터페이스.

DC 전동기뿐 아니라 나중에 유도전동기, PMSM, BLDC 등도 이 클래스를 상속한다.
UI와 시뮬레이션 엔진은 이 인터페이스만 사용하므로, 새 모델을 추가할 때
UI 코드는 거의 건드리지 않아도 된다.
"""
from abc import ABC, abstractmethod
import numpy as np
from core.params import ParamSpec


class MotorModel(ABC):
    family: str = ""         # 계열: "DC", 나중에 "IM", "PMSM" ...
    key: str = ""            # 고유 키: "dc_separately" 등
    name: str = ""           # 화면 이름
    state_names: list[str] = []
    state_labels: dict[str, str] = {}

    def __init__(self, params: dict):
        self.p = dict(params)

    # ---- 파라미터 -------------------------------------------------------
    @classmethod
    @abstractmethod
    def param_specs(cls) -> list[ParamSpec]:
        """사이드바에 표시할 파라미터 목록."""

    @classmethod
    def default_params(cls) -> dict:
        return {s.key: s.to_si(s.default) for s in cls.param_specs()}

    def validate(self) -> list[str]:
        """오류 메시지 목록 (비어 있으면 정상)."""
        errs = []
        for s in self.param_specs():
            msg = s.check(self.p[s.key])
            if msg:
                errs.append(msg)
        return errs

    # ---- 동특성 ----------------------------------------------------------
    @abstractmethod
    def default_inputs(self):
        """사이드바 값으로 만든 입력 dataclass."""

    @abstractmethod
    def initial_state(self, u) -> np.ndarray:
        """정지 상태 초기값."""

    @abstractmethod
    def derivatives(self, t, x, u) -> np.ndarray:
        """dx/dt"""

    @abstractmethod
    def outputs(self, X, u) -> dict:
        """상태 배열 X (상태 수 × N) → 이름별 신호 배열 dict."""

    # ---- 정상상태 --------------------------------------------------------
    @abstractmethod
    def steady_state(self, u):
        """운전점. 없으면 None."""
