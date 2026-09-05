# Windows 작업 스케줄러 등록 가이드

⚠️ **2026-09-06부터 `RecommendationsWatch`와 `TrackRecommendations`는 로컬 스케줄러 대신
GitHub Actions(클라우드)에서 돕니다** — PC가 꺼져 있어도 계속 작동하도록 이전했습니다.
자세한 내용은 [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) 참고. 이 두 로컬 작업은
중복 실행을 막기 위해 **비활성화(Disabled)** 처리해 뒀습니다(삭제는 안 함 — 필요하면 다시 켤 수 있음).

아래는 여전히 로컬에서 도는 나머지 작업들의 등록 가이드입니다.

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

## 4. RecommendationsWatch / TrackRecommendations — GitHub Actions로 이전됨 (2026-09-06)

로컬 `schtasks` 등록은 더 이상 사용하지 않습니다. 자세한 내용과 재활성화 방법은
[GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) 참고.

## 확인 / 삭제

```powershell
schtasks /query /tn "DailyRisingBearishScan"
schtasks /delete /tn "DailyRisingBearishScan" /f
```

## 참고
- `run_11toast`(Windows 토스트 알림)는 비대화형 스케줄러 세션에서 무한 대기하는 버그가 있어, `common.py`의 `notify_new_signals()`에서 텔레그램을 먼저 보내고 toast는 데몬 스레드로 분리해 두었습니다.
- 로그는 `logs/` 폴더에 쌓입니다. `PYTHONIOENCODING=utf-8` 없이 실행하면 한글이 깨지므로 각 `.ps1`에 이미 설정되어 있습니다.
