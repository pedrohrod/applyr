from __future__ import annotations
import pytest
from src.i18n.prompts import get_locale, LOCALES


def test_all_locales_have_required_fields():
    for code, locale in LOCALES.items():
        assert locale.code == code
        assert locale.name
        assert locale.cover_letter_instruction
        assert locale.score_instruction
        assert locale.answer_instruction


def test_get_locale_explicit_en():
    locale = get_locale("en")
    assert locale.code == "en"


def test_get_locale_explicit_pt():
    locale = get_locale("pt")
    assert locale.code == "pt"


def test_get_locale_explicit_es():
    locale = get_locale("es")
    assert locale.code == "es"


def test_get_locale_case_insensitive():
    assert get_locale("PT").code == "pt"
    assert get_locale("EN").code == "en"


def test_get_locale_unknown_falls_back_to_en():
    locale = get_locale("zz")
    assert locale.code == "en"


def test_get_locale_auto_pt_detected():
    job_text = "Desenvolvedor Python Sênior. Requisitos: experiência em Python e SQL. " * 10
    locale = get_locale("auto", job_text)
    assert locale.code == "pt"


def test_get_locale_auto_en_detected():
    job_text = "Senior Software Engineer. Requirements: strong Python and SQL skills. " * 10
    locale = get_locale("auto", job_text)
    assert locale.code == "en"


def test_get_locale_auto_es_detected():
    job_text = "Ingeniero de Software Senior. Requisitos: experiencia en Python y SQL. " * 10
    locale = get_locale("auto", job_text)
    assert locale.code == "es"


def test_get_locale_auto_empty_text_defaults_to_en():
    locale = get_locale("auto", "")
    assert locale.code == "en"
