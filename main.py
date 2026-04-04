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
from matcher.job_matcher import JobMatcher
from notifier.discord_notifier import DiscordNotifier


def run_crawl(sheets: SheetsManager) -> list[dict]:
    """크롤링 실행. 수집된 전체 공고 리스트 반환."""
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


# Unity 전용 공고 판별 키워드 (Unreal 없이 Unity만 있으면 제외)
_UNITY_ONLY_KEYWORDS = ["unity", "유니티", "c#"]
_UNREAL_KEYWORDS     = ["unreal", "ue4", "ue5", "uefn", "언리얼"]


def _is_unity_only(job: dict) -> bool:
    """Unity 전용 공고 여부 판별 (Unreal 키워드 없이 Unity 키워드만 있으면 True)"""
    text = " ".join(
        str(v) for v in job.values() if v and str(v).strip()
    ).lower()
    has_unreal = any(kw in text for kw in _UNREAL_KEYWORDS)
    has_unity  = any(kw in text for kw in _UNITY_ONLY_KEYWORDS)
    return has_unity and not has_unreal


def run_match(sheets: SheetsManager, jobs: list[dict] = None):
    """
    매칭 및 알림 실행.
    jobs 인자가 있으면 해당 공고로 매칭 (Full pipeline용).
    없으면 시트에서 '신규' 상태 공고를 읽어 매칭 (--match-only용).
    Full pipeline은 threshold 무관하게 상위 결과를 항상 Discord 전송.
    """
    print(f"\n{'='*50}")
    print(f"매칭 엔진 실행")
    print(f"{'='*50}")

    resume_data = sheets.get_resume_data()
    if not resume_data:
        print("이력서 데이터가 없습니다. 먼저 이력서를 파싱하세요.")
        return

    if jobs is not None:
        # Full pipeline: 크롤링된 공고 전체 대상
        before = len(jobs)
        target_jobs = [j for j in jobs if not _is_unity_only(j)]
        print(f"  크롤링 공고 {before}건 → Unity 전용 제외 후 {len(target_jobs)}건 매칭")
    else:
        # --match-only: 시트의 신규 공고만 대상
        all_sheet_jobs = sheets.get_all_jobs()
        if not all_sheet_jobs:
            print("채용공고 데이터가 없습니다. 먼저 크롤링을 실행하세요.")
            return
        before = len(all_sheet_jobs)
        target_jobs = [j for j in all_sheet_jobs if not _is_unity_only(j)]
        print(f"  전체 공고: {before}건 → Unity 제외 후 {len(target_jobs)}건")

    if not target_jobs:
        print("매칭할 공고가 없습니다.")
        return

    matcher = JobMatcher()

    if jobs is not None:
        # Full pipeline: threshold=0으로 전체 점수 산출 후 상위 결과 전송
        matches = matcher.match_all(resume_data, target_jobs)
        print(f"  전체 점수 산출: {len(matches)}건 (상위 순 정렬)")
    else:
        matches = matcher.match(resume_data, target_jobs)
        print(f"  매칭 결과: {len(matches)}건 (threshold: {Config.MATCH_THRESHOLD})")

    notifier = DiscordNotifier()
    notifier.send_matches(matches)
    print("Discord 알림 전송 완료")

    job_ids = [
        match["job"].get("공고ID") or match["job"].get("job_id", "")
        for match in matches
    ]
    sheets.bulk_update_job_status([jid for jid in job_ids if jid], "알림완료")


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
