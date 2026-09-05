# DailyRisingBearishScan 작업 스케줄러용 — 매일 08:30 평일 실행
# PYTHONIOENCODING 미설정 시 로그에 한글이 깨짐 (README 알려진 버그)
# cmd.exe로 리다이렉트 — PowerShell의 *>>는 stderr 진행로그를 NativeCommandError로 감싸 로그를 지저분하게 만듦
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

cmd /c "python find_entries.py --backup >> logs\daily_scan.log 2>&1"
cmd /c "python scan_rising_bearish_kr.py >> logs\daily_scan.log 2>&1"
cmd /c "python scan_rising_bearish_us.py >> logs\daily_scan.log 2>&1"
