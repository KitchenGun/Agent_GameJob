from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from crawlers.base_crawler import BaseCrawler
from crawlers.base_crawler import JobPosting


class NetmarbleCrawler(BaseCrawler):
    """넷마블 채용 공고 크롤러."""

    BASE_URL = "https://career.netmarble.com"
    LIST_URL = f"{BASE_URL}/announce"
    SOURCE = "넷마블컴퍼니 채용"

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
                print(f"[넷마블] 크롤링 에러: {exc}")
            finally:
                browser.close()

        return [job.to_dict() for job in results]

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[JobPosting] = []

        for item in soup.select("li.list_wrap"):
            onclick_target = " ".join(
                filter(
                    None,
                    [
                        item.get("onclick", ""),
                        *(tag.get("onclick", "") for tag in item.select("[onclick]")),
                    ],
                )
            )
            car_anno_match = re.search(r"clickAnnoDetailBtn\((\d+)\)", onclick_target)
            if not car_anno_match:
                continue

            title_el = item.select_one("p.tit")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title:
                continue

            company_logo = item.select_one(".company_box .logo img")
            company = company_logo.get("alt", "넷마블") if company_logo else "넷마블"
            hash_tags = ", ".join(tag.get_text(" ", strip=True) for tag in item.select(".hash *") if tag.get_text(" ", strip=True))
            deadline = ""
            period_el = item.select_one("p.period")
            if period_el:
                deadline = period_el.get_text(" ", strip=True)

            jobs.append(
                JobPosting(
                    job_id=f"netmarble_{car_anno_match.group(1)}",
                    source=self.SOURCE,
                    company=company,
                    title=title,
                    position=title,
                    skills=hash_tags,
                    deadline=deadline,
                    url=urljoin(self.BASE_URL, f"/announce/detail?carAnnoId={car_anno_match.group(1)}"),
                )
            )

        return jobs
