# Agent GameJob — Harness

## 프로젝트 개요
게임 프로그래머 채용공고 자동 수집 → Google Sheets 저장 → Hermes Agent 위임 → Discord 알림 파이프라인.

## 아키텍처

```
main.py (진입점/오케스트레이터)
  ├── crawlers/          각 사이트별 크롤러 (Playwright + requests/BS4)
  ├── sheets/            Google Sheets CRUD (gspread)
  ├── agents/            Hermes Agent 파일큐 요청 생성
  ├── parsers/           이력서 파싱 (PDF/DOCX)
  ├── matcher/           레거시 점수 매처 (미사용, 삭제 금지)
  └── notifier/          레거시 Discord 웹훅 (미사용, Hermes가 직접 전송)
```

### 데이터 흐름 (Full pipeline)
1. `run_crawl()` — 크롤러 10개 병렬 수집
2. `_dedupe_and_rank_jobs()` — 중복제거 + 프로그래머 공고 필터 + 게임사 우선순위 정렬
3. `sheets.append_jobs()` — Google Sheets "공고" 시트에 저장
4. `run_match()` → `sheets.cleanup_closed_jobs()` — 마감 공고 "만료" 처리
5. `JobManagementAgent.request_job_management()` — `data/hermes_queue/requests/` 에 JSON 파일 생성
6. Hermes Agent(별도 프로세스)가 파일을 읽어 LLM 판단 후 Discord 전송 → `data/hermes_queue/responses/` 에 결과 기록

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `main.py` | 파이프라인 조율, `_dedupe_and_rank_jobs`, `_is_programmer_job`, `_company_priority` |
| `config.py` | 환경변수 래퍼 (`GOOGLE_CREDENTIALS_PATH`, `HERMES_QUEUE_DIR` 등) |
| `crawlers/base_crawler.py` | 크롤러 기반 클래스 |
| `crawlers/gamejob_crawler.py` | 게임잡 (Playwright) |
| `crawlers/jobkorea_crawler.py` | 잡코리아 (Playwright) |
| `crawlers/saramin_crawler.py` | 사람인 |
| `crawlers/nexon_crawler.py` | 넥슨 Careers |
| `crawlers/ncsoft_crawler.py` | NC Careers |
| `crawlers/krafton_crawler.py` | KRAFTON Careers |
| `crawlers/netmarble_crawler.py` | 넷마블 채용 |
| `crawlers/pearlabyss_crawler.py` | Pearl Abyss Careers |
| `crawlers/smilegate_crawler.py` | Smilegate Careers |
| `crawlers/kakaogames_crawler.py` | 카카오게임즈 채용 |
| `sheets/sheets_manager.py` | Google Sheets 읽기/쓰기/상태변경, `cleanup_closed_jobs` |
| `agents/job_management_agent.py` | Hermes 파일큐 요청 JSON 생성, 공고 상태 → "에이전트요청됨" |
| `match_discord.py` | Discord용 매칭 데이터 추출 스크립트 (독립 실행) |

## 환경변수 (.env)

| 변수 | 설명 |
|------|------|
| `GOOGLE_CREDENTIALS_PATH` | 서비스 계정 JSON 경로 |
| `SPREADSHEET_NAME` | Google Sheets 이름 (기본: 게임프로그래머_채용공고) |
| `DISCORD_WEBHOOK_URL` | 레거시 웹훅 (Hermes가 직접 전송하므로 현재 미사용) |
| `HERMES_QUEUE_DIR` | 파일 큐 루트 디렉토리 (기본: data/hermes_queue) |
| `HERMES_RESPONSE_TIMEOUT_SECONDS` | Hermes 응답 대기 타임아웃 (0 = 대기 안 함) |
| `MAX_PAGES_PER_SITE` | 사이트당 최대 크롤링 페이지 수 (기본: 5) |

## 실행

```bash
# Full pipeline (크롤링 + 매칭)
python main.py

# 크롤링만
python main.py --crawl

# 이력서 파싱만
python main.py --parse-resume path/to/resume.pdf

# 매칭만 (이미 시트에 공고 있을 때)
python main.py --match
```

## 설계 제약 — 반드시 지켜야 할 사항

- **Hermes Agent가 매칭·Discord 전송을 담당한다.** `matcher/` 레거시 점수식을 재활성화하거나 Python 코드에서 Discord 웹훅을 직접 호출하지 말 것.
- **공고 필터링은 `_is_programmer_job()`으로 통일.** 새 크롤러를 추가할 때도 이 함수를 통과한 공고만 시트에 저장된다.
- **중복 제거 키는 `_job_signature(url, company, title)`.** URL이 없는 경우 `(company, title, deadline)` 폴백.
- **크롤러는 `base_crawler.py`를 상속해 `crawl(keywords, max_pages)` 인터페이스를 구현한다.**
- **Google Sheets 컬럼명은 한국어 키 사용.** `sheets_manager.py`의 헤더 순서를 바꾸면 기존 시트가 깨진다.
- **`matcher/`, `notifier/` 디렉토리는 삭제하지 말 것.** 히스토리 보존 목적.

## Google Sheets 시트 구조

| 시트명 | 용도 |
|--------|------|
| 공고 | 수집된 채용공고 전체 |
| 이력서 | 파싱된 이력서 데이터 |

공고 시트 상태값: `신규` → `에이전트요청됨` → `알림완료` / `만료`
