import time
import requests
from datetime import datetime
from config import Config


class DiscordNotifier:
    """Discord Webhook을 통한 알림 전송"""

    def __init__(self):
        self.webhook_url = Config.DISCORD_WEBHOOK_URL

    def send_matches(self, matches: list[dict]):
        """매칭된 공고들을 Discord로 전송"""
        if not matches:
            self._send_simple("🔍 새로운 매칭 공고가 없습니다.")
            return

        header = (
            f"🎮 **게임 프로그래머 채용 매칭 알림**\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"📊 매칭된 공고: **{len(matches)}건**\n"
            f"{'─' * 40}"
        )
        self._send_simple(header)

        for i, match in enumerate(matches[:10], 1):
            job = match["job"]
            score = match["score"]
            reasons = match.get("reasons", [])

            embed = {
                "title": f"#{i} {job.get('title', '제목 없음')}",
                "url": job.get("url", ""),
                "color": self._score_color(score),
                "fields": [
                    {
                        "name": "🏢 회사",
                        "value": job.get("company", "미상"),
                        "inline": True,
                    },
                    {
                        "name": "📊 매칭 점수",
                        "value": f"{score:.0%}",
                        "inline": True,
                    },
                    {
                        "name": "📍 위치",
                        "value": job.get("location", "미상"),
                        "inline": True,
                    },
                    {
                        "name": "💼 경력",
                        "value": job.get("experience", "미상"),
                        "inline": True,
                    },
                    {
                        "name": "🛠️ 기술스택",
                        "value": job.get("skills", "정보 없음")[:200],
                        "inline": False,
                    },
                    {
                        "name": "✅ 매칭 이유",
                        "value": "\n".join(f"• {r}" for r in reasons) or "일반 매칭",
                        "inline": False,
                    },
                    {
                        "name": "📅 마감일",
                        "value": job.get("deadline", "미상"),
                        "inline": True,
                    },
                    {
                        "name": "🌐 출처",
                        "value": job.get("source", ""),
                        "inline": True,
                    },
                ],
                "footer": {"text": f"공고 ID: {job.get('job_id', '')}"},
            }

            payload = {"embeds": [embed]}
            try:
                resp = requests.post(self.webhook_url, json=payload, timeout=10)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"Discord 전송 실패: {e}")

            time.sleep(0.5)  # rate limit 방지

    def _send_simple(self, message: str):
        """단순 텍스트 메시지 전송"""
        try:
            requests.post(
                self.webhook_url,
                json={"content": message},
                timeout=10,
            )
        except requests.RequestException as e:
            print(f"Discord 전송 실패: {e}")

    def _score_color(self, score: float) -> int:
        """매칭 점수에 따른 임베드 색상"""
        if score >= 0.8:
            return 0x00FF00   # 초록 (높은 매칭)
        elif score >= 0.6:
            return 0xFFFF00   # 노랑 (보통 매칭)
        else:
            return 0xFFA500   # 주황 (낮은 매칭)
