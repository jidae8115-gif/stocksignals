# 구글 드라이브 자동 동기화 설정 (서비스 계정)

`track_recommendations.py`가 매번 실행될 때마다 추천종목 추적 시트를 구글 드라이브
"주식" 폴더에 자동으로 갱신하도록 설정합니다. 딱 한 번만 하면 됩니다.

## 1. 구글 클라우드 프로젝트 + 서비스 계정 만들기

1. https://console.cloud.google.com/ 접속 (구글 계정으로 로그인: jidae8115@gmail.com)
2. 상단에서 **새 프로젝트** 생성 (이름 아무거나, 예: `stocksignals`)
3. 왼쪽 메뉴 **API 및 서비스 > 라이브러리** → "Google Drive API" 검색 → **사용** 클릭
4. 왼쪽 메뉴 **API 및 서비스 > 사용자 인증 정보** → 상단 **+ 사용자 인증 정보 만들기 > 서비스 계정**
5. 서비스 계정 이름 입력 (예: `stocksignals-bot`) → **만들기 및 계속하기** → 역할 선택은 건너뛰고 **완료**
6. 방금 만든 서비스 계정 클릭 → **키** 탭 → **키 추가 > 새 키 만들기** → **JSON** 선택 → 다운로드

## 2. 키 파일을 프로젝트 폴더에 저장

다운로드된 `xxxxx.json` 파일 이름을 `service_account.json`으로 바꿔서 아래 경로에 저장:

```
C:\Users\CADCAM\Desktop\Stock\StockSignals\service_account.json
```

⚠️ 이 파일은 계정 키이므로 절대 다른 사람과 공유하거나 인터넷에 올리지 마세요.

## 3. 구글 드라이브 폴더를 서비스 계정과 공유

1. 다운로드한 JSON 파일을 열어서 `"client_email"` 값을 복사 (예: `stocksignals-bot@stocksignals-123456.iam.gserviceaccount.com`)
2. 구글 드라이브에서 **"주식"** 폴더 우클릭 → **공유**
3. 위에서 복사한 이메일 주소를 추가하고 **편집자(Editor)** 권한 부여 → 반드시 **완료/보내기**까지 클릭

## 3-1. 시트를 사용자 계정으로 한 번 미리 만들어두기 (중요)

⚠️ 개인 구글 계정(비 Workspace)에서는 서비스 계정의 Drive 저장용량 할당량이 0이라 **새 파일을 직접
만들 수 없습니다**. 그래서 시트 파일 자체는 사용자 계정으로 먼저 한 번 만들어둬야 하고, 그 다음부터
`drive_sync.py`는 그 파일의 **내용만 덮어쓰는 방식**(소유권 안 바뀜 → 저장용량 안 씀)으로 갱신합니다.

"주식" 폴더 안에 제목이 `config.json`의 `google_drive.sheet_title`과 정확히 같은
빈 구글 시트를 하나 만들어두세요 (기본값: `StockSignals 추천종목 추적`). 이미 있다면 이 단계는 생략.

## 4. 확인

```powershell
python drive_sync.py
```

"성공: https://docs.google.com/..." 메시지가 나오면 정상 연결된 것입니다.
이후 `track_recommendations.py`(또는 대시보드의 "지금 추적 갱신" 버튼)를 실행할 때마다
자동으로 구글 시트가 최신 상태로 갱신됩니다.

## 5. 매일 자동 갱신 스케줄 등록 (선택)

```powershell
schtasks /create /tn "TrackRecommendations" /tr "powershell.exe -ExecutionPolicy Bypass -File `"C:\Users\CADCAM\Desktop\Stock\StockSignals\run_track_recommendations.ps1`"" /sc daily /st 07:00 /f
```

한국장(15:30)·미국장(06:00 KST 근처) 둘 다 마감된 이후인 매일 07:00에 실행되도록 설정.
