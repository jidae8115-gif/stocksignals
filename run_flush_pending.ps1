# 조용한시간 큐 일괄발송용 — 매일 06:00 실행
# cmd.exe로 리다이렉트 — PowerShell의 *>>는 stderr 진행로그를 NativeCommandError로 감싸 로그를 지저분하게 만듦
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

cmd /c "python flush_pending.py >> logs\flush_pending.log 2>&1"
