import re
from config import Config


# ─────────────────────────────────────────────────────
# 사용자 프로필 (이력서/경력기술서 기반)
# ─────────────────────────────────────────────────────

_USER_SKILLS = {
    "languages": ["c++", "c#", "verse", "lua", "blueprint"],
    "engines":   ["unreal", "ue4", "ue5", "uefn", "unity"],
    "tools":     ["git", "github", "svn", "perforce"],
    "graphics":  ["directx", "opengl", "hlsl", "shader", "셰이더", "렌더링"],
}

# 사용자 포트폴리오 프로젝트
_USER_PROJECTS = [
    {
        "name": "ShipmentGunGame (UEFN)",
        "engine": "unreal",
        "genre_keywords": [
            "fps", "슈터", "shooter", "배틀로얄", "battle", "gunplay", "건플레이", "총기",
        ],
        "platform_keywords": ["pc", "console", "콘솔", "포트나이트", "fortnite"],
        "feature_keywords":  ["멀티플레이", "multiplayer", "온라인", "네트워크", "pvp"],
    },
    {
        "name": "골목길",
        "engine": "unreal",
        "genre_keywords": ["action", "액션", "adventure", "어드벤처", "rpg", "3d"],
        "platform_keywords": ["pc", "콘솔"],
        "feature_keywords":  ["싱글플레이", "single"],
    },
    {
        "name": "ChairForce",
        "engine": "unreal",
        "genre_keywords": ["전략", "strategy", "시뮬레이션", "simulation", "rts"],
        "platform_keywords": ["pc"],
        "feature_keywords":  [],
    },
    {
        "name": "ForbiddenArt",
        "engine": "unreal",
        "genre_keywords": ["아트", "interactive", "인터랙티브", "art", "비주얼"],
        "platform_keywords": ["pc"],
        "feature_keywords":  [],
    },
]

# Unreal 관련 키워드
_UNREAL_KEYWORDS = ["unreal", "ue4", "ue5", "uefn", "언리얼"]
# Unity 관련 키워드
_UNITY_KEYWORDS  = ["unity", "유니티"]

# 게임 업계 공고 판별 키워드
_GAME_JOB_KEYWORDS = [
    "게임", "game", "mmorpg", "rpg", "fps", "moba", "배틀", "battle",
    "클라이언트", "언리얼", "unreal", "unity", "유니티", "콘솔", "console",
    "온라인게임", "모바일게임", "pc게임",
]

# 점수 가중치 (우선순위 순: 경력조건 > Unreal보너스 > 기술스택 > 게임업계)
_WEIGHTS = {
    "경력조건":    0.40,
    "Unreal보너스": 0.25,
    "기술스택":    0.25,
    "게임업계":    0.10,
}

# 공고에서 탐지할 기술 키워드 목록 (요건 비교용)
_TECH_KEYWORDS = [
    "c++", "c#", "python", "java", "lua", "verse", "blueprint", "typescript",
    "unreal", "ue4", "ue5", "uefn", "unity", "godot",
    "directx", "opengl", "vulkan", "metal", "hlsl", "shader", "셰이더",
    "git", "svn", "perforce", "github",
    "멀티플레이", "네트워크", "렌더링", "물리엔진", "ai", "pathfinding",
    "android", "ios", "console", "콘솔",
]


class JobMatcher:
    """이력서와 채용공고의 적합도를 계산하는 매칭 엔진"""

    def __init__(self):
        self.threshold = Config.MATCH_THRESHOLD
        # 평탄화된 사용자 스킬 목록
        self._all_user_skills: list[str] = list(
            {skill for group in _USER_SKILLS.values() for skill in group}
        )

    def match_all(self, resume_data: dict, jobs: list[dict]) -> list[dict]:
        """threshold 없이 모든 공고 점수 산출 후 내림차순 반환 (Full pipeline용)
        단, 경력조건 0점 공고(경력 2년 이상 초과)는 제외"""
        resume_text  = self._build_resume_text(resume_data)
        user_skills  = self._extract_resume_skills(resume_data)
        results = []
        for job in jobs:
            score, breakdown, reasons = self._calculate_score(
                resume_data, job, resume_text, user_skills
            )
            # 경력 조건이 완전 미달인 공고 제외
            if breakdown.get("경력조건", 1.0) == 0.0:
                continue
            results.append({
                "job":       job,
                "score":     round(score, 3),
                "breakdown": breakdown,
                "reasons":   reasons,
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def match(self, resume_data: dict, jobs: list[dict]) -> list[dict]:
        """
        이력서 데이터와 채용공고 리스트를 비교하여
        적합도가 threshold 이상인 공고를 반환

        반환값: [{"job": dict, "score": float, "breakdown": dict, "reasons": list}, ...]
        """
        resume_text = self._build_resume_text(resume_data)
        if not resume_text.strip():
            print("이력서 데이터가 비어있습니다.")
            return []

        # 이력서 데이터에서 기술스택 보강
        resume_skills = self._extract_resume_skills(resume_data)

        matched = []
        for job in jobs:
            score, breakdown, reasons = self._calculate_score(
                resume_data, job, resume_text, resume_skills
            )
            if score >= self.threshold:
                matched.append({
                    "job":       job,
                    "score":     round(score, 3),
                    "breakdown": breakdown,
                    "reasons":   reasons,
                })

        matched.sort(key=lambda x: x["score"], reverse=True)
        return matched

    # ──────────────────────────────────────────────────
    # private
    # ──────────────────────────────────────────────────

    def _build_resume_text(self, resume_data: dict) -> str:
        parts = []
        for value in resume_data.values():
            if isinstance(value, list):
                parts.append(" ".join(value))
            elif isinstance(value, str):
                parts.append(value)
        return " ".join(parts)

    def _extract_resume_skills(self, resume_data: dict) -> list[str]:
        """이력서 데이터의 기술스택 키에서 추가 스킬 추출"""
        extra: set[str] = set()
        for key, val in resume_data.items():
            if key.startswith("기술스택_"):
                if isinstance(val, list):
                    extra.update(s.lower() for s in val)
                elif isinstance(val, str):
                    extra.update(s.strip().lower() for s in val.split(","))
        return list(extra | set(self._all_user_skills))

    def _calculate_score(
        self,
        resume_data: dict,
        job: dict,
        resume_text: str,
        user_skills: list[str],
    ) -> tuple[float, dict, list[str]]:
        """
        종합 매칭 점수 계산

        가중치:
        - 기술스택 매칭:    30%
        - Unreal 보너스:    10%
        - 프로젝트 경험:    15%
        - 경력 조건:        15%
        - TF-IDF 유사도:    15%
        - 직무 키워드:      15%
        """
        reasons: list[str] = []
        breakdown: dict[str, float] = {}

        # ── 공고 텍스트 구성 ──────────────────────────
        job_text_full = " ".join(
            str(v) for v in job.values() if v and str(v).strip()
        ).lower()

        job_title_text = (
            (job.get("title") or job.get("제목", "")) + " " +
            (job.get("position") or job.get("직무", ""))
        ).lower()

        # ① 기술스택 매칭 (30%) ───────────────────────
        matched_skills = [s for s in user_skills if s and s in job_text_full]
        skill_ratio = len(matched_skills) / max(len(user_skills) * 0.4, 1)
        skill_score = min(skill_ratio, 1.0)
        breakdown["기술스택"] = round(skill_score, 3)
        if matched_skills:
            reasons.append(f"🔧 기술 매칭: {', '.join(matched_skills[:8])}")

        # ② Unreal 보너스 (10%) ───────────────────────
        is_unreal_job = any(kw in job_text_full for kw in _UNREAL_KEYWORDS)
        is_unity_job  = any(kw in job_text_full for kw in _UNITY_KEYWORDS)

        if is_unreal_job:
            unreal_score = 1.0
            reasons.append("🎮 Unreal 공고 — Unreal 우선 매칭 적용")
        else:
            unreal_score = 0.0
        breakdown["Unreal보너스"] = round(unreal_score, 3)

        # ③ 게임업계 공고 여부 (10%) ─────────────────
        game_hits = [kw for kw in _GAME_JOB_KEYWORDS if kw in job_text_full]
        game_score = min(len(game_hits) / 3, 1.0)
        breakdown["게임업계"] = round(game_score, 3)
        if game_score >= 0.67:
            reasons.append(f"🕹️ 게임업계 공고 확인: {', '.join(game_hits[:4])}")
        elif game_score > 0:
            reasons.append(f"🕹️ 게임 관련 키워드: {', '.join(game_hits[:3])}")

        # ④ 프로젝트 경험 매칭 (15%) ──────────────────
        proj_score, proj_reasons = self._match_projects(job_text_full)
        breakdown["프로젝트경험"] = round(proj_score, 3)
        reasons.extend(proj_reasons)

        # ④ 경력 조건 매칭 (15%) ──────────────────────
        exp_score = self._match_experience(
            resume_data.get("총경력년수", ""),
            job.get("experience") or job.get("경력요건", ""),
        )
        breakdown["경력조건"] = round(exp_score, 3)
        resume_yr_list = re.findall(r"\d+", resume_data.get("총경력년수", ""))
        job_exp_str = job.get("experience") or job.get("경력요건", "미상")
        r_yr_label = resume_yr_list[0] + "년" if resume_yr_list else "미기재"
        if exp_score >= 0.7:
            reasons.append(f"📅 경력 조건 충족: 보유 {r_yr_label} → 요구 {job_exp_str}")
        elif exp_score < 0.5:
            reasons.append(f"⚠️ 경력 미달 가능성: 보유 {r_yr_label} → 요구 {job_exp_str}")

        # ⑤ 직무 키워드 매칭 (20%) ───────────────────
        pos_keywords = ["게임", "프로그래머", "개발자", "클라이언트", "엔진", "언리얼", "unity", "유니티"]
        title_hits = [kw for kw in pos_keywords if kw in job_title_text]
        title_score = min(len(title_hits) / 3, 1.0)
        breakdown["직무키워드"] = round(title_score, 3)
        if title_hits:
            reasons.append(f"🏷️ 직무 키워드: {', '.join(title_hits)}")

        # ── 최종 점수 합산 ────────────────────────────
        final_score = sum(
            breakdown[k] * _WEIGHTS[k] for k in _WEIGHTS
        )
        breakdown["최종점수"] = round(final_score, 3)

        # ── 요건 비교 (담당업무/자격요건/우대사항) ────
        req_reasons = self._compare_requirements(job_text_full, user_skills)
        reasons.extend(req_reasons)

        return final_score, breakdown, reasons

    def _match_projects(self, job_text: str) -> tuple[float, list[str]]:
        """사용자 프로젝트 포트폴리오와 공고 매칭"""
        best_score = 0.0
        best_reasons: list[str] = []

        for proj in _USER_PROJECTS:
            score = 0.0
            hits: list[str] = []

            # 엔진 매칭 (0.4)
            engine_kw = proj["engine"]
            if engine_kw in job_text or (engine_kw == "unreal" and "언리얼" in job_text):
                score += 0.4
                hits.append(engine_kw.upper())

            # 장르 매칭 (0.3)
            for kw in proj["genre_keywords"]:
                if kw in job_text:
                    score += 0.3
                    hits.append(kw)
                    break

            # 플랫폼 매칭 (0.15)
            for kw in proj["platform_keywords"]:
                if kw in job_text:
                    score += 0.15
                    break

            # 기능 매칭 — 멀티플레이 등 (0.15)
            for kw in proj["feature_keywords"]:
                if kw in job_text:
                    score += 0.15
                    hits.append(kw)
                    break

            score = min(score, 1.0)
            if score > best_score:
                best_score = score
                best_reasons = (
                    [f"🗂️ 프로젝트 경험: {proj['name']} ({', '.join(hits)})"]
                    if hits else []
                )

        return best_score, best_reasons

    def _compare_requirements(
        self, job_text: str, user_skills: list[str]
    ) -> list[str]:
        """담당업무/자격요건/우대사항 키워드와 이력서 비교"""
        job_techs = [kw for kw in _TECH_KEYWORDS if kw in job_text]
        if not job_techs:
            return []

        has   = [t for t in job_techs if t in user_skills]
        lacks = [t for t in job_techs if t not in user_skills]

        out: list[str] = []
        if has:
            out.append(f"✅ 요건 보유 기술: {', '.join(has[:6])}")
        if lacks:
            out.append(f"📌 요건 미보유 기술: {', '.join(lacks[:4])}")
        return out

    def _match_experience(self, resume_exp: str, job_exp: str) -> float:
        """경력 조건 매칭 점수"""
        # 사용자 실제 경력: resume_data에서 파싱 안 되면 3년으로 고정
        _USER_YEARS = 3

        if not job_exp:
            return 0.7  # 정보 없으면 중립보다 약간 낮게

        if "무관" in job_exp:
            return 1.0

        if "신입" in job_exp:
            # 신입 공고는 경력자도 지원 가능하므로 허용
            return 0.8

        job_years = re.findall(r"(\d+)", job_exp)
        if not job_years:
            return 0.7

        r_years = re.findall(r"(\d+)", resume_exp)
        r = int(r_years[0]) if r_years else _USER_YEARS
        j = int(job_years[0])

        if r >= j:
            return 1.0
        elif r >= j - 1:
            return 0.6
        elif r >= j - 2:
            return 0.3
        else:
            # 경력 2년 이상 초과 요구 → 사실상 불가 → 0점 (필터링됨)
            return 0.0
