import json
from dataclasses import dataclass, field
from loguru import logger
from src.ai.llm_provider import LLMProvider


@dataclass
class MatchResult:
    score: int
    strong_matches: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    recommendation: str = ""


class JobMatcher:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def score(self, resume_text: str, job: dict) -> MatchResult:
        prompt = f"""Você é um especialista em recrutamento tech. Analise o match entre o currículo e a vaga abaixo.

## CURRÍCULO
{resume_text}

## VAGA
Título: {job.get('title', '')}
Empresa: {job.get('company', '')}
Descrição: {job.get('description', '')}
Requisitos: {job.get('requirements', '')}

## INSTRUÇÃO
Retorne APENAS um JSON válido com esta estrutura:
{{
  "score": <inteiro de 0 a 100>,
  "strong_matches": ["habilidade ou experiência que bate com a vaga"],
  "missing_skills": ["o que está faltando no currículo"],
  "recommendation": "frase curta explicando o score"
}}

Critérios de score:
- 90-100: Encaixe perfeito, candidato ideal
- 70-89: Bom encaixe, vale aplicar
- 50-69: Encaixe parcial, pode tentar
- 0-49: Encaixe fraco, não recomendado
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
            logger.error(f"Erro ao calcular match: {e}")
            return MatchResult(score=0, recommendation=f"Erro: {e}")
