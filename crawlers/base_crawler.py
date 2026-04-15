from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
import random


@dataclass
class JobPosting:
    """채용공고 데이터 구조"""
    job_id: str = ""
    source: str = ""
    company: str = ""
    title: str = ""
    position: str = ""
    experience: str = ""
    skills: str = ""
    education: str = ""
    location: str = ""
    salary: str = ""
    deadline: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "source": self.source,
            "company": self.company,
            "title": self.title,
            "position": self.position,
            "experience": self.experience,
            "skills": self.skills,
            "education": self.education,
            "location": self.location,
            "salary": self.salary,
            "deadline": self.deadline,
            "url": self.url,
        }


class BaseCrawler(ABC):
    """크롤러 베이스 클래스"""

    CLOSED_MARKERS = (
        "접수마감",
        "모집마감",
        "채용마감",
        "채용 종료",
        "채용종료",
        "마감됨",
        "공고마감",
        "closed",
    )

    def __init__(self):
        self.jobs: list[JobPosting] = []

    @abstractmethod
    def crawl(self, keywords: list[str], max_pages: int = 5) -> list[dict]:
        """키워드로 채용공고를 크롤링하여 리스트로 반환"""
        pass

    def _random_delay(self, min_sec=1, max_sec=3):
        """안티봇 대응을 위한 랜덤 딜레이"""
        time.sleep(random.uniform(min_sec, max_sec))

    def _create_browser_context(self, playwright):
        """브라우저 컨텍스트 생성 (탐지 우회 설정 포함)"""
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
        )
        return browser, context

    def _is_closed_posting(self, *texts: str) -> bool:
        """마감된 공고 여부 판별"""
        normalized = " ".join(
            str(text).strip().lower() for text in texts if text and str(text).strip()
        )
        if not normalized:
            return False

        if "채용시" in normalized or "상시" in normalized:
            return False

        return any(marker in normalized for marker in self.CLOSED_MARKERS)
