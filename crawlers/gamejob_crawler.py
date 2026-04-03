from playwright.sync_api import sync_playwright
from crawlers.base_crawler import BaseCrawler, JobPosting
from bs4 import BeautifulSoup


class GameJobCrawler(BaseCrawler):
    """게임잡(GameJob.co.kr) 크롤러"""

    BASE_URL = "https://www.gamejob.co.kr"
    SOURCE = "게임잡"

    def crawl(self, keywords: list[str], max_pages: int = 5) -> list[dict]:
        results = []

        with sync_playwright() as p:
            browser, context = self._create_browser_context(p)
            page = context.new_page()

            for keyword in keywords:
                try:
                    search_url = f"{self.BASE_URL}/List_GI/GIB_SearchList.asp"
                    page.goto(search_url, wait_until="networkidle")
                    self._random_delay()

                    search_input = page.query_selector("input[name='search']")
                    if search_input:
                        search_input.fill(keyword)
                        page.keyboard.press("Enter")
                        page.wait_for_load_state("networkidle")
                        self._random_delay()

                    for page_num in range(1, max_pages + 1):
                        html = page.content()
                        jobs = self._parse_list_page(html)
                        results.extend(jobs)

                        next_btn = page.query_selector(
                            f"a[href*='page={page_num + 1}']"
                        )
                        if next_btn:
                            next_btn.click()
                            page.wait_for_load_state("networkidle")
                            self._random_delay()
                        else:
                            break

                except Exception as e:
                    print(f"[게임잡] '{keyword}' 크롤링 에러: {e}")

            browser.close()

        return [j.to_dict() for j in results]

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        """목록 페이지에서 공고 정보 파싱"""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        for item in soup.select(".recruit-item, .list-item, tr.list"):
            try:
                job = JobPosting(source=self.SOURCE)

                company_el = item.select_one(".company, .co-name")
                job.company = company_el.get_text(strip=True) if company_el else ""

                title_el = item.select_one(".title a, .recruit-title a")
                if title_el:
                    job.title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    job.url = (
                        f"{self.BASE_URL}{href}" if not href.startswith("http")
                        else href
                    )
                    job.job_id = f"gamejob_{href.split('=')[-1] if '=' in href else hash(href)}"

                info_els = item.select(".info span, .condition span")
                for el in info_els:
                    text = el.get_text(strip=True)
                    if "경력" in text or "신입" in text:
                        job.experience = text
                    elif any(loc in text for loc in ["서울", "경기", "부산", "대전"]):
                        job.location = text

                date_el = item.select_one(".date, .deadline")
                job.deadline = date_el.get_text(strip=True) if date_el else ""

                if job.title:
                    jobs.append(job)
            except Exception as e:
                print(f"[게임잡] 파싱 에러: {e}")
                continue

        return jobs

    def _crawl_detail(self, page, job: JobPosting) -> JobPosting:
        """상세 페이지에서 추가 정보 수집"""
        try:
            page.goto(job.url, wait_until="networkidle")
            self._random_delay(1, 2)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")

            detail_text = soup.get_text()
            tech_keywords = [
                "C++", "C#", "Unity", "Unreal", "Python", "Java",
                "DirectX", "OpenGL", "Vulkan", "서버", "클라이언트",
                "네트워크", "AI", "물리엔진", "셰이더", "UE5", "UE4",
            ]
            found_skills = [kw for kw in tech_keywords if kw.lower() in detail_text.lower()]
            job.skills = ", ".join(found_skills)

            salary_el = soup.select_one(".salary, .pay")
            if salary_el:
                job.salary = salary_el.get_text(strip=True)

        except Exception as e:
            print(f"상세 페이지 크롤링 실패: {e}")

        return job
