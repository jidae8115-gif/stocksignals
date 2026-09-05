# GitHub Actions 클라우드 자동화 (PC 꺼져 있어도 계속 작동)

로컬 PC가 꺼져 있어도 추천종목 스캔과 성과추적이 계속 돌아가도록, `RecommendationsWatch`와
`TrackRecommendations` 스케줄을 로컬 Windows 작업 스케줄러 대신 GitHub Actions(무료, 클라우드,
결제정보 불필요)로 옮겼습니다. 2026-09-06에 설정 완료.

## 구조

- 리포지토리: https://github.com/jidae8115-gif/stocksignals (비공개)
- `.github/workflows/recommendations-watch.yml`: 매 30분마다 실행(cron `*/30 * * * *`).
  `watch_recommendations.py`가 장시간 아니면 자동 스킵하는 로직은 그대로 유지.
  결과(`latest_recommendations.csv`, `last_scan_recommendations.json`)를 리포지토리에 커밋해서 상태 유지.
- `.github/workflows/track-recommendations.yml`: 매일 07:00 KST(cron `0 22 * * *`, UTC 기준) 실행.
  `track_recommendations.py`로 목표가/손절가 도달 여부 판정 + `recommendations_log.csv` 커밋 +
  구글 드라이브 "주식" 폴더의 시트 자동 동기화.
- 두 워크플로 모두 `workflow_dispatch`로 수동 실행 가능 (Actions 탭 → 워크플로 선택 → Run workflow).

## 자격증명

- 구글 서비스 계정 키(`service_account.json`)는 **base64로 인코딩해서** `SERVICE_ACCOUNT_JSON_B64`
  라는 GitHub Secret으로 저장 (평문으로 저장하면 GitHub 쪽에서 값이 잘리는 문제가 있어 base64 사용).
  워크플로 안에서 `base64 -d`로 복원해서 씀.
- `requirements-cloud.txt`를 사용 (일반 `requirements.txt`의 `win11toast`는 Windows 전용이라 제외).
- `FinanceDataReader`는 PyPI에 정식 배포되어 있지 않아 GitHub 소스(`git+https://github.com/...`)로 설치.

## 로컬 스케줄러와의 관계

기존 로컬 `RecommendationsWatch`/`TrackRecommendations` 작업스케줄러 항목은 중복 실행 방지를 위해
**비활성화(Disabled)** 처리했습니다. 다시 로컬로 되돌리려면:

```powershell
schtasks /change /tn "RecommendationsWatch" /enable
schtasks /change /tn "TrackRecommendations" /enable
```

(단, 로컬과 GitHub Actions를 동시에 켜면 같은 파일에 서로 다른 내용을 커밋하려다 git 충돌이 날 수 있어
권장하지 않습니다.)

## 결과 확인

- **구글 시트** (가장 편함, PC 상태와 무관): https://docs.google.com/spreadsheets/d/1WSk9P_qt915rzNnJn30fWoiV0pzdBYpAdH5ATLSK_5w/edit
- **GitHub Actions 실행 로그**: https://github.com/jidae8115-gif/stocksignals/actions
- 로컬 대시보드(`streamlit run app.py`)를 쓰려면 먼저 `git pull`로 최신 상태를 받아와야 함
  (로컬 파일은 더 이상 자동으로 갱신되지 않음).

## 유지보수 참고

- GitHub 개인 액세스 토큰(PAT)은 리포지토리 생성·시크릿 등록 때 1회 사용. 만료되면(90일) 재발급 필요
  — 이후 GitHub Actions 자체 실행에는 PAT가 필요 없음(내장 `GITHUB_TOKEN` 사용).
- Actions 무료 사용량: 비공개 리포지토리 기준 월 2,000분. RecommendationsWatch(30분마다, 1회 약 3~5분)
  기준 하루 약 15~20회 실행 × 4~5분 ≈ 하루 60~100분, 한 달이면 무료 한도에 걸릴 수 있음 — 사용량이
  부족해지면 [Settings → Billing](https://github.com/settings/billing)에서 확인하고 주기를 늘리는 것을 고려.
