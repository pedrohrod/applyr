import pytest
from src.ai.cover_letter import CoverLetterGenerator


def test_generate_returns_string(mock_provider, sample_profile):
    mock_provider.complete.return_value = "Dear hiring manager, I am excited to apply..."
    gen = CoverLetterGenerator(mock_provider)
    result = gen.generate("resume text", {"title": "SWE", "company": "Stripe", "description": "..."}, sample_profile)
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_returns_empty_on_error(mock_provider, sample_profile):
    mock_provider.complete.side_effect = Exception("API error")
    gen = CoverLetterGenerator(mock_provider)
    result = gen.generate("resume text", {"title": "SWE", "company": "Stripe", "description": ""}, sample_profile)
    assert result == ""


def test_detects_english_job(mock_provider, sample_profile):
    mock_provider.complete.return_value = "cover letter"
    gen = CoverLetterGenerator(mock_provider)
    job = {"title": "Software Engineer", "description": "backend developer experience required", "company": "X"}
    gen.generate("resume", job, sample_profile)
    prompt = mock_provider.complete.call_args[0][0]
    assert "English" in prompt


def test_detects_portuguese_job(mock_provider, sample_profile):
    mock_provider.complete.return_value = "carta"
    gen = CoverLetterGenerator(mock_provider)
    job = {"title": "Desenvolvedor Backend", "description": "empresa brasileira requisitos experiência vaga", "company": "X"}
    gen.generate("resume", job, sample_profile)
    prompt = mock_provider.complete.call_args[0][0]
    assert "português" in prompt


def test_salary_included_when_present(mock_provider, sample_profile):
    mock_provider.complete.return_value = "cover letter"
    gen = CoverLetterGenerator(mock_provider)
    gen.generate("resume", {"title": "Dev", "company": "Co", "description": ""}, sample_profile)
    prompt = mock_provider.complete.call_args[0][0]
    assert "80,000" in prompt


def test_no_salary_line_when_empty(mock_provider, sample_profile):
    mock_provider.complete.return_value = "cover letter"
    profile = {**sample_profile, "salary_expectations": {"range": ""}}
    gen = CoverLetterGenerator(mock_provider)
    gen.generate("resume", {"title": "Dev", "company": "Co", "description": ""}, profile)
    prompt = mock_provider.complete.call_args[0][0]
    assert "Salary expectation" not in prompt
