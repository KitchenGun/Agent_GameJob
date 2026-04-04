"""
공고 상세 페이지 크롤러
- 전체 텍스트 추출
- 이미지 OCR (easyocr)
- 자사 채용사이트 링크 탐지 및 추가 크롤링
"""
import io
import re
import time
import requests
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# OCR 리더 (최초 호출 시 모델 다운로드, 이후 재사용)
_ocr_reader = None


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
            print("  [OCR] easyocr 모델 로드 완료")
        except Exception as e:
            print(f"  [OCR] easyocr 로드 실패: {e}")
    return _ocr_reader


# 잡 포털 도메인 (외부 채용사이트 탐지 시 제외)
_JOB_PORTAL_DOMAINS = {
    "gamejob.co.kr", "jobkorea.co.kr", "saramin.co.kr",
    "wanted.co.kr", "linkedin.com", "incruit.com",
    "jumpit.co.kr", "programmers.co.kr", "rocketpunch.com",
}

# 기술스택 키워드 사전
_TECH_KEYWORDS = [
    "C++", "C#", "Python", "Java", "Go", "Rust", "Kotlin", "Swift",
    "JavaScript", "TypeScript", "Lua", "Verse", "Blueprints",
    "Unreal", "UE4", "UE5", "Unity", "CryEngine", "Godot",
    "DirectX", "OpenGL", "Vulkan", "Metal", "WebGL",
    "Git", "SVN", "Perforce", "GitLab", "GitHub",
    "MMORPG", "RPG", "FPS", "RTS", "SNG",
    "멀티플레이", "네트워크", "렌더링", "물리엔진", "셰이더",
    "Android", "iOS", "PC", "Console", "AR", "VR", "XR",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes",
]


def crawl_detail(playwright_page, url: str, source_domain: str) -> dict:
    """
    공고 상세 페이지 크롤링.
    playwright_page: 이미 열려 있는 Playwright Page 객체
    url: 상세 페이지 URL
    source_domain: 출처 도메인 (gamejob.co.kr 등)

    Returns:
        {
            "detail_text": str,   # 전체 텍스트
            "skills_text": str,   # 기술스택 추출 결과
            "external_url": str,  # 자사 채용사이트 URL (없으면 "")
        }
    """
    result = {"detail_text": "", "skills_text": "", "external_url": ""}

    try:
        playwright_page.goto(url, wait_until="domcontentloaded", timeout=25000)
        time.sleep(1.5)
        html = playwright_page.content()
    except Exception as e:
        print(f"    [상세] 로드 실패 {url[:60]}: {e}")
        return result

    soup = BeautifulSoup(html, "lxml")

    # ── 1. 본문 텍스트 추출 ──────────────────────────
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    detail_text = soup.get_text(separator=" ", strip=True)
    result["detail_text"] = detail_text[:6000]

    # ── 2. 기술스택 키워드 추출 ──────────────────────
    found = _extract_tech_keywords(detail_text)
    result["skills_text"] = ", ".join(found)

    # ── 3. 이미지 OCR ────────────────────────────────
    ocr_text = _run_ocr_on_images(soup, url)
    if ocr_text:
        ocr_skills = _extract_tech_keywords(ocr_text)
        extra = [s for s in ocr_skills if s not in found]
        if extra:
            result["skills_text"] += (", " if result["skills_text"] else "") + ", ".join(extra)
        result["detail_text"] += " [OCR] " + ocr_text[:1000]

    # ── 4. 자사 채용사이트 링크 탐지 ─────────────────
    external_url = _find_external_career_link(soup, source_domain)
    if external_url:
        result["external_url"] = external_url
        ext_text = _fetch_external_page(playwright_page, external_url)
        if ext_text:
            ext_skills = _extract_tech_keywords(ext_text)
            extra = [s for s in ext_skills if s not in result["skills_text"]]
            if extra:
                result["skills_text"] += (", " if result["skills_text"] else "") + ", ".join(extra)
            result["detail_text"] += " [자사사이트] " + ext_text[:1000]

    return result


# ─────────────────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────────────────

def _extract_tech_keywords(text: str) -> list[str]:
    """텍스트에서 기술스택 키워드 추출"""
    found = []
    text_lower = text.lower()
    for kw in _TECH_KEYWORDS:
        if kw.lower() in text_lower and kw not in found:
            found.append(kw)
    return found


def _run_ocr_on_images(soup: BeautifulSoup, base_url: str) -> str:
    """본문 이미지에서 OCR 텍스트 추출"""
    reader = _get_ocr_reader()
    if reader is None:
        return ""

    ocr_results = []
    imgs = soup.find_all("img", src=True)

    for img in imgs[:10]:  # 최대 10장
        src = img.get("src", "")
        if not src or src.startswith("data:"):
            continue
        # 상대 경로 → 절대 경로
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            parsed = urlparse(base_url)
            src = f"{parsed.scheme}://{parsed.netloc}{src}"

        # 아이콘/로고 제외 (작은 이미지)
        width = img.get("width", "")
        if width and str(width).isdigit() and int(width) < 100:
            continue

        try:
            resp = requests.get(src, timeout=8,
                                headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                continue
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type:
                continue

            img_data = io.BytesIO(resp.content)
            result = reader.readtext(img_data.read(), detail=0, paragraph=True)
            if result:
                ocr_results.append(" ".join(result))
        except Exception:
            continue

    return " ".join(ocr_results)


def _find_external_career_link(soup: BeautifulSoup, source_domain: str) -> str:
    """자사 채용사이트 링크 탐지"""
    career_keywords = [
        "자사", "홈페이지", "바로지원", "채용사이트", "채용페이지",
        "apply", "careers", "career", "recruit", "job",
    ]
    exclude_patterns = re.compile(
        r"(javascript:|mailto:|tel:|#|\.pdf|\.jpg|\.png|\.gif)", re.I
    )

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if exclude_patterns.search(href):
            continue

        link_text = (a.get_text(strip=True) + " " + a.get("title", "")).lower()
        href_lower = href.lower()

        is_career_link = any(kw in link_text or kw in href_lower
                             for kw in career_keywords)
        if not is_career_link:
            continue

        # 외부 도메인 여부 확인
        try:
            parsed = urlparse(href if href.startswith("http") else "https://" + href)
            link_domain = parsed.netloc.replace("www.", "")
            source = source_domain.replace("www.", "")

            if link_domain and link_domain != source \
                    and not any(d in link_domain for d in _JOB_PORTAL_DOMAINS):
                return href
        except Exception:
            continue

    return ""


def _fetch_external_page(playwright_page, url: str) -> str:
    """외부 채용사이트 텍스트 추출"""
    try:
        playwright_page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(1.5)
        html = playwright_page.content()
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:4000]
    except Exception as e:
        print(f"    [외부사이트] 로드 실패 {url[:60]}: {e}")
        return ""
