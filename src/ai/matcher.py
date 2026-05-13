from __future__ import annotations
import json
from dataclasses import dataclass, field
from loguru import logger
from src.ai.llm_provider import LLMProvider
from src.i18n.prompts import PromptLocale, LOCALES


@dataclass
class MatchResult:
    score: int
    strong_matches: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    recommendation: str = ""


class JobMatcher:
    def __init__(self, provider: LLMProvider, locale: PromptLocale | None = None):
        self.provider = provider
        self.locale = locale or LOCALES["en"]

    def score(self, resume_text: str, job: dict) -> MatchResult:
        prompt = f"""You are an expert tech recruiter. Analyze the match between the resume and the job posting below.

## RESUME
{resume_text}

## JOB POSTING
Title: {job.get('title', '')}
Company: {job.get('company', '')}
Description: {job.get('description', '')}
Requirements: {job.get('requirements', '')}

## INSTRUCTIONS
Return ONLY a valid JSON with this exact structure:
{{
  "score": <integer from 0 to 100>,
  "strong_matches": ["skills or experience that align with the job"],
  "missing_skills": ["skills missing from the resume"],
  "recommendation": "short sentence explaining the score"
}}

Score criteria:
- 90-100: Perfect fit, ideal candidate
- 70-89: Good fit, worth applying
- 50-69: Partial fit, could try
- 0-49: Weak fit, not recommended

{self.locale.score_instruction}
"""
        try:
            raw = self.provider.complete(prompt, max_tokens=512)
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            return MatchResult(
                score=int(data.get("score", 0)),
                strong_matches=data.get("strong_matches", []),
                missing_skills=data.get("missing_skills", []),
                recommendation=data.get("recommendation", ""),
            )
        except Exception as e:
            logger.error(f"Failed to compute match score: {e}")
            return MatchResult(score=0, recommendation=f"Error: {e}")
