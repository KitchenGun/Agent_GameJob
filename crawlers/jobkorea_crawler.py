from playwright.sync_api import sync_playwright
from crawlers.base_crawler import BaseCrawler, JobPosting
from crawlers.detail_crawler import crawl_detail
from bs4 import BeautifulSoup
import urllib.parse
import re


class JobKoreaCrawler(BaseCrawler):
    """잡코리아(jobkorea.co.kr) 크롤러"""

    BASE_URL = "https://www.jobkorea.co.kr"
    SOURCE = "잡코리아"

    # 필터 조건 (서버 프로그래머 제외)
    FILTER_KEYWORDS = ["게임 클라이언트 프로그래머", "언리얼 프로그래머", "Unity 프로그래머"]
    FILTER_LOCAL    = "I000,B000"  # 서울, 경기 (jobkorea 포맷)

    # 게임 관련 공고 판별 키워드 (하나라도 제목에 포함 시 게임 공고로 판단)
    GAME_TITLE_KEYWORDS = [
        "게임", "game", "클라이언트", "client", "언리얼", "unreal", "unity", "유니티",
        "엔진", "engine", "그래픽스", "렌더링", "rendering", "콘텐츠",
    ]

    def crawl(self, keywords: list[str], max_pages: int = 5) -> list[dict]:
        results = []
        seen_ids = set()

        with sync_playwright() as p:
            browser, context = self._create_browser_context(p)
            page = context.new_page()

            # 사용자 지정 keywords 대신 필터 조건에 맞는 키워드 사용
            search_keywords = self.FILTER_KEYWORDS

            for keyword in search_keywords:
                try:
                    encoded = urllib.parse.quote(keyword)
                    # 서울(I000), 경기(B000) 지역 필터 추가
                    search_url = (
                        f"{self.BASE_URL}/Search/?stext={encoded}"
                        f"&tabType=recruit&local=I000&local=B000"
                    )
                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    self._random_delay(3, 5)

                    for page_num in range(1, max_pages + 1):
                        html = page.content()
                        jobs = self._parse_list_page(html)
                        for job in jobs:
                            if job.job_id not in seen_ids:
                                seen_ids.add(job.job_id)
                                results.append(job)

                        # 다음 페이지 버튼
                        next_btn = page.query_selector(
                            f"a[href*='Page={page_num + 1}'], button[data-page='{page_num + 1}']"
                        )
                        if next_btn:
                            next_btn.click()
                            page.wait_for_load_state("domcontentloaded")
                            self._random_delay(2, 4)
                        else:
                            break

                except Exception as e:
                    print(f"[잡코리아] '{keyword}' 크롤링 에러: {e}")

            # 상세 페이지 크롤링 (기술스택 + OCR + 자사사이트)
            new_results = [j for j in results if not j.skills]
            if new_results:
                print(f"  [잡코리아] 상세 크롤링 시작 ({len(new_results)}건)...")
                for i, job in enumerate(new_results):
                    try:
                        detail = crawl_detail(page, job.url, "jobkorea.co.kr")
                        if detail["skills_text"]:
                            job.skills = detail["skills_text"]
                        if detail["external_url"]:
                            print(f"    자사사이트 발견: {detail['external_url'][:60]}")
                    except Exception as e:
                        print(f"    상세 실패 [{job.job_id}]: {e}")
                    self._random_delay(0.5, 1.5)

            browser.close()

        return [j.to_dict() for j in results]

    def _parse_list_page(self, html: str) -> list[JobPosting]:
        """잡코리아 검색결과 페이지 파싱"""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # GI_Read 링크를 포함한 공고 컨테이너 탐색
        gi_links = soup.find_all("a", href=re.compile(r"/Recruit/GI_Read/\d+"))
        seen_hrefs = set()

        for link in gi_links:
            href = link.get("href", "")
            # 제목 링크만 처리 (텍스트가 있는 링크)
            title_text = link.get_text(strip=True)
            if not title_text or href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            try:
                job = JobPosting(source=self.SOURCE)
                job.title = title_text

                # URL 및 Job ID
                job.url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                gno_match = re.search(r"/GI_Read/(\d+)", href)
                job.job_id = f"jobkorea_{gno_match.group(1)}" if gno_match else f"jobkorea_{hash(href)}"

                # 부모 컨테이너에서 회사명, 조건 등 추출
                container = link.find_parent("div", class_=re.compile(r"p-7|gap-5"))
                if not container:
                    container = link.find_parent("div")

                if container:
                    # 회사명: 두 번째 링크의 텍스트
                    all_links = container.find_all("a", href=re.compile(r"/Recruit/GI_Read/"))
                    for al in all_links:
                        text = al.get_text(strip=True)
                        if text and text != job.title:
                            job.company = text
                            break

                    # 칩 정보 (지역, 경력, 스킬 등)
                    chips = container.find_all("span", class_=re.compile(r"text-typo-b4"))
                    chip_texts = [c.get_text(strip=True) for c in chips if c.get_text(strip=True)]
                    for text in chip_texts:
                        if any(loc in text for loc in ["서울", "경기", "부산", "대전", "인천", "판교", "성남", "수원"]):
                            job.location = text
                        elif "경력" in text or "신입" in text or "무관" in text:
                            job.experience = text
                        elif not job.skills:
                            job.skills = text

                if job.title and self._is_game_job(job.title):
                    jobs.append(job)
                elif job.title:
                    pass  # 게임 무관 공고 제외
            except Exception as e:
                print(f"[잡코리아] 파싱 에러: {e}")

        return jobs

    def _is_game_job(self, title: str) -> bool:
        """제목 기준으로 게임 관련 공고 여부 판별"""
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.GAME_TITLE_KEYWORDS)
