# 전동기 학습용 시뮬레이터

타여자·분권·직권·복권(가동/차동, 장분권) DC 전동기의 원리, 정상상태 특성, 동특성, 속도 제어를
파라미터를 바꿔 가며 확인하는 Streamlit 앱입니다.

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
| `ui/` | 파라미터 입력 자동 생성, 결선도·블록도, 탭별 화면 |
| `ui/pages/` | 메뉴 페이지: DC 시뮬레이터, 교류 전동기(준비 중), 관련 개념 |
| `ui/realtime/` | 브라우저에서 도는 실시간 시뮬레이터 (engine.js: 전동기·제어기, charts.js: 흘러가는 그래프, structure.js: 전동기 그림, blocks.js + editor.html: 제어 블록 편집기) |
| `tests/` | pytest 검증 |

## 새 전동기 추가 방법
1. `motors/<계열>/xxx.py` 에 `MotorModel`(DC 는 `DCMotor`) 을 상속한 클래스를 만들고 `@register`
2. `param_specs()` 로 입력 파라미터 선언 → 파라미터 입력 영역은 자동 생성
3. DC 여자 방식은 `kphi`, `field_ss`, `R_arm`, `line_current`, `input_power`, `losses`,
   `derivatives` 만 구현하면 정상상태·곡선·동특성이 공통 코드로 동작

## 웹사이트 (Streamlit Community Cloud)
share.streamlit.io 에서 이 저장소, 브랜치 `main`, 파일 `app.py` 로 배포합니다.
`main` 에 올라온 변경은 사이트에 자동 반영됩니다.

## 실시간 모드
원리 탭의 단면 애니메이션과 제어 탭의 "실시간 제어 실험"은 계산을 브라우저(JavaScript)에서 합니다.
슬라이더·게인을 바꾸면 서버 왕복 없이 현재 상태에서 바로 반응하고, ⟲ 버튼으로 정지 상태부터 다시 시작합니다.
`engine.js` 는 파이썬 모델과 같은 식이며 `tests/test_js_engine.py` 가 두 결과를 비교합니다 (Node.js 필요).

## 화면 구성
- 왼쪽 메뉴: **직류 전동기** / **교류 전동기**(준비 중) / **관련 개념**(전자기 기초, 정류 원리, 자기회로와 Kφ, 제어 기초, 기호와 단위)
- 각 시뮬레이터 페이지 위쪽에 파라미터 설정, 아래에 탭
- 원리 탭 실시간 화면의 '보기': 단순 모형 / 실제 구조 단면(2·4극) / 실제 구조 측면 / 단면 + 측면

## 제어 블록 편집기
메뉴 **직류 전동기 → 제어 블록 편집기**. 신호원·합산점·게인·리미터·적분기·필터·P/PI/PID·초퍼·DC 전동기·스코프 블록을
끌어다 이어 제어 구조를 만들고 실시간으로 돌립니다. 템플릿: 이중 루프, 전류 루프만, 속도 루프만, P 제어, 개루프, 위치 제어.
만든 구조는 브라우저에 자동 저장되고 JSON 으로 내보내기/가져오기 할 수 있습니다. 엔진 검증: `tests/test_js_blocks.py`.
