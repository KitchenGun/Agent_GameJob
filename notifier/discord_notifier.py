import json
import time
import requests
from datetime import datetime
from pathlib import Path
from config import Config

MESSAGE_IDS_FILE = Path("data/discord_message_ids.json")


class DiscordNotifier:
    """Discord Webhook을 통한 알림 전송"""

    def __init__(self):
        self.webhook_url = Config.DISCORD_WEBHOOK_URL
        # webhook URL에서 id/token 추출 (메시지 삭제용)
        # https://discord.com/api/webhooks/{id}/{token}
        parts = self.webhook_url.rstrip("/").split("/")
        self.webhook_id = parts[-2]
        self.webhook_token = parts[-1]

    # ──────────────────────────────────────────
    # public
    # ──────────────────────────────────────────

    def send_matches(self, matches: list[dict]):
        """이전 메시지 삭제 후 매칭 공고 전송"""
        self._delete_previous_messages()

        if not matches:
            self._send_and_track({"content": "🔍 새로운 매칭 공고가 없습니다."})
            return

        header = {
            "content": (
                f"🎮 **게임 프로그래머 채용 매칭 알림**\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"📊 매칭된 공고: **{len(matches)}건**\n"
                f"{'─' * 40}"
            )
        }
        self._send_and_track(header)

        for i, match in enumerate(matches, 1):
            job       = match["job"]
            score     = match["score"]
            reasons   = match.get("reasons", [])
            breakdown = match.get("breakdown", {})

            # Google Sheets(한글 키) / 크롤러(영문 키) 모두 지원
            title    = job.get("title")      or job.get("제목",    "제목 없음")
            company  = job.get("company")    or job.get("회사명",  "미상")
            location = job.get("location")   or job.get("근무지역", "미상")
            exp      = job.get("experience") or job.get("경력요건", "미상")
            skills   = job.get("skills")     or job.get("기술스택", "정보 없음")
            deadline = job.get("deadline")   or job.get("마감일",  "미상")
            source   = job.get("source")     or job.get("사이트",  "")
            url      = job.get("url")        or job.get("공고URL", "")
            job_id   = job.get("job_id")     or job.get("공고ID",  "")

            # 점수 산정 상세 텍스트
            score_detail = self._format_breakdown(breakdown)

            embed = {
                "title": f"#{i} {title}",
                "url": url or None,
                "color": self._score_color(score),
                "fields": [
                    {"name": "🏢 회사",      "value": company or "미상",  "inline": True},
                    {"name": "📊 매칭 점수", "value": f"**{score:.0%}**", "inline": True},
                    {"name": "📍 위치",      "value": location or "미상", "inline": True},
                    {"name": "💼 경력",      "value": exp or "미상",      "inline": True},
                    {
                        "name": "🛠️ 기술스택",
                        "value": (skills or "정보 없음")[:200],
                        "inline": False,
                    },
                    {
                        "name": "📈 점수 산정",
                        "value": score_detail,
                        "inline": False,
                    },
                    {
                        "name": "✅ 매칭 이유 / 이력서 비교",
                        "value": "\n".join(f"• {r}" for r in reasons)[:900] or "일반 매칭",
                        "inline": False,
                    },
                    {"name": "📅 마감일", "value": deadline or "미상", "inline": True},
                    {"name": "🌐 출처",   "value": source or "미상",   "inline": True},
                ],
                "footer": {"text": f"공고 ID: {job_id}"},
            }
            if not embed["url"]:
                del embed["url"]

            self._send_and_track({"embeds": [embed]})
            time.sleep(0.5)

    # ──────────────────────────────────────────
    # private
    # ──────────────────────────────────────────

    def _send_and_track(self, payload: dict):
        """메시지 전송 후 message_id 저장"""
        try:
            resp = requests.post(
                self.webhook_url + "?wait=true",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            msg_id = resp.json().get("id")
            if msg_id:
                self._save_message_id(msg_id)
        except requests.RequestException as e:
            print(f"Discord 전송 실패: {e}")

    def _delete_previous_messages(self):
        """저장된 이전 메시지 ID를 모두 삭제"""
        ids = self._load_message_ids()
        if not ids:
            return

        delete_url = (
            f"https://discord.com/api/webhooks"
            f"/{self.webhook_id}/{self.webhook_token}/messages/{{msg_id}}"
        )
        deleted = 0
        for msg_id in ids:
            try:
                resp = requests.delete(
                    delete_url.format(msg_id=msg_id),
                    timeout=10,
                )
                if resp.status_code in (204, 404):
                    deleted += 1
                time.sleep(0.3)
            except requests.RequestException:
                pass

        print(f"  이전 Discord 메시지 {deleted}건 삭제")
        MESSAGE_IDS_FILE.write_text("[]", encoding="utf-8")

    def _save_message_id(self, msg_id: str):
        ids = self._load_message_ids()
        ids.append(msg_id)
        MESSAGE_IDS_FILE.write_text(json.dumps(ids), encoding="utf-8")

    def _load_message_ids(self) -> list:
        if MESSAGE_IDS_FILE.exists():
            try:
                return json.loads(MESSAGE_IDS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _format_breakdown(self, breakdown: dict) -> str:
        """점수 산정 상세 포맷"""
        if not breakdown:
            return "산정 정보 없음"

        weights = {
            "기술스택":    0.25,
            "Unreal보너스": 0.10,
            "게임업계":    0.10,
            "프로젝트경험": 0.15,
            "경력조건":    0.15,
            "내용유사도":  0.10,
            "직무키워드":  0.15,
        }
        lines = []
        for key, w in weights.items():
            val = breakdown.get(key, 0.0)
            contrib = val * w
            bar = "█" * int(val * 5) + "░" * (5 - int(val * 5))
            lines.append(f"`{key:<10}` {bar} {val:.2f} × {w:.0%} = **{contrib:.3f}**")

        total = breakdown.get("최종점수", 0.0)
        lines.append(f"\n**최종 점수: {total:.3f} ({total:.0%})**")
        return "\n".join(lines)

    def _score_color(self, score: float) -> int:
        if score >= 0.75:
            return 0x00FF00   # 초록 — 높음
        elif score >= 0.55:
            return 0xFFFF00   # 노랑 — 보통
        elif score >= 0.40:
            return 0xFFA500   # 주황 — 낮음
        else:
            return 0xFF4444   # 빨강 — 미달
