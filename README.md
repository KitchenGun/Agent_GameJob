# 🎮 게임 프로그래머 취업 매칭 에이전트

게임잡, 사람인, 잡코리아에서 채용공고를 자동 수집하고, 이력서와 매칭하여 Discord로 알림을 보내는 에이전트입니다.

## 아키텍처

```
크롤러 (Playwright) → Google Sheets → 매칭 엔진 → Discord 알림
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
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL |
| `MATCH_THRESHOLD` | 매칭 임계값 (0.0~1.0, 기본값 0.5) |

### 3. Google Sheets 설정

1. [Google Cloud Console](https://console.cloud.google.com) → 새 프로젝트 생성
2. Google Sheets API + Google Drive API 활성화
3. 서비스 계정 생성 → JSON 키 다운로드 → `data/credentials/service_account.json` 저장
4. Google Sheets 생성 후 서비스 계정 이메일을 편집자로 공유

### 4. Discord Webhook 생성

Discord 채널 설정 → 연동 → 웹후크 → URL 복사 → `.env` 입력

### 5. 이력서 등록

`data/resume/` 폴더에 이력서 파일(PDF, DOCX, TXT) 넣기

## 실행

```bash
# 전체 파이프라인 (크롤링 → 매칭 → 알림)
python main.py

# 크롤링만
python main.py --crawl-only

# 이력서 파싱만
python main.py --parse-resume

# 매칭만
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
├── matcher/                 # 매칭 엔진 (TF-IDF + 키워드)
├── notifier/                # Discord 알림
├── sheets/                  # Google Sheets 연동
└── data/
    ├── resume/              # 이력서 파일 보관
    └── credentials/         # Google API 인증 파일
```

## 매칭 점수 기준

| 항목 | 가중치 |
|------|--------|
| 기술스택 키워드 매칭 | 40% |
| TF-IDF 코사인 유사도 | 30% |
| 경력 조건 부합 | 20% |
| 직무명 키워드 | 10% |

`MATCH_THRESHOLD` 값(기본 0.5)을 조정하여 알림 민감도를 변경할 수 있습니다.
