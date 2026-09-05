# RecommendationsWatch 작업 스케줄러용 — 30분마다 상시 실행 (내부에서 장시간 아니면 스킵)
# 6개 전략(실전 5개+더블비) 통합 스캔 — 종목별 fetch를 캐싱해 공유하므로 doubleb 단독 스캔과 소요시간 거의 동일(약 3분)
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

cmd /c "python watch_recommendations.py >> logs\watch_recommendations.log 2>&1"
