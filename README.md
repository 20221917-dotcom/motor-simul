# DC 전동기 학습용 시뮬레이터

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py      # 브라우저에서 http://localhost:8501
pytest -q                 # 해석해 비교 테스트
```

## 구조
| 폴더 | 내용 |
|---|---|
| `core/` | 파라미터 정의(ParamSpec), 단위 변환, 이벤트 구간별 solve_ivp 시뮬레이션 엔진 |
| `motors/` | `MotorModel` 공통 인터페이스, 등록소(registry), `dc/` DC 전동기 모델 |
| `control/` | PI(안티와인드업), 초퍼 평균값 모델, 게인 추천, 이중 루프 속도 제어 |
| `concepts/` | 정류자 토크 파형, 단면 애니메이션 |
| `ui/` | 사이드바 자동 생성, 결선도·블록도, 탭별 화면 |
| `tests/` | pytest 검증 |

## 새 전동기 추가 방법
1. `motors/<계열>/xxx.py` 에 `MotorModel`(DC 는 `DCMotor`) 을 상속한 클래스를 만들고 `@register`
2. `param_specs()` 로 입력 파라미터 선언 → 사이드바는 자동 생성
3. DC 여자 방식은 `kphi`, `field_ss`, `R_arm`, `line_current`, `input_power`, `losses`,
   `derivatives` 만 구현하면 정상상태·곡선·동특성이 공통 코드로 동작
