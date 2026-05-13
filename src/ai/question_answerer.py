import json
from loguru import logger
from src.ai.llm_provider import LLMProvider


class QuestionAnswerer:
    """Answers screening questions found in job application forms."""

    def __init__(self, provider: LLMProvider, profile: dict):
        self.provider = provider
        self.profile = profile

    def answer(self, question: str, options: list[str] | None = None) -> str:
        options_text = ""
        if options:
            options_text = f"\nAvailable options: {json.dumps(options)}"
            options_text += "\nReturn EXACTLY one of the options above (identical text)."

        prompt = f"""You are the candidate below answering a job application screening question.

## CANDIDATE PROFILE
{json.dumps(self.profile, ensure_ascii=False, indent=2)}

## QUESTION
{question}{options_text}

## INSTRUCTIONS
Return ONLY the answer, no explanations, no extra punctuation.
If it is a multiple-choice question, return exactly one of the options.
If it is free text, be concise (maximum 2 sentences).
"""
        try:
            return self.provider.complete(prompt, max_tokens=200)
        except Exception as e:
            logger.error(f"Failed to answer question '{question}': {e}")
            return options[0] if options else "Yes"
