import pdfplumber
from docx import Document as DocxDocument
from pathlib import Path
import re


class ResumeParser:
    """이력서/경력기술서를 로우데이터로 변환"""

    TECH_KEYWORDS = {
        "languages": [
            "C++", "C#", "Python", "Java", "JavaScript", "TypeScript",
            "Lua", "Go", "Rust", "Kotlin", "Swift",
        ],
        "engines": [
            "Unity", "Unreal Engine", "UE4", "UE5", "Godot", "Cocos2d",
            "CryEngine", "자체엔진",
        ],
        "graphics": [
            "DirectX", "OpenGL", "Vulkan", "Metal", "셰이더", "HLSL",
            "GLSL", "렌더링", "그래픽스",
        ],
        "server": [
            "서버", "네트워크", "소켓", "TCP", "UDP", "gRPC",
            "Redis", "MySQL", "MongoDB", "PostgreSQL", "AWS", "GCP",
        ],
        "tools": [
            "Git", "SVN", "Perforce", "Jenkins", "Docker",
            "Jira", "Confluence",
        ],
        "domains": [
            "MMORPG", "FPS", "RPG", "액션", "퍼즐", "모바일",
            "PC", "콘솔", "PS5", "Xbox", "VR", "AR",
        ],
    }

    def parse(self, file_path: str) -> dict:
        """파일에서 텍스트를 추출하고 구조화된 데이터로 변환"""
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            text = self._extract_from_pdf(file_path)
        elif path.suffix.lower() in (".docx", ".doc"):
            text = self._extract_from_docx(file_path)
        elif path.suffix.lower() == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {path.suffix}")

        return self._structure_data(text)

    def _extract_from_pdf(self, file_path: str) -> str:
        """PDF에서 텍스트 추출"""
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for pg in pdf.pages:
                page_text = pg.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    def _extract_from_docx(self, file_path: str) -> str:
        """DOCX에서 텍스트 추출"""
        doc = DocxDocument(file_path)
        return "\n".join(para.text for para in doc.paragraphs if para.text.strip())

    def _structure_data(self, text: str) -> dict:
        """텍스트를 구조화된 로우데이터로 변환"""
        data = {
            "원본텍스트": text[:5000],
            "기술스택_언어": [],
            "기술스택_엔진": [],
            "기술스택_그래픽스": [],
            "기술스택_서버": [],
            "기술스택_도구": [],
            "기술스택_도메인": [],
            "총경력년수": "",
            "학력": "",
            "프로젝트목록": [],
        }

        text_lower = text.lower()

        for category, keywords in self.TECH_KEYWORDS.items():
            found = []
            for kw in keywords:
                if kw.lower() in text_lower:
                    found.append(kw)
            category_key = {
                "languages": "기술스택_언어",
                "engines": "기술스택_엔진",
                "graphics": "기술스택_그래픽스",
                "server": "기술스택_서버",
                "tools": "기술스택_도구",
                "domains": "기술스택_도메인",
            }[category]
            data[category_key] = found

        exp_patterns = [
            r"(\d+)\s*년\s*(\d+)?\s*개월?",
            r"경력\s*[:：]?\s*(\d+)",
            r"총\s*경력\s*[:：]?\s*(\d+)",
        ]
        for pattern in exp_patterns:
            match = re.search(pattern, text)
            if match:
                data["총경력년수"] = match.group(0)
                break

        edu_keywords = ["박사", "석사", "학사", "대졸", "전문대", "고졸"]
        for edu in edu_keywords:
            if edu in text:
                data["학력"] = edu
                break

        project_patterns = [
            r"프로젝트\s*[:：]\s*(.+)",
            r"(?:참여|개발)\s*(?:프로젝트|게임)\s*[:：]?\s*(.+)",
        ]
        for pattern in project_patterns:
            matches = re.findall(pattern, text)
            data["프로젝트목록"].extend(
                m.strip() for m in matches if m.strip()
            )

        return data

    def get_all_skills_flat(self, resume_data: dict) -> list[str]:
        """모든 기술 키워드를 하나의 리스트로"""
        skills = []
        for key in resume_data:
            if key.startswith("기술스택_"):
                value = resume_data[key]
                if isinstance(value, list):
                    skills.extend(value)
                elif isinstance(value, str) and value:
                    skills.extend(value.split(", "))
        return skills
