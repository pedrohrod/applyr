import pytest
from src.ai.question_answerer import QuestionAnswerer


def test_answer_free_text(mock_provider, sample_profile):
    mock_provider.complete.return_value = "3 years"
    qa = QuestionAnswerer(mock_provider, sample_profile)
    result = qa.answer("How many years of experience do you have?")
    assert result == "3 years"


def test_answer_multiple_choice_returns_option(mock_provider, sample_profile):
    mock_provider.complete.return_value = "Yes"
    qa = QuestionAnswerer(mock_provider, sample_profile)
    result = qa.answer("Are you authorized to work?", options=["Yes", "No"])
    assert result == "Yes"


def test_answer_fallback_on_error(mock_provider, sample_profile):
    mock_provider.complete.side_effect = Exception("API down")
    qa = QuestionAnswerer(mock_provider, sample_profile)
    result = qa.answer("Are you available?", options=["Yes", "No"])
    assert result == "Yes"  # falls back to first option


def test_answer_fallback_no_options_on_error(mock_provider, sample_profile):
    mock_provider.complete.side_effect = Exception("API down")
    qa = QuestionAnswerer(mock_provider, sample_profile)
    result = qa.answer("Describe yourself")
    assert result == "Yes"  # default fallback


def test_options_included_in_prompt(mock_provider, sample_profile):
    mock_provider.complete.return_value = "Remote"
    qa = QuestionAnswerer(mock_provider, sample_profile)
    qa.answer("Work preference?", options=["Remote", "Onsite", "Hybrid"])
    prompt = mock_provider.complete.call_args[0][0]
    assert "Remote" in prompt
    assert "Onsite" in prompt
