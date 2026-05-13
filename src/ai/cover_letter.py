from __future__ import annotations
from loguru import logger
from src.ai.llm_provider import LLMProvider
from src.i18n.prompts import PromptLocale, get_locale


class CoverLetterGenerator:
    def __init__(self, provider: LLMProvider, locale: PromptLocale | None = None):
        self.provider = provider
        self.locale = locale  # None = auto-detect per job

    def generate(self, resume_text: str, job: dict, profile: dict) -> str:
        name = profile.get("personal", {}).get("name", "Candidate")
        salary = profile.get("salary_expectations", {}).get("range", "")
        salary_line = f"Salary expectation: {salary}" if salary else ""

        locale = self.locale or get_locale("auto", f"{job.get('title','')} {job.get('description','')}")

        prompt = f"""You are a career expert. Write a professional and personalized cover letter.

## ABOUT THE CANDIDATE
Name: {name}
{salary_line}
{resume_text[:2000]}

## JOB POSTING
Title: {job.get('title', '')}
Company: {job.get('company', '')}
Description: {job.get('description', '')[:1500]}

## RULES
- Maximum 3 short paragraphs
- Professional but human tone, not generic
- Mention the company and role specifically
- Highlight 2-3 skills from the resume that match the job
- {locale.cover_letter_instruction}
- No header or formal closing, just the body of the letter
"""
        try:
            return self.provider.complete(prompt, max_tokens=600)
        except Exception as e:
            logger.error(f"Failed to generate cover letter: {e}")
            return ""
