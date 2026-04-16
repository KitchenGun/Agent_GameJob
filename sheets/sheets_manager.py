import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from config import Config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsManager:
    CLOSED_MARKERS = (
        "접수마감",
        "모집마감",
        "채용마감",
        "채용 종료",
        "채용종료",
        "마감됨",
        "공고마감",
        "closed",
    )

    def __init__(self):
        creds = Credentials.from_service_account_file(
            Config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
        )
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open(Config.SPREADSHEET_NAME)

    def get_or_create_worksheet(self, title, headers=None):
        """워크시트가 없으면 생성, 있으면 반환"""
        try:
            ws = self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=title, rows=1000, cols=20)
            if headers:
                ws.update("A1", [headers])
        return ws

    def reset_jobs(self):
        """채용공고 시트 초기화 (헤더 유지, 데이터 전체 삭제)"""
        ws = self.get_or_create_worksheet(
            "채용공고_로우데이터",
            headers=[
                "공고ID", "사이트", "회사명", "제목", "직무",
                "경력요건", "기술스택", "학력", "근무지역",
                "급여", "마감일", "공고URL", "수집일시", "상태"
            ],
        )
        ws.clear()
        ws.update("A1", [[
            "공고ID", "사이트", "회사명", "제목", "직무",
            "경력요건", "기술스택", "학력", "근무지역",
            "급여", "마감일", "공고URL", "수집일시", "상태"
        ]])
        print("  채용공고 시트 초기화 완료")

    def append_jobs(self, jobs: list[dict]):
        """채용공고 데이터를 시트에 추가 (중복 제거)"""
        ws = self.get_or_create_worksheet(
            "채용공고_로우데이터",
            headers=[
                "공고ID", "사이트", "회사명", "제목", "직무",
                "경력요건", "기술스택", "학력", "근무지역",
                "급여", "마감일", "공고URL", "수집일시", "상태"
            ],
        )
        existing = self._ws_to_records(ws)
        existing_ids = {row.get("공고ID") for row in existing}

        new_jobs = [j for j in jobs if j.get("job_id") not in existing_ids]
        if not new_jobs:
            print("새로운 공고가 없습니다.")
            return 0

        rows = []
        for j in new_jobs:
            rows.append([
                j.get("job_id", ""),
                j.get("source", ""),
                j.get("company", ""),
                j.get("title", ""),
                j.get("position", ""),
                j.get("experience", ""),
                j.get("skills", ""),
                j.get("education", ""),
                j.get("location", ""),
                j.get("salary", ""),
                j.get("deadline", ""),
                j.get("url", ""),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "신규",
            ])

        ws.append_rows(rows)
        print(f"{len(rows)}건의 신규 공고 추가 완료")
        return len(rows)

    def save_resume_data(self, resume_data: dict):
        """이력서 로우데이터를 별도 시트에 저장"""
        ws = self.get_or_create_worksheet(
            "이력서_로우데이터",
            headers=["항목", "내용", "업데이트일시"],
        )
        ws.clear()
        ws.update("A1", [["항목", "내용", "업데이트일시"]])

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for key, value in resume_data.items():
            if isinstance(value, list):
                value = ", ".join(value)
            rows.append([key, str(value), now])

        ws.append_rows(rows)
        print("이력서 데이터 저장 완료")

    def _ws_to_records(self, ws) -> list[dict]:
        """워크시트의 모든 값을 헤더 기반 dict 리스트로 변환"""
        values = ws.get_all_values()
        if not values:
            return []
        headers = values[0]
        return [
            {headers[i]: row[i] if i < len(row) else ""
             for i in range(len(headers)) if headers[i]}
            for row in values[1:]
            if any(row)
        ]

    def get_all_jobs(self):
        """모든 채용공고 로우데이터 반환"""
        ws = self.get_or_create_worksheet("채용공고_로우데이터")
        return self._ws_to_records(ws)

    def get_jobs_by_status(self, status: str) -> list[dict]:
        """특정 상태의 채용공고만 반환"""
        return [
            row for row in self.get_all_jobs()
            if (row.get("상태") or "").strip() == status
        ]

    def get_resume_data(self):
        """이력서 로우데이터 반환"""
        ws = self.get_or_create_worksheet("이력서_로우데이터")
        records = self._ws_to_records(ws)
        return {row["항목"]: row["내용"] for row in records if "항목" in row}

    def cleanup_closed_jobs(self) -> int:
        """시트에 저장된 마감 공고를 '만료' 상태로 정리"""
        jobs = self.get_all_jobs()
        expired_job_ids = []

        for job in jobs:
            status = (job.get("상태") or "").strip()
            if status == "만료":
                continue

            if self._is_closed_posting(
                job.get("마감일", ""),
                job.get("제목", ""),
                job.get("직무", ""),
                job.get("기술스택", ""),
            ):
                job_id = (job.get("공고ID") or "").strip()
                if job_id:
                    expired_job_ids.append(job_id)

        if not expired_job_ids:
            print("  정리할 마감 공고가 없습니다.")
            return 0

        self.bulk_update_job_status(expired_job_ids, "만료")
        print(f"  마감 공고 정리 완료: {len(expired_job_ids)}건")
        return len(expired_job_ids)

    def _is_closed_posting(self, *texts: str) -> bool:
        normalized = " ".join(
            str(text).strip().lower() for text in texts if text and str(text).strip()
        )
        if not normalized:
            return False

        if "채용시" in normalized or "상시" in normalized:
            return False

        return any(marker in normalized for marker in self.CLOSED_MARKERS)

    def update_job_status(self, job_id: str, status: str):
        """공고 상태 업데이트 (신규/매칭됨/알림완료/만료)"""
        self.bulk_update_job_status([job_id], status)

    def bulk_update_job_status(self, job_ids: list[str], status: str):
        """공고 상태 일괄 업데이트"""
        if not job_ids:
            return
        ws = self.spreadsheet.worksheet("채용공고_로우데이터")
        all_ids = ws.col_values(1)  # A열 전체 (job_id 컬럼)
        updates = []
        for job_id in job_ids:
            try:
                row = all_ids.index(job_id) + 1  # 1-based
                updates.append({
                    "range": f"N{row}",
                    "values": [[status]],
                })
            except ValueError:
                pass
        if updates:
            ws.batch_update(updates)
            print(f"  상태 업데이트: {len(updates)}건 → '{status}'")
