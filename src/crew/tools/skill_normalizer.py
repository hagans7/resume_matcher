"""SkillNormalizerTool — Custom CrewAI BaseTool for skill alias resolution.

Used by Skill Matcher agent to normalize skill names before comparison.
HashMap lookup O(1) per skill. Deduplication via set O(n).

Usage by agent: tool input is comma-separated skill string.
Returns normalized comma-separated string.
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


SKILL_ALIASES: dict[str, str] = {
    # JavaScript ecosystem
    "js": "javascript",
    "ts": "typescript",
    "node": "nodejs",
    "node.js": "nodejs",
    "react.js": "react",
    "vue.js": "vue",
    "next.js": "nextjs",
    "nuxt.js": "nuxtjs",
    # Python
    "py": "python",
    # Databases
    "pg": "postgresql",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "mssql": "sql server",
    "mysql": "mysql",
    "redis": "redis",
    # Cloud / DevOps
    "k8s": "kubernetes",
    "tf": "terraform",
    "aws": "aws",
    "gcp": "google cloud",
    "az": "azure",
    # ML / Data
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "sk": "scikit-learn",
    "sklearn": "scikit-learn",
    "tf2": "tensorflow",
    "pt": "pytorch",
    # CI/CD
    "gh actions": "github actions",
    "ci": "ci/cd",
    "cd": "ci/cd",
    # General
    "oop": "object oriented programming",
    "rest": "rest api",
    "graphql": "graphql",
    "sql": "sql",
    "nosql": "nosql",
    "git": "git",
    "docker": "docker",
    "linux": "linux",
}


class SkillNormalizerInput(BaseModel):
    skills: str = Field(description="Comma-separated list of skills to normalize")


class SkillNormalizerTool(BaseTool):
    name: str = "skill_normalizer"
    description: str = (
        "Normalize a comma-separated list of skill names to their canonical form. "
        "Resolves aliases like JS→JavaScript, k8s→Kubernetes, py→Python. "
        "Input: comma-separated skills string. Output: normalized comma-separated string."
    )
    args_schema: type[BaseModel] = SkillNormalizerInput

    def _run(self, skills: str) -> str:
        """Normalize skill list. O(n) where n = number of skills."""
        raw_skills = [s.strip().lower() for s in skills.split(",") if s.strip()]
        normalized = {SKILL_ALIASES.get(skill, skill) for skill in raw_skills}
        result = ", ".join(sorted(normalized))
        return result
