import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import Config


@dataclass
class JobManagementRequest:
    request_id: str
    request_file: Path
    requested_job_ids: list[str]
    response_file: Path


class JobManagementAgent:
    """Hermes Agent에 작업 관리 요청을 넘기는 오케스트레이터."""

    def __init__(self, sheets):
        self.sheets = sheets
        self.queue_dir = Path(Config.HERMES_QUEUE_DIR)
        self.requests_dir = self.queue_dir / "requests"
        self.responses_dir = self.queue_dir / "responses"

    def request_job_management(self, jobs: list[dict] | None = None) -> JobManagementRequest | None:
        resume_data = self.sheets.get_resume_data()
        if not resume_data:
            print("이력서 데이터가 없습니다. 먼저 이력서를 파싱하세요.")
            return None

        target_jobs = jobs if jobs is not None else self.sheets.get_jobs_by_status("신규")
        target_jobs = [job for job in target_jobs if self._job_has_minimum_data(job)]

        if not target_jobs:
            print("Hermes Agent에 전달할 신규 공고가 없습니다.")
            return None

        request_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)

        request_file = self.requests_dir / f"job_management_request_{request_id}.json"
        response_file = self.responses_dir / f"job_management_response_{request_id}.json"
        normalized_jobs = [self._normalize_job(job) for job in target_jobs]
        requested_job_ids = [job["job_id"] for job in normalized_jobs if job.get("job_id")]

        payload = {
            "request_id": request_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "type": "job_management",
            "delivery_owner": "hermes_agent",
            "instructions": {
                "goal": (
                    "이력서와 채용공고 로우데이터를 바탕으로 Hermes Agent가 직접 공고를 선별하고, "
                    "요약/판단을 수행한 뒤 Discord 메시지를 전송한다."
                ),
                "must_do": [
                    "기존 파이썬 내부 점수식, threshold, top-N 방식에 의존하지 말 것",
                    "이력서와 공고 원문을 읽고 적합한 공고만 스스로 선별할 것",
                    "선별 근거를 한국어로 요약할 것",
                    "Discord 메시지 전송을 Hermes Agent가 직접 수행할 것",
                    "처리 후 response_file 경로에 결과 JSON을 기록할 것",
                ],
                "must_not_do": [
                    "Python의 legacy matcher 점수를 참조하지 말 것",
                    "전송 책임을 Python webhook 코드로 되돌리지 말 것",
                    "선정 이유 없이 공고를 나열하지 말 것",
                ],
                "response_contract": {
                    "response_file": str(response_file),
                    "required_fields": [
                        "request_id",
                        "status",
                        "selected_job_ids",
                        "summary",
                        "discord_sent",
                    ],
                },
            },
            "candidate_profile": resume_data,
            "jobs": normalized_jobs,
        }
        request_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if requested_job_ids:
            self.sheets.bulk_update_job_status(requested_job_ids, "에이전트요청됨")

        print(f"Hermes 요청 파일 생성: {request_file}")
        print(f"Hermes 응답 파일 경로: {response_file}")

        return JobManagementRequest(
            request_id=request_id,
            request_file=request_file,
            requested_job_ids=requested_job_ids,
            response_file=response_file,
        )

    def _normalize_job(self, job: dict) -> dict:
        return {
            "job_id": job.get("job_id") or job.get("공고ID", ""),
            "source": job.get("source") or job.get("사이트", ""),
            "company": job.get("company") or job.get("회사명", ""),
            "title": job.get("title") or job.get("제목", ""),
            "position": job.get("position") or job.get("직무", ""),
            "experience": job.get("experience") or job.get("경력요건", ""),
            "skills": job.get("skills") or job.get("기술스택", ""),
            "education": job.get("education") or job.get("학력", ""),
            "location": job.get("location") or job.get("근무지역", ""),
            "salary": job.get("salary") or job.get("급여", ""),
            "deadline": job.get("deadline") or job.get("마감일", ""),
            "url": job.get("url") or job.get("공고URL", ""),
            "status": job.get("status") or job.get("상태", ""),
            "raw": job,
        }

    def _job_has_minimum_data(self, job: dict) -> bool:
        title = job.get("title") or job.get("제목", "")
        company = job.get("company") or job.get("회사명", "")
        url = job.get("url") or job.get("공고URL", "")
        return any([title, company, url])
