import pytest
from src.ai.matcher import JobMatcher, MatchResult


def test_score_returns_match_result(mock_provider, sample_job):
    mock_provider.complete.return_value = (
        '{"score": 85, "strong_matches": ["Python", "FastAPI"], '
        '"missing_skills": ["Go"], "recommendation": "Good fit"}'
    )
    matcher = JobMatcher(mock_provider)
    result = matcher.score("resume text", {
        "title": sample_job.title,
        "company": sample_job.company,
        "description": sample_job.description,
        "requirements": sample_job.requirements,
    })
    assert isinstance(result, MatchResult)
    assert result.score == 85
    assert "Python" in result.strong_matches
    assert "Go" in result.missing_skills
    assert result.recommendation == "Good fit"


def test_score_handles_markdown_json(mock_provider):
    mock_provider.complete.return_value = (
        "```json\n"
        '{"score": 72, "strong_matches": [], "missing_skills": [], "recommendation": "ok"}\n'
        "```"
    )
    matcher = JobMatcher(mock_provider)
    result = matcher.score("resume", {"title": "Dev", "company": "Co", "description": "", "requirements": ""})
    assert result.score == 72


def test_score_returns_zero_on_invalid_json(mock_provider):
    mock_provider.complete.return_value = "this is not json"
    matcher = JobMatcher(mock_provider)
    result = matcher.score("resume", {"title": "Dev", "company": "Co", "description": "", "requirements": ""})
    assert result.score == 0


def test_score_returns_zero_on_provider_error(mock_provider):
    mock_provider.complete.side_effect = Exception("API error")
    matcher = JobMatcher(mock_provider)
    result = matcher.score("resume", {"title": "Dev", "company": "Co", "description": "", "requirements": ""})
    assert result.score == 0
    assert "Error" in result.recommendation


def test_score_clamps_to_valid_range(mock_provider):
    mock_provider.complete.return_value = (
        '{"score": 95, "strong_matches": [], "missing_skills": [], "recommendation": "perfect"}'
    )
    matcher = JobMatcher(mock_provider)
    result = matcher.score("resume", {"title": "Dev", "company": "Co", "description": "", "requirements": ""})
    assert 0 <= result.score <= 100
