"""앱 전체 스모크 테스트: 모든 전동기 종류에서 4개 탭이 예외 없이 그려지는지."""
import pathlib
import pytest
from streamlit.testing.v1 import AppTest

APP = str(pathlib.Path(__file__).resolve().parents[1] / "app.py")


def _run(choice, extra=None):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["motor_choice"] = choice
    for k, v in (extra or {}).items():
        at.session_state[k] = v
    at.run()
    return at


@pytest.mark.parametrize("choice", ["타여자", "분권", "직권", "복권"])
def test_all_tabs_render(choice):
    at = _run(choice)
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.tabs) == 4


def test_differential_compound_with_comparisons():
    at = _run("복권", {"p_sigma": "차동 복권", "dy_cmp": ["타여자", "직권"],
                       "cmp_차동 복권": True})
    assert not at.exception, [e.value for e in at.exception]
    # 불안정 경고가 떠야 한다
    assert any("불안정" in e.value for e in at.error)


def test_invalid_parameter_stops_with_error():
    at = _run("타여자", {"p_Ra": -1.0})
    assert not at.exception
    assert any("0보다 커야" in e.value for e in at.error)
