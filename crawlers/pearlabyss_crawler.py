from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from crawlers.base_crawler import BaseCrawler
from crawlers.base_crawler import JobPosting


class PearlAbyssCrawler(BaseCrawler):
    """펄어비스 채용 공고 크롤러."""

    BASE_URL = "https://www.pearlabyss.com"
    LIST_URL = f"{BASE_URL}/ko-KR/Company/Careers/List"
    SOURCE = "Pearl Abyss Careers"
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def crawl(self, keywords: list[str], max_pages: int = 5) -> list[dict]:
        del keywords, max_pages
        try:
            response = requests.get(self.LIST_URL, headers=self._HEADERS, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"[펄어비스] 요청 실패: {exc}")
            return []

        return [job.to_dict() for job in self._parse_list_page(response.text)]

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[JobPosting] = []
        seen_ids: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            if "/Company/Careers/detail" not in href:
                continue

            job_id_match = re.search(r"_jobOpeningNo=(\d+)", href)
            if not job_id_match:
                continue
            job_id = f"pearlabyss_{job_id_match.group(1)}"
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            block_text = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
            lines = [part.strip() for part in block_text.split(" ") if part.strip()]
            title = self._extract_title(block_text)
            if not title:
                continue

            experience = self._extract_token(block_text, r"(신입·경력·경력무관|신입/경력|신입·경력|경력무관|경력|신입)")
            employment = self._extract_token(block_text, r"(정규직·계약직·인턴·아르바이트·프리랜서|정규직|계약직|인턴|아르바이트|프리랜서|파견직)")
            location = self._extract_token(block_text, r"(과천|대만|홍콩|싱가폴|암스테르담|LA|도쿄|아이슬란드|벤쿠버|PA아트센터)")
            deadline = self._extract_token(block_text, r"(\d{4}-\d{2}-\d{2}\s*~\s*\d{4}-\d{2}-\d{2}|상시채용|인재풀)")
            skill_group = self._extract_skill_group(block_text)

            jobs.append(
                JobPosting(
                    job_id=job_id,
                    source=self.SOURCE,
                    company="펄어비스",
                    title=title,
                    position=title,
                    experience=experience,
                    skills=skill_group,
                    location=location,
                    salary=employment,
                    deadline=deadline,
                    url=urljoin(self.BASE_URL, href),
                )
            )

        return jobs

    def _extract_title(self, text: str) -> str:
        match = re.match(r"(.+?)(\d{4}-\d{2}-\d{2}\s*~\s*\d{4}-\d{2}-\d{2}|상시채용|인재풀)", text)
        if match:
            return match.group(1).strip()
        return text[:120].strip()

    def _extract_token(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    def _extract_skill_group(self, text: str) -> str:
        match = re.search(r"(프로그래밍|아트|게임 디자인|오디오|사업|게임 서비스|경영지원|개발 지원|기타)", text)
        return match.group(1).strip() if match else ""
