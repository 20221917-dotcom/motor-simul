"""전동기 모델 등록소. 여기 등록된 모델만 화면 상단 선택 목록에 나타난다."""
_REGISTRY: dict[str, type] = {}


def register(cls):
    _REGISTRY[cls.key] = cls
    return cls


def all_models(family: str | None = None) -> list[type]:
    return [c for c in _REGISTRY.values() if family is None or c.family == family]


def get(key: str) -> type:
    return _REGISTRY[key]


def _load_builtin():
    # 모듈을 import 하면 @register 데코레이터가 등록을 수행한다
    import motors.dc  # noqa: F401


_load_builtin()
