# StockSignals — 개인 퀀트 스크리닝 시스템

한국(KOSPI/KOSDAQ) + 미국(S&P500/나스닥) 대상 스윙 트레이딩 신호 자동 스캔·백테스트·알림 시스템.
위치: `C:\Users\CADCAM\Desktop\Stock\StockSignals`

---

## 0. 설치 / 실행

```powershell
pip install -r requirements.txt

# 실전 신호 스캔 (승률 1위 2개 전략)
python find_entries.py

# 30분 감시봇 (장시간 아니면 자동 스킵)
python watch_signals.py

# 대시보드
streamlit run app.py
```

`config.json`에서 계좌 잔고, 리스크 비율, 거래량/유동성 필터, 텔레그램 봇 토큰을 설정합니다.
텔레그램 토큰이 비어있으면 `send_telegram()`은 콘솔 출력으로 대체 동작합니다.

## 1. 지금 실전에서 도는 것

| 시장 | 전략 | 대상 |
|---|---|---|
| 한국 | 볼린저밴드 하단터치 | KOSPI 시총 100 |
| 미국 | RSI(14) 과매도 (<30) | S&P500 |

- 규칙: 신호일 종가 매수 → 최대 5거래일 보유, 20일선 도달 시 익절 또는 5일째 강제청산
- 신호 조건에 **거래량 확인**(20일 평균 대비 1.5배 이상) + **유동성 필터**(20일 평균 거래대금 한국 5억원/미국 $500만 미만 제외) 필수 적용 — `common.py`의 `build_signals()`에 내장, 모든 스캔에 자동 반영
- `run_daily_scan.ps1`(08:30) + `run_watch_signals.ps1`(30분마다)을 작업 스케줄러에 등록하면 자동 실행, 신호 뜨면 텔레그램 알림 — 등록 명령은 [SCHEDULER_SETUP.md](SCHEDULER_SETUP.md) 참고 (아직 미등록)

## 2. 더블비(Double B) 볼린저밴드 — `backtest_doubleb.py`

- **규칙**: 볼린저밴드 2개 동시 사용 — BB1(20기간, 종가 기준) + BB2(44기간, 시가 기준). 20일선이 5거래일 전보다 위(상승추세)일 때, 종가가 두 밴드 하단을 **동시에** 하회하면 매수
- 한국 쪽은 표본이 작아 통계적 신뢰도가 낮음 — 아직 실전 자동 스캔(`find_entries.py`)에는 편입 안 함

## 3. 전체 유니버스 확장 백테스트 (`backtest_full_universe.py`)

코스피+코스닥 전체 / S&P500+나스닥 전체로 6개 전략(더블비/RSI과매도/BB하단터치/골든크로스/20일신고가/상승음봉) 재검증.

## 4. 요일 효과 분석 (`backtest_weekday.py`, 참고용)

신호 발생 요일별 이후 성과 비교. 일봉 데이터라 장중 시간대 분석은 불가능, 요일 단위만 가능.

## 5. 단타(당일매매) — 결론: 엣지 없음, 폐기

| 카테고리 | 스크립트 |
|---|---|
| 갭매매 | `backtest_daytrade_gap.py` |
| ORB | `backtest_orb_v2.py` |
| 신규 후보 4종 | `backtest_daytrade_candidates.py` |
| VWAP 되돌림 | `backtest_vwap.py` |
| PEAD(실적서프라이즈) | `backtest_pead.py` |

FinanceDataReader가 일봉만 제공하므로 각 스크립트는 당일 O/H/L/C 기반 근사 시뮬레이션을 사용합니다(상세 주석 참고). 결론은 전부 수수료 감안 시 무의미 — 초대형주·초단기 구간은 이미 차익거래로 소진된 효율적 시장.

## 6. 자동화 구성

- **Windows 작업 스케줄러** (등록 가이드: [SCHEDULER_SETUP.md](SCHEDULER_SETUP.md))
  - `DailyRisingBearishScan`: 매일 08:30 평일, 전체 스캔 + `history/`에 날짜별 백업
  - `SignalWatch30min`: 30분마다 상시 실행, 스크립트 내부에서 장시간(한국 09:00~15:30 / 미국 22:00~06:30) 아니면 즉시 스킵
  - `FlushPendingNotifications`: 매일 06:00, 조용한시간(23:00~06:00) 큐 일괄 발송
- **텔레그램 봇** — 새 신호만 알림(중복 방지: `notified_state.json`), 조용한시간엔 큐잉 후 06:00에 일괄 발송(`pending_notifications.json`). `config.json`에 `bot_token`/`chat_id` 입력 필요
- **대시보드**: `streamlit run app.py` → `localhost:8501`. 다른 기기에서 접속하려면 방화벽 인바운드 규칙(예: `StockSignals Dashboard`, TCP 8501)을 직접 추가하세요

### 알려진 버그/주의사항
- `win11toast`가 스케줄러의 비대화형 세션에서 무한 대기 → 텔레그램 전송까지 막을 수 있음. 대응: 텔레그램 먼저 보내고 toast는 데몬 스레드로 분리(`common.py`의 `notify_new_signals()`)
- PowerShell 래퍼(`run_*.ps1`)는 `$env:PYTHONIOENCODING="utf-8"` 안 하면 로그에 한글 깨짐 — 이미 적용됨
- Streamlit 실행 중에 `common.py`/`app.py` 수정하면 재시작 전까지 반영 안 됨(모듈 캐시) — ImportError 원인 1순위
- KRX 공식 사이트는 로그인 필수로 바뀌어(2026-08~) pykrx/직접 스크래핑이 막힘 — FinanceDataReader(네이버 기반)로 전량 우회
- `pd.read_html(url)` 직접 호출 시 인증서 오류가 나는 환경이 있음 — 필요 시 `requests.get()` 후 `io.StringIO(html)`로 우회

## 7. 파일 구조

```
common.py                       # 공통 유틸: build_signals(), position_size(), is_liquid(), send_telegram(), config
backtest_core.py                 # 스윙 백테스트 공용 엔진 (신호→보유→청산 시뮬레이션)
backtest_daytrade_core.py         # 단타 백테스트 공용 엔진 (당일 O/H/L/C 근사)
config.json                        # 계좌/리스크/거래량/텔레그램 설정 (대시보드에서도 수정 가능)
find_entries.py                     # 실전 2개 전략 스캔 (승률 1위만)
scan_signals.py                      # 6개 전략 전체 스캔 (전략 선택 가능)
scan_rising_bearish_kr/us.py           # 전체 시장 상승음봉 스캔
backtest_swing.py                       # 기존 5개 전략 백테스트 (KOSPI100/S&P500)
backtest_doubleb.py                      # 더블비 볼린저밴드 백테스트
backtest_full_universe.py                 # 전체시장(코스피+코스닥, S&P500+나스닥) 6개 전략 백테스트
backtest_weekday.py                        # 요일별 성과 분석
backtest_daytrade_gap.py, backtest_orb_v2.py, backtest_daytrade_candidates.py,
backtest_vwap.py, backtest_pead.py          # 단타(전부 기각됨)
watch_signals.py                             # 30분 감시봇
flush_pending.py                              # 조용한시간 큐 일괄발송 (06:00)
app.py                                         # Streamlit 대시보드
export_excel.py                                 # 결과 엑셀 내보내기
run_daily_scan.ps1, run_watch_signals.ps1,
run_flush_pending.ps1                            # 작업 스케줄러용 PowerShell 래퍼
SCHEDULER_SETUP.md                                # schtasks 등록 명령 가이드
```

---
*최종 정리: 2026-09-03*
