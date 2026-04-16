from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from crawlers.base_crawler import BaseCrawler
from crawlers.base_crawler import JobPosting


class KraftonCrawler(BaseCrawler):
    """크래프톤 채용 공고 크롤러."""

    BASE_URL = "https://www.krafton.com"
    LIST_URL = f"{BASE_URL}/careers/jobs/"
    SOURCE = "KRAFTON Careers"
    PAGE_SIZE = 10

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def crawl(self, keywords: list[str], max_pages: int = 5) -> list[dict]:
        del keywords
        results: list[JobPosting] = []
        seen_ids: set[str] = set()

        for page_num in range(1, max_pages + 1):
            try:
                response = requests.get(
                    self._page_url(page_num),
                    headers=self._HEADERS,
                    timeout=20,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                print(f"[크래프톤] 페이지 {page_num} 요청 실패: {exc}")
                break

            jobs = self._parse_list_page(response.text)
            if not jobs:
                break

            new_count = 0
            for job in jobs:
                if job.job_id in seen_ids:
                    continue
                seen_ids.add(job.job_id)
                results.append(job)
                new_count += 1

            if new_count == 0:
                break

        return [job.to_dict() for job in results]

    def _page_url(self, page_num: int) -> str:
        return f"{self.LIST_URL}?var_page={page_num}&search_list_cnt={self.PAGE_SIZE}"

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[JobPosting] = []

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            if "/careers/recruit-detail/" not in href:
                continue

            title = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
            if not title:
                continue

            job_id_match = re.search(r"[?&]job=(\d+)", href)
            if not job_id_match:
                continue

            parent = link.find_parent("li") or link.find_parent("article") or link.parent
            context_text = re.sub(r"\s+", " ", parent.get_text(" ", strip=True)).strip() if parent else ""
            meta_items = [item.strip() for item in context_text.split("-") if item.strip()]

            company = "크래프톤"
            skills = ""
            experience = ""
            location = ""

            if len(meta_items) >= 2:
                company = meta_items[1] if len(meta_items) > 1 else company
            if len(meta_items) >= 3:
                skills = meta_items[2]
            if len(meta_items) >= 4:
                experience = meta_items[3]
            if len(meta_items) >= 5:
                location = meta_items[4]

            jobs.append(
                JobPosting(
                    job_id=f"krafton_{job_id_match.group(1)}",
                    source=self.SOURCE,
                    company=company,
                    title=title,
                    position=title,
                    experience=experience,
                    skills=skills,
                    location=location,
                    url=urljoin(self.BASE_URL, href),
                )
            )

        return jobs
