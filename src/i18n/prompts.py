from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PromptLocale:
    code: str
    name: str
    cover_letter_instruction: str
    score_instruction: str
    answer_instruction: str


LOCALES: dict[str, PromptLocale] = {
    "en": PromptLocale(
        code="en",
        name="English",
        cover_letter_instruction="Write the cover letter in English.",
        score_instruction="Return the JSON with keys and values in English.",
        answer_instruction="Answer in English. Be concise (max 2 sentences).",
    ),
    "pt": PromptLocale(
        code="pt",
        name="Portuguese",
        cover_letter_instruction="Escreva a carta de apresentação em português.",
        score_instruction="Retorne o JSON com chaves e valores em português.",
        answer_instruction="Responda em português. Seja conciso (máximo 2 frases).",
    ),
    "es": PromptLocale(
        code="es",
        name="Spanish",
        cover_letter_instruction="Escribe la carta de presentación en español.",
        score_instruction="Devuelve el JSON con claves y valores en español.",
        answer_instruction="Responde en español. Sé conciso (máximo 2 frases).",
    ),
    "de": PromptLocale(
        code="de",
        name="German",
        cover_letter_instruction="Schreibe das Anschreiben auf Deutsch.",
        score_instruction="Gib das JSON mit Schlüsseln und Werten auf Englisch zurück.",
        answer_instruction="Antworte auf Deutsch. Sei präzise (maximal 2 Sätze).",
    ),
    "fr": PromptLocale(
        code="fr",
        name="French",
        cover_letter_instruction="Rédigez la lettre de motivation en français.",
        score_instruction="Retournez le JSON avec les clés et valeurs en anglais.",
        answer_instruction="Répondez en français. Soyez concis (2 phrases maximum).",
    ),
}

_LANG_WORDS: dict[str, list[str]] = {
    "pt": ["desenvolvedor", "engenheiro", "empresa", "vaga", "requisitos", "experiência", "cargo"],
    "es": ["desarrollador", "ingeniero", "empresa", "vacante", "requisitos", "experiencia", "cargo"],
    "de": ["entwickler", "ingenieur", "unternehmen", "stelle", "anforderungen", "erfahrung"],
    "fr": ["développeur", "ingénieur", "entreprise", "poste", "exigences", "expérience"],
    "en": ["engineer", "developer", "software", "backend", "frontend", "experience", "required"],
}


def get_locale(lang_setting: str, job_text: str = "") -> PromptLocale:
    if lang_setting != "auto":
        return LOCALES.get(lang_setting.lower(), LOCALES["en"])

    if not job_text:
        return LOCALES["en"]

    text = job_text.lower()
    scores = {lang: sum(1 for w in words if w in text) for lang, words in _LANG_WORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return LOCALES["en"]
    return LOCALES.get(best, LOCALES["en"])
