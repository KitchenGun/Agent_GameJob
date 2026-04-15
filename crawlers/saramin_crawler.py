from playwright.sync_api import sync_playwright
from crawlers.base_crawler import BaseCrawler, JobPosting
from bs4 import BeautifulSoup
import urllib.parse


class SaraminCrawler(BaseCrawler):
    """사람인(saramin.co.kr) 크롤러"""

    BASE_URL = "https://www.saramin.co.kr"
    SOURCE = "사람인"

    def crawl(self, keywords: list[str], max_pages: int = 5) -> list[dict]:
        results = []

        with sync_playwright() as p:
            browser, context = self._create_browser_context(p)
            page = context.new_page()

            for keyword in keywords:
                try:
                    encoded = urllib.parse.quote(keyword)
                    search_url = (
                        f"{self.BASE_URL}/zf_user/search/recruit"
                        f"?searchType=search&searchword={encoded}"
                        f"&recruitPage=1&recruitSort=relation"
                    )
                    page.goto(search_url, wait_until="networkidle")
                    self._random_delay(2, 4)

                    for page_num in range(1, max_pages + 1):
                        html = page.content()
                        jobs = self._parse_list_page(html)
                        results.extend(jobs)

                        next_btn = page.query_selector(
                            f".pagination a[page='{page_num + 1}']"
                        )
                        if next_btn:
                            next_btn.click()
                            page.wait_for_load_state("networkidle")
                            self._random_delay(2, 4)
                        else:
                            break

                except Exception as e:
                    print(f"[사람인] '{keyword}' 크롤링 에러: {e}")

            browser.close()

        return [j.to_dict() for j in results]

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        """사람인 검색결과 페이지 파싱"""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        for item in soup.select(".item_recruit"):
            try:
                job = JobPosting(source=self.SOURCE)

                corp = item.select_one(".corp_name a")
                job.company = corp.get_text(strip=True) if corp else ""

                title_el = item.select_one(".job_tit a")
                if title_el:
                    job.title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    job.url = (
                        f"{self.BASE_URL}{href}" if not href.startswith("http")
                        else href
                    )
                    rec_idx = href.split("rec_idx=")[-1].split("&")[0] if "rec_idx=" in href else ""
                    job.job_id = f"saramin_{rec_idx}"

                conditions = item.select(".job_condition span")
                for cond in conditions:
                    text = cond.get_text(strip=True)
                    if "경력" in text or "신입" in text:
                        job.experience = text
                    elif "학력" in text or "대졸" in text:
                        job.education = text
                    elif any(loc in text for loc in ["서울", "경기", "부산", "판교"]):
                        job.location = text

                stacks = item.select(".job_sector span")
                job.skills = ", ".join(
                    s.get_text(strip=True) for s in stacks
                )

                date_el = item.select_one(".job_date .date")
                job.deadline = date_el.get_text(strip=True) if date_el else ""

                if self._is_closed_posting(job.deadline, item.get_text(" ", strip=True)):
                    continue

                if job.title:
                    jobs.append(job)
            except Exception as e:
                print(f"[사람인] 파싱 에러: {e}")

        return jobs
