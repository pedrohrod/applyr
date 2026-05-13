import json
from loguru import logger
from src.ai.llm_provider import LLMProvider


class QuestionAnswerer:
    """Responde perguntas de triagem de formulários de candidatura."""

    def __init__(self, provider: LLMProvider, profile: dict):
        self.provider = provider
        self.profile = profile

    def answer(self, question: str, options: list[str] | None = None) -> str:
        options_text = ""
        if options:
            options_text = f"\nOpções disponíveis: {json.dumps(options, ensure_ascii=False)}"
            options_text += "\nRetorne EXATAMENTE uma das opções acima (texto idêntico)."

        prompt = f"""Você é o candidato abaixo respondendo uma pergunta de triagem de emprego.

## PERFIL DO CANDIDATO
{json.dumps(self.profile, ensure_ascii=False, indent=2)}

## PERGUNTA
{question}{options_text}

## INSTRUÇÃO
Retorne APENAS a resposta, sem explicações, sem pontuação extra.
Se for pergunta de múltipla escolha, retorne exatamente uma das opções.
Se for texto livre, seja conciso (máximo 2 frases).
"""
        try:
            return self.provider.complete(prompt, max_tokens=200)
        except Exception as e:
            logger.error(f"Erro ao responder pergunta '{question}': {e}")
            return options[0] if options else "Sim"
