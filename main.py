"""
게임 프로그래머 취업 매칭 에이전트 - 메인 실행 스크립트

사용법:
    python main.py                    # 전체 파이프라인 실행
    python main.py --crawl-only       # 크롤링만 실행
    python main.py --match-only       # 매칭만 실행 (시트의 신규 공고 대상)
    python main.py --parse-resume     # 이력서 파싱만 실행
"""

import argparse
import re
from datetime import datetime
from urllib.parse import parse_qsl
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from config import Config
from sheets.sheets_manager import SheetsManager
from crawlers.gamejob_crawler import GameJobCrawler
from crawlers.jobkorea_crawler import JobKoreaCrawler
from crawlers.kakaogames_crawler import KakaoGamesCrawler
from crawlers.krafton_crawler import KraftonCrawler
from crawlers.ncsoft_crawler import NCSoftCrawler
from crawlers.nexon_crawler import NexonCrawler
from crawlers.netmarble_crawler import NetmarbleCrawler
from crawlers.pearlabyss_crawler import PearlAbyssCrawler
from crawlers.saramin_crawler import SaraminCrawler
from crawlers.smilegate_crawler import SmilegateCrawler
from parsers.resume_parser import ResumeParser
from agents.job_management_agent import JobManagementAgent


PREFERRED_GAME_COMPANIES = [
    "넥슨", "넥슨게임즈", "엔씨소프트", "ncsoft", "크래프톤", "krafton",
    "넷마블", "펄어비스", "스마일게이트", "카카오게임즈", "네오위즈",
    "컴투스", "웹젠", "라인게임즈", "엑스엘게임즈", "라이온하트",
]

PROGRAMMER_KEYWORDS = [
    "프로그래머", "programmer", "developer", "development", "개발자", "개발",
    "engineer", "엔지니어", "client", "server", "backend", "frontend",
    "클라이언트", "서버", "엔진", "engine", "게임플레이", "render", "graphics",
    "unreal", "unity", "ue4", "ue5", "c++", "c#", "cpp", "테크니컬", "technical",
    "tools", "tool", "sdk", "platform", "웹 애플리케이션", "웹서비스개발",
]

NON_PROGRAMMER_KEYWORDS = [
    "qa beginner", "hr", "finance", "accounting", "marketing", "pr ", "홍보", "재무", "회계",
    "인사", "법무", "총무", "채용", "운영지원", "사업", "마케팅", "디자이너", "아티스트",
    "sound", "audio", "번역", "localization", "gm/cm", "community manager", "esg",
    "구매", "복지", "general affairs", "account manager", "community", "composer",
]


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_text_key(value: str) -> str:
    normalized = _normalize_space(value).lower()
    normalized = re.sub(r"[^a-z0-9가-힣]+", "", normalized)
    return normalized


def _canonical_job_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        split = urlsplit(raw)
        query_items = sorted(
            (key, val)
            for key, val in parse_qsl(split.query, keep_blank_values=False)
            if not key.lower().startswith(("utm_", "fbclid", "gclid"))
        )
        return urlunsplit((split.scheme.lower(), split.netloc.lower(), split.path.rstrip("/"), "&".join(f"{k}={v}" for k, v in query_items), ""))
    except Exception:
        return raw.lower()


def _job_signature(job: dict) -> tuple[str, str, str]:
    return (
        _canonical_job_url(job.get("url", "")),
        _normalize_text_key(job.get("company", "")),
        _normalize_text_key(job.get("title", "")),
    )


def _is_programmer_job(job: dict) -> bool:
    title = str(job.get("title") or "")
    position = str(job.get("position") or "")
    skills = str(job.get("skills") or "")
    company = str(job.get("company") or "")
    source = str(job.get("source") or "")
    haystack = _normalize_space(" ".join([title, position, skills, company, source])).lower()

    positive = any(keyword in haystack for keyword in PROGRAMMER_KEYWORDS)
    negative = any(keyword in haystack for keyword in NON_PROGRAMMER_KEYWORDS)

    if positive and not negative:
        return True

    strong_title = _normalize_space(f"{title} {position}").lower()
    return any(token in strong_title for token in ["프로그래머", "programmer", "개발자", "engineer", "클라이언트", "서버", "unreal", "unity", "엔진"])


def _company_priority(job: dict) -> tuple[int, int, str, str]:
    company = str(job.get("company") or "")
    source = str(job.get("source") or "")
    haystack = f"{company} {source}".lower()
    for index, keyword in enumerate(PREFERRED_GAME_COMPANIES):
        if keyword.lower() in haystack:
            return (0, index, _normalize_space(company).lower(), _normalize_space(job.get("title") or "").lower())
    return (1, 999, _normalize_space(company).lower(), _normalize_space(job.get("title") or "").lower())


def _dedupe_and_rank_jobs(jobs: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str, str], dict] = {}

    for job in jobs:
        normalized_job = dict(job)
        signature = _job_signature(normalized_job)
        if not any(signature):
            signature = (
                _normalize_text_key(normalized_job.get("company", "")),
                _normalize_text_key(normalized_job.get("title", "")),
                _normalize_text_key(normalized_job.get("deadline", "")),
            )

        if signature in deduped:
            existing = deduped[signature]
            if len(_normalize_space(str(normalized_job.get("skills") or ""))) > len(_normalize_space(str(existing.get("skills") or ""))):
                merged = dict(existing)
                merged.update({k: v for k, v in normalized_job.items() if v})
                deduped[signature] = merged
            continue

        deduped[signature] = normalized_job

    filtered = [job for job in deduped.values() if _is_programmer_job(job)]
    filtered.sort(key=_company_priority)
    return filtered


def run_crawl(sheets: SheetsManager) -> list[dict]:
    """크롤링 실행. 수집된 전체 공고 리스트 반환."""
    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] 크롤링 시작")
    print(f"{'='*50}")

    # 매 실행마다 시트 초기화 (항상 최신 공고만 유지)
    print("  이전 공고 데이터 초기화 중...")
    sheets.reset_jobs()

    all_jobs = []

    crawler_specs = [
        ("게임잡", GameJobCrawler),
        ("잡코리아", JobKoreaCrawler),
        ("사람인", SaraminCrawler),
        ("넥슨 커리어스", NexonCrawler),
        ("NC Careers", NCSoftCrawler),
        ("KRAFTON Careers", KraftonCrawler),
        ("넷마블컴퍼니 채용", NetmarbleCrawler),
        ("Pearl Abyss Careers", PearlAbyssCrawler),
        ("Smilegate Careers", SmilegateCrawler),
        ("카카오게임즈 채용", KakaoGamesCrawler),
    ]

    source_counts: list[tuple[str, int]] = []
    for index, (label, crawler_cls) in enumerate(crawler_specs, start=1):
        print(f"\n[{index}/{len(crawler_specs)}] {label} 크롤링 중...")
        try:
            crawler = crawler_cls()
            jobs = crawler.crawl(Config.SEARCH_KEYWORDS, Config.MAX_PAGES_PER_SITE)
            all_jobs.extend(jobs)
            source_counts.append((label, len(jobs)))
            print(f"  → {len(jobs)}건 수집")
        except Exception as e:
            source_counts.append((label, 0))
            print(f"  → {label} 크롤링 실패: {e}")

    raw_count = len(all_jobs)
    processed_jobs = _dedupe_and_rank_jobs(all_jobs)
    deduped_count = len(processed_jobs)
    filtered_out_count = raw_count - deduped_count

    if processed_jobs:
        new_count = sheets.append_jobs(processed_jobs)
        total_count = sum(count for _, count in source_counts)
        source_summary = ", ".join(f"{label} {count}건" for label, count in source_counts)
        print(f"\n총 {total_count}건 수집, {new_count}건 신규 저장")
        print(f"수집 출처 요약: {source_summary}")
        print(f"후처리 결과: 원본 {raw_count}건 → 최종 {deduped_count}건 (중복/비대상 제외 {filtered_out_count}건)")
    else:
        print("수집된 공고 없음")

    return processed_jobs


def run_parse_resume(sheets: SheetsManager, file_path: str = None):
    """이력서 파싱 및 저장"""
    print(f"\n{'='*50}")
    print(f"이력서 파싱 시작")
    print(f"{'='*50}")

    parser = ResumeParser()

    if file_path:
        resume_files = [file_path]
    else:
        from pathlib import Path
        resume_dir = Path("data/resume")
        resume_files = list(resume_dir.glob("*.*"))

    all_data = {}
    for fp in resume_files:
        print(f"  파싱 중: {fp}")
        try:
            data = parser.parse(str(fp))
            all_data.update(data)
        except Exception as e:
            print(f"  파싱 실패: {e}")

    if all_data:
        sheets.save_resume_data(all_data)
        print("이력서 데이터 Google Sheets 저장 완료")
    else:
        print("파싱된 이력서 데이터 없음")


def run_match(sheets: SheetsManager, jobs: list[dict] = None):
    """
    Hermes 기반 Job management 요청 생성.
    jobs 인자가 있으면 해당 공고를 요청 payload에 포함 (Full pipeline용).
    없으면 시트의 '신규' 상태 공고만 Hermes Agent에 전달 (--match-only용).
    """
    print(f"\n{'='*50}")
    print(f"Hermes Job management 요청 생성")
    print(f"{'='*50}")

    if jobs is None:
        sheets.cleanup_closed_jobs()

    agent = JobManagementAgent(sheets)
    request = agent.request_job_management(jobs=jobs)
    if request is None:
        return

    print(f"Hermes Agent 요청 완료: {request.request_id}")
    print(f"대상 공고 수: {len(request.requested_job_ids)}")
    print(f"요청 파일: {request.request_file}")
    print("Discord 전송은 Hermes Agent가 처리합니다.")


def main():
    parser = argparse.ArgumentParser(description="게임 프로그래머 취업 매칭 에이전트")
    parser.add_argument("--crawl-only", action="store_true", help="크롤링만 실행")
    parser.add_argument("--match-only", action="store_true", help="매칭만 실행")
    parser.add_argument("--parse-resume", type=str, nargs="?", const="", help="이력서 파싱")
    args = parser.parse_args()

    sheets = SheetsManager()

    if args.crawl_only:
        run_crawl(sheets)
    elif args.match_only:
        run_match(sheets)
    elif args.parse_resume is not None:
        run_parse_resume(sheets, args.parse_resume or None)
    else:
        # Full pipeline: 크롤링 → 시트 저장 → 시트에서 읽어 매칭
        run_crawl(sheets)
        run_match(sheets)

    print(f"\n[{datetime.now()}] 실행 완료")


if __name__ == "__main__":
    main()
