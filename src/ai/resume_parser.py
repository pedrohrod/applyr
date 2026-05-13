import pdfplumber
from pathlib import Path
from loguru import logger


def parse_resume(path: str) -> str:
    file = Path(path)
    if not file.exists():
        raise FileNotFoundError(f"Currículo não encontrado: {path}")

    suffix = file.suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(file)
    elif suffix in (".txt", ".md"):
        return file.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Formato não suportado: {suffix}. Use PDF ou TXT.")


def _parse_pdf(path: Path) -> str:
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    full_text = "\n".join(text_parts)
    logger.debug(f"Currículo extraído: {len(full_text)} caracteres de {len(text_parts)} página(s)")
    return full_text
