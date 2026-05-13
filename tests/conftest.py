import pytest
from unittest.mock import MagicMock
from src.scrapers.linkedin import Job


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.complete.return_value = '{"score": 85, "strong_matches": ["Python"], "missing_skills": [], "recommendation": "Good fit"}'
    return provider


@pytest.fixture
def sample_job():
    return Job(
        id="job-123",
        title="Backend Developer",
        company="Acme Corp",
        location="Brazil",
        url="https://linkedin.com/jobs/123",
        description="We need a Python backend developer with 3+ years experience.",
        requirements="Python, FastAPI, PostgreSQL",
        platform="linkedin",
    )


@pytest.fixture
def sample_profile():
    return {
        "personal": {"name": "John Doe", "email": "john@example.com"},
        "professional": {"current_role": "Software Developer", "experience_years": 3},
        "skills": {"technical": ["Python", "FastAPI", "PostgreSQL"]},
        "salary_expectations": {"range": "USD 80,000 - 100,000"},
        "availability": {"notice_period": "Immediately"},
        "work_preferences": {"remote_work": "Yes", "open_to_relocation": "No"},
        "legal_authorization": {"us_work_authorization": "No"},
    }
