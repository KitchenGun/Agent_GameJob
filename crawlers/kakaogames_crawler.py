from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from crawlers.base_crawler import BaseCrawler
from crawlers.base_crawler import JobPosting


class KakaoGamesCrawler(BaseCrawler):
    """카카오게임즈 GreetingHR 채용 공고 크롤러."""

    BASE_URL = "https://recruit.kakaogames.com"
    LIST_URL = f"{BASE_URL}/ko/joinjuskr"
    SOURCE = "카카오게임즈 채용"
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
            print(f"[카카오게임즈] 요청 실패: {exc}")
            return []

        return [job.to_dict() for job in self._parse_list_page(response.text)]

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[JobPosting] = []
        seen_ids: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            if not re.search(r"/ko/o/\d+", href):
                continue

            job_id_match = re.search(r"/ko/o/(\d+)", href)
            if not job_id_match:
                continue
            job_id = f"kakaogames_{job_id_match.group(1)}"
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            block_text = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
            parts = [part.strip() for part in re.split(r"---|\n", block_text) if part.strip()]
            title = parts[0] if parts else block_text
            if not title:
                continue

            job_group = parts[1] if len(parts) > 1 else ""
            position = parts[2] if len(parts) > 2 else title
            deadline = self._extract_token(block_text, r"(\d{4}\.\s*\d{2}\.\s*\d{2},\s*\d{2}:\d{2}까지|D-\d+)")

            jobs.append(
                JobPosting(
                    job_id=job_id,
                    source=self.SOURCE,
                    company="카카오게임즈",
                    title=title,
                    position=position,
                    skills=job_group,
                    deadline=deadline,
                    url=urljoin(self.BASE_URL, href),
                )
            )

        return jobs

    def _extract_token(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""
