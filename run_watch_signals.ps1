# SignalWatch30min 작업 스케줄러용 — 30분마다 상시 실행
# 스크립트 내부(watch_signals.py)에서 장시간 아니면 즉시 스킵하므로 트리거는 상시 30분 간격으로 등록
# cmd.exe로 리다이렉트 — PowerShell의 *>>는 stderr 진행로그를 NativeCommandError로 감싸 로그를 지저분하게 만듦
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

cmd /c "python watch_signals.py >> logs\watch_signals.log 2>&1"
