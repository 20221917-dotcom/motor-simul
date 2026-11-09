"""여자 방식 비교용 도우미: 비교 대상 목록과 모델 생성."""
from motors import registry
from ui.sidebar import params_from_session

# (화면 이름, 모델 키, 덮어쓸 파라미터)
VARIANTS = [
    ("타여자", "dc_separately", {}),
    ("분권", "dc_shunt", {}),
    ("직권", "dc_series", {}),
    ("가동 복권", "dc_compound", {"sigma": 1.0}),
    ("차동 복권", "dc_compound", {"sigma": -1.0}),
]
COLORS = {"타여자": "#264653", "분권": "#2a9d8f", "직권": "#e76f51",
          "가동 복권": "#8e44ad", "차동 복권": "#e9a23b"}


def label_of(model):
    """현재 모델의 비교용 이름 (복권은 가동/차동까지)."""
    return getattr(model, "variant", model.name)


def build(label, current_model=None, current_params=None):
    """비교 대상 모델. 현재 선택된 종류면 사이드바 값을 그대로 쓴다."""
    _, key, over = next(v for v in VARIANTS if v[0] == label)
    cls = registry.get(key)
    if current_model is not None and label_of(current_model) == label:
        return current_model
    if current_model is not None and current_model.key == key:
        p = dict(current_params)
        p.update(over)
    else:
        p = params_from_session(cls, over)
    return cls(p)
