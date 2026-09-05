# DoubleBWatch 작업 스케줄러용 — 30분마다 상시 실행 (내부에서 장시간 아니면 스킵)
# 실측: KOSPI100+S&P500 스캔 1회 약 2.9분, 30분 주기면 약 10배 여유
# cmd.exe로 리다이렉트 — PowerShell의 *>>는 stderr 진행로그를 NativeCommandError로 감싸 로그를 지저분하게 만듦
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

cmd /c "python watch_doubleb.py >> logs\watch_doubleb.log 2>&1"
