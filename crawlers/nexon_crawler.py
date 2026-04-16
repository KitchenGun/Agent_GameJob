from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from crawlers.base_crawler import BaseCrawler
from crawlers.base_crawler import JobPosting


class NexonCrawler(BaseCrawler):
    """넥슨 커리어 사이트 크롤러."""

    BASE_URL = "https://careers.nexon.com"
    LIST_URL = f"{BASE_URL}/recruit"
    SOURCE = "넥슨 커리어스"

    _EXCLUDE_KEYWORDS = ("지원안내", "공지", "faq", "복지", "회사소개", "로그인")

    def crawl(self, keywords: list[str], max_pages: int = 5) -> list[dict]:
        del keywords, max_pages
        results: list[JobPosting] = []
        seen_ids: set[str] = set()

        with sync_playwright() as playwright:
            browser, context = self._create_browser_context(playwright)
            page = context.new_page()

            try:
                page.goto(self.LIST_URL, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                self._random_delay(2, 4)
                html = page.content()
                for job in self._parse_list_page(html):
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        results.append(job)
            except Exception as exc:
                print(f"[넥슨] 크롤링 에러: {exc}")
            finally:
                browser.close()

        return [job.to_dict() for job in results]

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = urljoin(self.BASE_URL, link.get("href", "").strip())
            if not self._looks_like_job_link(href):
                continue

            title = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
            if not title or self._is_excluded_title(title):
                continue

            if href in seen_urls:
                continue
            seen_urls.add(href)

            container = link.find_parent(["li", "article", "section", "div"])
            context_text = ""
            if container is not None:
                context_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True)).strip()

            job = JobPosting(
                job_id=self._build_job_id(href),
                source=self.SOURCE,
                company="넥슨",
                title=title,
                position=title,
                experience=self._extract_experience(context_text),
                location=self._extract_location(context_text),
                deadline=self._extract_deadline(context_text),
                url=href,
            )

            if self._is_closed_posting(job.deadline, context_text):
                continue

            jobs.append(job)

        return jobs

    def _looks_like_job_link(self, href: str) -> bool:
        lowered = href.lower()
        return "/recruit" in lowered and not lowered.rstrip("/") == self.LIST_URL.lower()

    def _is_excluded_title(self, title: str) -> bool:
        lowered = title.lower()
        return any(token in lowered for token in self._EXCLUDE_KEYWORDS)

    def _build_job_id(self, href: str) -> str:
        match = re.search(r"(id|sn|job|post)=([A-Za-z0-9_-]+)", href)
        if match:
            return f"nexon_{match.group(2)}"
        return "nexon_" + hashlib.md5(href.encode("utf-8")).hexdigest()[:12]

    def _extract_experience(self, text: str) -> str:
        match = re.search(r"(신입|경력무관|인턴|계약직|정규직|경력\s*\d+년[^\s,)]*)", text)
        return match.group(1).strip() if match else ""

    def _extract_location(self, text: str) -> str:
        match = re.search(r"(서울|경기|판교|성남|강남|서초|분당|제주|부산)[^|,/]*", text)
        return match.group(0).strip() if match else ""

    def _extract_deadline(self, text: str) -> str:
        match = re.search(r"(~?\d{1,2}[./-]\d{1,2}|상시채용|채용시|접수중|마감)", text)
        return match.group(1).strip() if match else ""
