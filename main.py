"""
게임 프로그래머 취업 매칭 에이전트 - 메인 실행 스크립트

사용법:
    python main.py                    # 전체 파이프라인 실행
    python main.py --crawl-only       # 크롤링만 실행
    python main.py --match-only       # 매칭만 실행
    python main.py --parse-resume     # 이력서 파싱만 실행
"""

import argparse
from datetime import datetime

from config import Config
from sheets.sheets_manager import SheetsManager
from crawlers.gamejob_crawler import GameJobCrawler
from crawlers.jobkorea_crawler import JobKoreaCrawler
from parsers.resume_parser import ResumeParser
from matcher.job_matcher import JobMatcher
from notifier.discord_notifier import DiscordNotifier


def run_crawl(sheets: SheetsManager) -> int:
    """크롤링 실행"""
    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] 크롤링 시작")
    print(f"{'='*50}")

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
        print(f"\n총 {len(all_jobs)}건 수집, {new_count}건 신규 저장")
        return new_count
    else:
        print("수집된 공고 없음")
        return 0


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


def run_match(sheets: SheetsManager):
    """매칭 및 알림 실행"""
    print(f"\n{'='*50}")
    print(f"매칭 엔진 실행")
    print(f"{'='*50}")

    jobs = sheets.get_all_jobs()
    resume_data = sheets.get_resume_data()

    if not jobs:
        print("채용공고 데이터가 없습니다. 먼저 크롤링을 실행하세요.")
        return
    if not resume_data:
        print("이력서 데이터가 없습니다. 먼저 이력서를 파싱하세요.")
        return

    new_jobs = [j for j in jobs if j.get("상태") == "신규"]
    print(f"  전체 공고: {len(jobs)}건, 신규 공고: {len(new_jobs)}건")

    if not new_jobs:
        print("새로운 공고가 없습니다.")
        return

    matcher = JobMatcher()
    matches = matcher.match(resume_data, new_jobs)
    print(f"  매칭 결과: {len(matches)}건 (threshold: {Config.MATCH_THRESHOLD})")

    if matches:
        notifier = DiscordNotifier()
        notifier.send_matches(matches)
        print("Discord 알림 전송 완료")

        job_ids = [
            match["job"].get("공고ID") or match["job"].get("job_id", "")
            for match in matches
        ]
        sheets.bulk_update_job_status([jid for jid in job_ids if jid], "알림완료")
    else:
        print("매칭되는 공고가 없습니다.")


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
        run_crawl(sheets)
        run_match(sheets)

    print(f"\n[{datetime.now()}] 실행 완료")


if __name__ == "__main__":
    main()
