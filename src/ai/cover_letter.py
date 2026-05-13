from loguru import logger
from src.ai.llm_provider import LLMProvider


class CoverLetterGenerator:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def generate(self, resume_text: str, job: dict, profile: dict) -> str:
        name = profile.get("personal", {}).get("name", "Candidato")
        salary = profile.get("salary_expectations", {}).get("range", "")
        salary_line = f"Pretensão salarial: {salary}" if salary else ""

        prompt = f"""Você é um especialista em carreira. Escreva uma carta de apresentação profissional e personalizada.

## SOBRE O CANDIDATO
Nome: {name}
{salary_line}
{resume_text[:2000]}

## VAGA
Título: {job.get('title', '')}
Empresa: {job.get('company', '')}
Descrição: {job.get('description', '')[:1500]}

## REGRAS
- Máximo 3 parágrafos curtos
- Tom profissional mas humano, não genérico
- Mencione especificamente a empresa e o cargo
- Destaque 2-3 habilidades do currículo que se encaixam na vaga
- Escreva em {self._detect_language(job)}
- Não inclua cabeçalho nem assinatura formal, apenas o corpo da carta
"""
        try:
            return self.provider.complete(prompt, max_tokens=600)
        except Exception as e:
            logger.error(f"Erro ao gerar cover letter: {e}")
            return ""

    def _detect_language(self, job: dict) -> str:
        text = f"{job.get('title', '')} {job.get('description', '')}".lower()
        english_words = ["engineer", "developer", "software", "backend", "frontend", "experience"]
        en_count = sum(1 for w in english_words if w in text)
        return "inglês" if en_count >= 3 else "português"
