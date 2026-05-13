import pytest
import os
from unittest.mock import patch
from src.config_validator import validate


BASE_SETTINGS = {
    "job_search": {
        "keywords": ["Software Engineer"],
        "date_posted": "month",
        "distance": 0,
    },
    "matching": {"threshold": 70},
    "platforms": {
        "linkedin": {"enabled": True, "daily_limit": 40},
        "gupy": {"enabled": False, "daily_limit": 30},
    },
    "tracking": {},
    "application": {},
}

VALID_ENV = {
    "LLM_PROVIDER": "anthropic",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "LINKEDIN_EMAIL": "test@example.com",
    "LINKEDIN_PASSWORD": "password",
}


def run_validate(settings=None, env=None, resume_exists=True):
    s = settings or BASE_SETTINGS
    e = env or VALID_ENV
    resume = "resume/resume.pdf"
    with patch.dict(os.environ, e, clear=False):
        with patch("src.config_validator.Path") as mock_path:
            mock_path.return_value.exists.return_value = resume_exists
            validate(s, resume)


def test_valid_config_passes():
    run_validate()  # should not raise


def test_missing_api_key_exits(tmp_path):
    env = {**VALID_ENV, "ANTHROPIC_API_KEY": ""}
    with pytest.raises(SystemExit):
        run_validate(env=env)


def test_invalid_provider_exits():
    env = {**VALID_ENV, "LLM_PROVIDER": "nonexistent"}
    with pytest.raises(SystemExit):
        run_validate(env=env)


def test_missing_resume_exits():
    with pytest.raises(SystemExit):
        run_validate(resume_exists=False)


def test_threshold_out_of_range_exits():
    settings = {**BASE_SETTINGS, "matching": {"threshold": 150}}
    with pytest.raises(SystemExit):
        run_validate(settings=settings)


def test_threshold_zero_is_valid():
    settings = {**BASE_SETTINGS, "matching": {"threshold": 0}}
    run_validate(settings=settings)


def test_invalid_date_posted_exits():
    settings = {
        **BASE_SETTINGS,
        "job_search": {**BASE_SETTINGS["job_search"], "date_posted": "yesterday"},
    }
    with pytest.raises(SystemExit):
        run_validate(settings=settings)


def test_invalid_distance_exits():
    settings = {
        **BASE_SETTINGS,
        "job_search": {**BASE_SETTINGS["job_search"], "distance": 7},
    }
    with pytest.raises(SystemExit):
        run_validate(settings=settings)


def test_missing_linkedin_creds_when_enabled_exits():
    env = {**VALID_ENV, "LINKEDIN_EMAIL": "", "LINKEDIN_PASSWORD": ""}
    with pytest.raises(SystemExit):
        run_validate(env=env)


def test_empty_keywords_exits():
    settings = {
        **BASE_SETTINGS,
        "job_search": {**BASE_SETTINGS["job_search"], "keywords": []},
    }
    with pytest.raises(SystemExit):
        run_validate(settings=settings)


def test_openai_provider_requires_openai_key():
    env = {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "", "LINKEDIN_EMAIL": "a", "LINKEDIN_PASSWORD": "b"}
    with pytest.raises(SystemExit):
        run_validate(env=env)


def test_ollama_provider_requires_api_url():
    env = {"LLM_PROVIDER": "ollama", "LLM_API_URL": "", "LINKEDIN_EMAIL": "a", "LINKEDIN_PASSWORD": "b"}
    with pytest.raises(SystemExit):
        run_validate(env=env)
