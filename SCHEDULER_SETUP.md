# Windows 작업 스케줄러 등록 가이드

스크립트만 준비된 상태이며, 아래 `schtasks` 명령은 아직 실행되지 않았습니다.
관리자 권한 PowerShell에서 필요한 것만 골라 직접 실행하거나, 실행을 요청해 주세요.

## 1. DailyRisingBearishScan — 매일 08:30 평일, 전체 스캔 + history 백업

```powershell
schtasks /create /tn "DailyRisingBearishScan" /tr "powershell.exe -ExecutionPolicy Bypass -File `"C:\Users\CADCAM\Desktop\Stock\StockSignals\run_daily_scan.ps1`"" /sc weekly /d MON,TUE,WED,THU,FRI /st 08:30 /rl HIGHEST
```

## 2. SignalWatch30min — 30분마다 상시 실행 (내부에서 장시간 아니면 스킵)

```powershell
schtasks /create /tn "SignalWatch30min" /tr "powershell.exe -ExecutionPolicy Bypass -File `"C:\Users\CADCAM\Desktop\Stock\StockSignals\run_watch_signals.ps1`"" /sc minute /mo 30 /rl HIGHEST
```

## 3. FlushPendingNotifications — 매일 06:00, 조용한시간 큐 일괄 발송

```powershell
schtasks /create /tn "FlushPendingNotifications" /tr "powershell.exe -ExecutionPolicy Bypass -File `"C:\Users\CADCAM\Desktop\Stock\StockSignals\run_flush_pending.ps1`"" /sc daily /st 06:00 /rl HIGHEST
```

## 4. RecommendationsWatch — 30분마다 상시 실행 (6개 전략 통합, 이미 등록됨 ✅)

실전 5개 전략(볼린저밴드 하단터치/RSI과매도/골든크로스/20일신고가돌파/상승음봉) + 더블비를 한 번에 스캔해
매수가/목표가/손절가/손익비까지 계산. KOSPI100+S&P500(600종목) fetch를 6개 전략이 공유해 소요시간은
단일 전략 스캔과 거의 동일(약 2.9~3분) — 30분 주기면 약 10배 여유. 2026-09-04에 아래 명령으로 등록 완료
(이전에 더블비 전용으로 썼던 `DoubleBWatch`는 중복 스캔을 피하기 위해 삭제하고 이걸로 대체):

```powershell
schtasks /delete /tn "DoubleBWatch" /f
schtasks /create /tn "RecommendationsWatch" /tr "powershell.exe -ExecutionPolicy Bypass -File `"C:\Users\CADCAM\Desktop\Stock\StockSignals\run_watch_recommendations.ps1`"" /sc minute /mo 30 /f
```

## 5. TrackRecommendations — 매일 07:00 (성과추적 + 구글드라이브 동기화, 이미 등록됨 ✅)

추천종목이 목표가/손절가에 도달했는지 확인하고 `recommendations_log.csv`를 갱신, `service_account.json`이
설정돼 있으면(DRIVE_SETUP.md 참고) 구글 드라이브 "주식" 폴더의 추적 시트도 자동 동기화. 한국장(15:30)·
미국장(06:00 KST 근처) 둘 다 마감된 이후인 07:00에 실행되도록 2026-09-04에 등록 완료:

```powershell
schtasks /create /tn "TrackRecommendations" /tr "powershell.exe -ExecutionPolicy Bypass -File `"C:\Users\CADCAM\Desktop\Stock\StockSignals\run_track_recommendations.ps1`"" /sc daily /st 07:00 /f
```

## 확인 / 삭제

```powershell
schtasks /query /tn "DailyRisingBearishScan"
schtasks /delete /tn "DailyRisingBearishScan" /f
```

## 참고
- `run_11toast`(Windows 토스트 알림)는 비대화형 스케줄러 세션에서 무한 대기하는 버그가 있어, `common.py`의 `notify_new_signals()`에서 텔레그램을 먼저 보내고 toast는 데몬 스레드로 분리해 두었습니다.
- 로그는 `logs/` 폴더에 쌓입니다. `PYTHONIOENCODING=utf-8` 없이 실행하면 한글이 깨지므로 각 `.ps1`에 이미 설정되어 있습니다.
