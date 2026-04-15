# 🎮 게임 프로그래머 취업 매칭 에이전트

게임잡, 사람인, 잡코리아에서 채용공고를 자동 수집하고, 이력서/공고 로우데이터를 Hermes Agent에 넘겨 선별 및 Discord 전송을 수행하는 에이전트입니다.

## 아키텍처

```
크롤러 (Playwright) → Google Sheets → Hermes 요청 파일 생성 → Hermes Agent → Discord 알림
                                ↑
                        이력서 파서 (PDF/DOCX)
```

## 빠른 시작

### 1. 환경 세팅

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. 환경변수 설정

`.env.example`을 `.env`로 복사 후 값 입력:

```bash
copy .env.example .env
```

| 변수 | 설명 |
|------|------|
| `GOOGLE_CREDENTIALS_PATH` | Google 서비스 계정 JSON 경로 |
| `SPREADSHEET_NAME` | Google Sheets 스프레드시트 이름 |
| `DISCORD_WEBHOOK_URL` | (레거시) 기존 Python Discord 전송용 값 |
| `HERMES_QUEUE_DIR` | Hermes 요청/응답 파일 큐 디렉터리 |

### 3. Google Sheets 설정

1. [Google Cloud Console](https://console.cloud.google.com) → 새 프로젝트 생성
2. Google Sheets API + Google Drive API 활성화
3. 서비스 계정 생성 → JSON 키 다운로드 → `data/credentials/service_account.json` 저장
4. Google Sheets 생성 후 서비스 계정 이메일을 편집자로 공유

### 4. Hermes Agent 연동

Python은 `HERMES_QUEUE_DIR` 아래에 요청 JSON을 생성합니다.
Hermes Agent는 `requests/` 폴더를 감시해 공고를 분석하고 Discord 메시지를 직접 보낸 뒤,
`responses/` 폴더에 처리 결과 JSON을 남기도록 구성합니다.

### 5. 이력서 등록

`data/resume/` 폴더에 이력서 파일(PDF, DOCX, TXT) 넣기

## 실행

```bash
# 전체 파이프라인 (크롤링 → Hermes 작업 요청)
python main.py

# 크롤링만
python main.py --crawl-only

# 이력서 파싱만
python main.py --parse-resume

# Hermes 작업 요청만
python main.py --match-only
```

## 자동 스케줄링 (6시간 주기)

`scheduler_setup.bat`를 **관리자 권한**으로 실행:

```
우클릭 → 관리자 권한으로 실행
```

## 프로젝트 구조

```
├── config.py                # 설정 관리
├── main.py                  # 메인 실행 스크립트
├── run_agent.bat            # 배치 실행 파일
├── scheduler_setup.bat      # Windows 작업 스케줄러 등록
├── crawlers/                # 크롤러 모듈
│   ├── gamejob_crawler.py   # 게임잡
│   ├── saramin_crawler.py   # 사람인
│   └── jobkorea_crawler.py  # 잡코리아
├── parsers/                 # 이력서 파서
├── agents/                  # Hermes Job management 요청 생성
├── matcher/                 # 레거시 매칭 엔진
├── notifier/                # 레거시 Discord 알림
├── sheets/                  # Google Sheets 연동
├── skills/                  # skills.sh 호환 로컬 스킬 문서
└── data/
    ├── resume/              # 이력서 파일 보관
    ├── credentials/         # Google API 인증 파일
    └── hermes_queue/        # Hermes 요청/응답 파일 큐
```

## Hermes 요청 파일 예시 흐름

1. Python이 `data/hermes_queue/requests/job_management_request_*.json` 생성
2. Hermes Agent가 이력서/공고 로우데이터를 읽고 공고 선별
3. Hermes Agent가 Discord 메시지 직접 전송
4. Hermes Agent가 `data/hermes_queue/responses/job_management_response_*.json` 기록

기존 Python 내부 점수식/threshold/top-N 방식은 더 이상 Stage 2의 기준이 아닙니다.
