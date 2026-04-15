"""
게임 프로그래머 취업 매칭 에이전트 - 메인 실행 스크립트

사용법:
    python main.py                    # 전체 파이프라인 실행
    python main.py --crawl-only       # 크롤링만 실행
    python main.py --match-only       # 매칭만 실행 (시트의 신규 공고 대상)
    python main.py --parse-resume     # 이력서 파싱만 실행
"""

import argparse
from datetime import datetime

from config import Config
from sheets.sheets_manager import SheetsManager
from crawlers.gamejob_crawler import GameJobCrawler
from crawlers.jobkorea_crawler import JobKoreaCrawler
from parsers.resume_parser import ResumeParser
from agents.job_management_agent import JobManagementAgent


def run_crawl(sheets: SheetsManager) -> list[dict]:
    """크롤링 실행. 수집된 전체 공고 리스트 반환."""
    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] 크롤링 시작")
    print(f"{'='*50}")

    # 매 실행마다 시트 초기화 (항상 최신 공고만 유지)
    print("  이전 공고 데이터 초기화 중...")
    sheets.reset_jobs()

    all_jobs = []

    print("\n[1/2] 게임잡 크롤링 중...")
    try:
        gamejob = GameJobCrawler()
        jobs = gamejob.crawl(Config.SEARCH_KEYWORDS, Config.MAX_PAGES_PER_SITE)
        all_jobs.extend(jobs)
        print(f"  → {len(jobs)}건 수집")
    except Exception as e:
        print(f"  → 게임잡 크롤링 실패: {e}")

    print("\n[2/2] 잡코리아 크롤링 중...")
    try:
        jobkorea = JobKoreaCrawler()
        jobs = jobkorea.crawl(Config.SEARCH_KEYWORDS, Config.MAX_PAGES_PER_SITE)
        all_jobs.extend(jobs)
        print(f"  → {len(jobs)}건 수집")
    except Exception as e:
        print(f"  → 잡코리아 크롤링 실패: {e}")

    if all_jobs:
        new_count = sheets.append_jobs(all_jobs)
        print(f"\n총 {len(jobs)}건 수집, {new_count}건 신규 저장")
    else:
        print("수집된 공고 없음")

    return all_jobs


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
        # Full pipeline: 크롤링 후 수집된 공고 바로 매칭
        crawled_jobs = run_crawl(sheets)
        run_match(sheets, jobs=crawled_jobs)

    print(f"\n[{datetime.now()}] 실행 완료")


if __name__ == "__main__":
    main()
