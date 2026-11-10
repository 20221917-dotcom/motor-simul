"""전동기 모델 등록소. 여기 등록된 모델만 화면 상단 선택 목록에 나타난다.

모델 모듈을 import 하면 @register 데코레이터가 등록을 수행한다.
Streamlit Cloud 처럼 서버가 다시 시작되지 않은 채 코드만 갱신되면 이 등록소가 예전 목록을
들고 있을 수 있으므로, 찾는 키가 없으면 해당 모듈을 그 자리에서 불러온다.
"""
import importlib

_REGISTRY: dict[str, type] = {}

# 키 → 모델이 들어 있는 모듈 (새 모델을 추가하면 여기에도 적어 둔다)
_MODULES = {
    "dc_separately": "motors.dc.separately",
    "dc_shunt": "motors.dc.shunt",
    "dc_series": "motors.dc.series",
    "dc_compound": "motors.dc.compound",
    "bldc": "motors.bldc.model",
    "induction": "motors.ac.induction",
    "pmsm": "motors.ac.pmsm",
}


def register(cls):
    _REGISTRY[cls.key] = cls
    return cls


def _ensure(keys=None):
    for key in (keys or _MODULES):
        if key not in _REGISTRY and key in _MODULES:
            importlib.import_module(_MODULES[key])


def all_models(family: str | None = None) -> list[type]:
    _ensure()
    order = list(_MODULES)
    models = sorted(_REGISTRY.values(), key=lambda c: order.index(c.key) if c.key in order else len(order))
    return [c for c in models if family is None or c.family == family]


def get(key: str) -> type:
    if key not in _REGISTRY:
        _ensure([key])
    if key not in _REGISTRY:
        raise KeyError(f"등록되지 않은 전동기 모델: {key!r} (motors/registry.py 의 _MODULES 를 확인하세요)")
    return _REGISTRY[key]


_ensure()
