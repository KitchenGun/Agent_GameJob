import time
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from crawlers.base_crawler import BaseCrawler, JobPosting
from crawlers.detail_crawler import crawl_detail


class GameJobCrawler(BaseCrawler):
    """게임잡(GameJob.co.kr) 크롤러 - 직종/지역/플랫폼 필터 적용"""

    BASE_URL = "https://www.gamejob.co.kr"
    SOURCE = "게임잡"

    # 필터 값: 게임개발(클라이언트), 서울+경기, 온라인PC+콘솔+멀티플랫폼
    FILTER_DUTY   = "1"          # 게임개발(클라이언트)
    FILTER_LOCAL  = "I000,B000"  # 서울, 경기
    FILTER_DIVICE = "1,4,5"      # 온라인PC게임(1), 콘솔게임(4), 멀티플랫폼게임(5)

    AJAX_URL      = f"{BASE_URL}/Recruit/_GI_Job_List/"
    COUNT_URL     = f"{BASE_URL}/Recruit/_SearchCount/"
    PAGE_SIZE     = 40

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": f"{BASE_URL}/Recruit/joblist",
        "X-Requested-With": "XMLHttpRequest",
    }

    def crawl(self, keywords: list[str], max_pages: int = 5) -> list[dict]:
        """필터 기반 AJAX 크롤링 + 상세 페이지 크롤링"""
        results = []
        seen_ids: set[str] = set()

        # 전체 공고 수 확인
        try:
            r = requests.post(self.COUNT_URL, headers=self._HEADERS,
                              data=self._build_condition(page=1), timeout=15)
            total = int(r.text.strip()) if r.text.strip().isdigit() else 0
            print(f"  [게임잡] 필터 적용 공고: {total}건")
        except Exception:
            total = 0

        # 목록 수집
        for page_num in range(1, max_pages + 1):
            try:
                resp = requests.post(self.AJAX_URL, headers=self._HEADERS,
                                     data=self._build_condition(page=page_num), timeout=20)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [게임잡] 페이지 {page_num} 요청 실패: {e}")
                break

            jobs = self._parse_response(resp.text)
            if not jobs:
                break
            for job in jobs:
                if job.job_id not in seen_ids:
                    seen_ids.add(job.job_id)
                    results.append(job)
            time.sleep(1)

        # 상세 페이지 크롤링 (기술스택 + OCR + 자사사이트)
        if results:
            print(f"  [게임잡] 상세 크롤링 시작 ({len(results)}건)...")
            with sync_playwright() as p:
                browser, context = self._create_browser_context(p)
                page = context.new_page()
                for i, job in enumerate(results):
                    try:
                        detail = crawl_detail(page, job.url, "gamejob.co.kr")
                        if detail["skills_text"]:
                            job.skills = detail["skills_text"]
                        if detail["external_url"]:
                            print(f"    자사사이트 발견: {detail['external_url'][:60]}")
                    except Exception as e:
                        print(f"    상세 실패 [{job.job_id}]: {e}")
                    self._random_delay(0.5, 1.5)
                browser.close()

        return [j.to_dict() for j in results]

    # ──────────────────────────────────────────
    # private
    # ──────────────────────────────────────────

    def _build_condition(self, page: int = 1) -> dict:
        return {
            "condition[duty]":    self.FILTER_DUTY,
            "condition[local]":   self.FILTER_LOCAL,
            "condition[divice]":  self.FILTER_DIVICE,
            "condition[menucode]": "filter",
            "condition[pageIndex]": str(page),
            "condition[pageSize]":  str(self.PAGE_SIZE),
        }

    def _parse_response(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        tabcont = soup.find("div", class_="tabCont on")
        if not tabcont:
            return jobs

        rows = tabcont.find_all("tr")
        for row in rows[1:]:  # 헤더 skip
            job = self._parse_row(row)
            if job:
                jobs.append(job)

        return jobs

    def _parse_row(self, row) -> JobPosting:
        tds = row.find_all("td")
        if len(tds) < 2:
            return None

        job = JobPosting(source=self.SOURCE)

        # 회사명
        co = tds[0].select_one("div.company strong, div.company a")
        job.company = co.get_text(strip=True) if co else ""

        # 제목 / URL / ID
        title_el = tds[1].select_one("div.tit a[href*='GI_No']")
        if not title_el:
            return None
        job.title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        job.url = f"{self.BASE_URL}{href}" if not href.startswith("http") else href
        gi_no = href.split("GI_No=")[-1].split("&")[0] if "GI_No=" in href else str(hash(href))
        job.job_id = f"gamejob_{gi_no}"

        # 경력/지역/기술
        for span in tds[1].select("p.info span"):
            text = span.get_text(strip=True)
            if "경력" in text or "신입" in text or "무관" in text:
                job.experience = text
            elif any(loc in text for loc in ["서울", "경기", "부산", "대전", "인천", "판교", "성남"]):
                job.location = text
            elif not job.skills and len(text) > 2:
                job.skills = text

        # 마감일
        if len(tds) >= 3:
            date_el = tds[2].select_one("span.date")
            job.deadline = date_el.get_text(strip=True) if date_el else ""

        if self._is_closed_posting(job.deadline, row.get_text(" ", strip=True)):
            return None

        return job if job.title else None
