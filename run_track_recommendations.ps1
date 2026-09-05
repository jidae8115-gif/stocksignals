# TrackRecommendations 작업 스케줄러용 — 매일 07:00 실행 (한국장·미국장 둘 다 마감 이후)
# 추천종목 성과 추적 로그 갱신 + (설정돼 있으면) 구글 드라이브 시트 자동 동기화
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

cmd /c "python track_recommendations.py >> logs\track_recommendations.log 2>&1"
