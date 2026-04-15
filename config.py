import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Google Sheets
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
    SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "게임프로그래머_채용공고")

    # Discord (deprecated: Hermes Agent가 직접 전송)
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

    # Hermes Agent file queue
    HERMES_QUEUE_DIR = os.getenv("HERMES_QUEUE_DIR", "data/hermes_queue")
    HERMES_RESPONSE_TIMEOUT_SECONDS = int(
        os.getenv("HERMES_RESPONSE_TIMEOUT_SECONDS", 0)
    )

    # 크롤링
    CRAWL_INTERVAL_HOURS = int(os.getenv("CRAWL_INTERVAL_HOURS", 6))
    MAX_PAGES_PER_SITE = int(os.getenv("MAX_PAGES_PER_SITE", 5))

    # 매칭
    MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0.5))

    # 크롤링 키워드
    SEARCH_KEYWORDS = [
        "게임 프로그래머",
        "게임 클라이언트 프로그래머",
        "게임 서버 프로그래머",
        "언리얼 프로그래머",
        "Unity 프로그래머",
    ]
