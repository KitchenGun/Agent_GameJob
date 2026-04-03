import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config import Config


class JobMatcher:
    """이력서와 채용공고의 적합도를 계산하는 매칭 엔진"""

    def __init__(self):
        self.threshold = Config.MATCH_THRESHOLD

    def match(self, resume_data: dict, jobs: list[dict]) -> list[dict]:
        """
        이력서 데이터와 채용공고 리스트를 비교하여
        적합도가 threshold 이상인 공고를 반환

        반환값: [{"job": dict, "score": float, "reasons": list}, ...]
        """
        resume_text = self._build_resume_text(resume_data)
        if not resume_text.strip():
            print("이력서 데이터가 비어있습니다.")
            return []

        matched = []
        for job in jobs:
            score, reasons = self._calculate_score(resume_data, job, resume_text)
            if score >= self.threshold:
                matched.append({
                    "job": job,
                    "score": round(score, 3),
                    "reasons": reasons,
                })

        matched.sort(key=lambda x: x["score"], reverse=True)
        return matched

    def _build_resume_text(self, resume_data: dict) -> str:
        """이력서 데이터를 하나의 텍스트로 변환"""
        parts = []
        for key, value in resume_data.items():
            if isinstance(value, list):
                parts.append(" ".join(value))
            elif isinstance(value, str):
                parts.append(value)
        return " ".join(parts)

    def _calculate_score(
        self, resume_data: dict, job: dict, resume_text: str
    ) -> tuple[float, list[str]]:
        """
        종합 매칭 점수 계산

        가중치:
        - 기술스택 매칭: 40%
        - TF-IDF 코사인 유사도: 30%
        - 경력 조건 부합: 20%
        - 직무 키워드 매칭: 10%
        """
        reasons = []
        scores = {}

        # ① 기술스택 키워드 매칭 (40%)
        resume_skills = set()
        for key in resume_data:
            if key.startswith("기술스택_"):
                val = resume_data[key]
                if isinstance(val, list):
                    resume_skills.update(s.lower() for s in val)
                elif isinstance(val, str):
                    resume_skills.update(s.strip().lower() for s in val.split(","))

        job_skills_text = (
            job.get("skills", "") + " " +
            job.get("title", "") + " " +
            job.get("position", "")
        ).lower()

        if resume_skills:
            matched_skills = [s for s in resume_skills if s in job_skills_text]
            skill_score = len(matched_skills) / max(len(resume_skills), 1)
            scores["skills"] = min(skill_score * 1.5, 1.0)
            if matched_skills:
                reasons.append(f"기술 매칭: {', '.join(matched_skills)}")
        else:
            scores["skills"] = 0

        # ② TF-IDF 코사인 유사도 (30%)
        job_text = " ".join(str(v) for v in job.values() if v)
        try:
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform([resume_text, job_text])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            scores["tfidf"] = similarity
            if similarity > 0.3:
                reasons.append(f"내용 유사도: {similarity:.0%}")
        except Exception:
            scores["tfidf"] = 0

        # ③ 경력 조건 매칭 (20%)
        scores["experience"] = self._match_experience(
            resume_data.get("총경력년수", ""),
            job.get("experience", ""),
        )
        if scores["experience"] > 0.5:
            reasons.append("경력 조건 부합")

        # ④ 직무 키워드 매칭 (10%)
        job_title = job.get("title", "").lower()
        position_keywords = ["게임", "프로그래머", "개발자", "엔지니어"]
        title_match = sum(1 for kw in position_keywords if kw in job_title)
        scores["title"] = min(title_match / 2, 1.0)
        if title_match >= 2:
            reasons.append("직무명 매칭")

        final_score = (
            scores["skills"] * 0.4
            + scores["tfidf"] * 0.3
            + scores["experience"] * 0.2
            + scores["title"] * 0.1
        )

        return final_score, reasons

    def _match_experience(self, resume_exp: str, job_exp: str) -> float:
        """경력 조건 매칭 점수"""
        if not job_exp:
            return 0.5

        if "신입" in job_exp and ("신입" in resume_exp or not resume_exp):
            return 1.0
        if "무관" in job_exp:
            return 1.0

        resume_years = re.findall(r"(\d+)", resume_exp)
        job_years = re.findall(r"(\d+)", job_exp)

        if resume_years and job_years:
            r_years = int(resume_years[0])
            j_years = int(job_years[0])
            if r_years >= j_years:
                return 1.0
            elif r_years >= j_years - 1:
                return 0.7
            else:
                return 0.3

        return 0.5
