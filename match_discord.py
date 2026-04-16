"""
Discord용 공고 매칭 데이터 추출 스크립트.
시트에서 이력서 + 신규 공고를 읽어 1차 필터링 후 JSON으로 출력.
LLM이 판단하도록 원문 데이터를 전달하는 것이 목적.
"""
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from sheets.sheets_manager import SheetsManager

# LLM에게 넘길 최대 공고 수 (토큰 절약)
MAX_CANDIDATES = 30

EXCLUDE_KEYWORDS = [
    "기획자", "아티스트", "애니메이터", "디자이너", "artist", "animator",
    "community manager", "community associate", "business development",
    "technical artist", "강사", "교육", "3d 디자이너", "컨셉", "사운드",
    "마케팅", "홍보", "인사", "회계", "법무", "총무", "번역", "개발pm",
    "반도체", "로봇", "시뮬레이션",
]

SENIOR_PATTERNS = ["8년 이상", "10년 이상", "15년 이상", "리드급"]

PROGRAMMER_KEYWORDS = [
    "프로그래머", "programmer", "개발자", "developer", "engineer",
    "클라이언트", "client", "서버", "server", "엔진", "engine",
    "c++", "c#", "unreal", "unity",
]


def _is_candidate(job: dict) -> bool:
    text = " ".join([
        job.get("제목", ""),
        job.get("직무", ""),
        job.get("기술스택", ""),
    ]).lower()

    if any(ex in text for ex in EXCLUDE_KEYWORDS):
        return False
    if any(sr in text for sr in SENIOR_PATTERNS):
        return False
    if not any(pk in text for pk in PROGRAMMER_KEYWORDS):
        return False
    return True


def _rough_score(job: dict) -> int:
    """LLM에게 넘길 후보를 좁히기 위한 최소한의 점수 (순위 결정용 아님)."""
    text = " ".join([
        job.get("제목", ""),
        job.get("직무", ""),
        job.get("기술스택", ""),
    ]).lower()
    score = 0
    for kw in ["c++", "c#", "unreal", "unity", "ue5", "클라이언트", "게임플레이"]:
        if kw in text:
            score += 1
    return score


def main() -> None:
    sm = SheetsManager()
    resume = sm.get_resume_data()
    jobs = sm.get_jobs_by_status("신규")

    if not resume:
        print(json.dumps({"error": "이력서 데이터가 없습니다."}, ensure_ascii=False))
        return

    if not jobs:
        print(json.dumps({"error": "신규 공고가 없습니다."}, ensure_ascii=False))
        return

    candidates = [j for j in jobs if _is_candidate(j)]
    candidates.sort(key=_rough_score, reverse=True)
    candidates = candidates[:MAX_CANDIDATES]

    output = {
        "resume": resume,
        "total_jobs": len(jobs),
        "candidates": [
            {
                "공고ID": j.get("공고ID", ""),
                "회사명": j.get("회사명", ""),
                "제목": j.get("제목", ""),
                "직무": j.get("직무", ""),
                "경력요건": j.get("경력요건", ""),
                "기술스택": j.get("기술스택", ""),
                "마감일": j.get("마감일", ""),
                "근무지역": j.get("근무지역", ""),
                "공고URL": j.get("공고URL", ""),
            }
            for j in candidates
        ],
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
