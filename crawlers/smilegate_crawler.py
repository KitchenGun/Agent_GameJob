from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from crawlers.base_crawler import BaseCrawler
from crawlers.base_crawler import JobPosting


class SmilegateCrawler(BaseCrawler):
    """스마일게이트 채용 공고 크롤러."""

    BASE_URL = "https://careers.smilegate.com"
    LIST_URL = f"{BASE_URL}/apply"
    SOURCE = "Smilegate Careers"

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
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                self._random_delay(2, 4)
                html = page.content()
                for job in self._parse_list_page(html):
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        results.append(job)
            except Exception as exc:
                print(f"[스마일게이트] 크롤링 에러: {exc}")
            finally:
                browser.close()

        return [job.to_dict() for job in results]

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = urljoin(self.BASE_URL, link.get("href", "").strip())
            lowered = href.lower()
            if "/apply/" not in lowered or any(token in lowered for token in ["/apply$", "/apply?", "/apply/"]):
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
            if not title or title in {"APPLY", "지원하기", "입사지원"}:
                continue

            container = link.find_parent(["li", "div", "article"])
            context_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True)).strip() if container else ""
            job_id_match = re.search(r"(seq|id|jobId|job)=([A-Za-z0-9_-]+)", href)
            job_id = f"smilegate_{job_id_match.group(2)}" if job_id_match else f"smilegate_{abs(hash(href))}"

            jobs.append(
                JobPosting(
                    job_id=job_id,
                    source=self.SOURCE,
                    company="스마일게이트",
                    title=title,
                    position=title,
                    experience=self._extract_token(context_text, r"(신입|경력무관|경력\d+년[^\s]*|경력|인턴|계약직)") ,
                    skills=self._extract_token(context_text, r"(개발|기술|디자인|사업|운영|모바일운영|게임운영|PM|QA|클라이언트)") ,
                    location=self._extract_token(context_text, r"(성남|판교|서울|경기)[^|,/]*"),
                    deadline=self._extract_token(context_text, r"(\d{4}\.\d{2}\.\d{2}|\d{4}-\d{2}-\d{2}|상시채용|마감)") ,
                    url=href,
                )
            )

        return jobs

    def _extract_token(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""
