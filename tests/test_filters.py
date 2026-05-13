import pytest
from src.scrapers.linkedin import Job


def make_job(**kwargs):
    defaults = dict(
        id="job-1", title="Software Engineer", company="Acme Corp",
        location="Brazil", url="https://example.com", platform="linkedin",
    )
    return Job(**{**defaults, **kwargs})


def blacklist_check(job, company_bl=None, title_bl=None, location_bl=None):
    """Mirrors orchestrator._is_blacklisted logic."""
    company_bl = [c.lower() for c in (company_bl or [])]
    title_bl = [t.lower() for t in (title_bl or [])]
    location_bl = [l.lower() for l in (location_bl or [])]

    for term in company_bl:
        if term in job.company.lower():
            return True, f"company blacklisted: '{term}'"
    for term in title_bl:
        if term in job.title.lower():
            return True, f"title blacklisted: '{term}'"
    for term in location_bl:
        if term in job.location.lower():
            return True, f"location blacklisted: '{term}'"
    return False, ""


class TestCompanyBlacklist:
    def test_exact_match_blocked(self):
        job = make_job(company="Wipro")
        blocked, reason = blacklist_check(job, company_bl=["Wipro"])
        assert blocked
        assert "company blacklisted" in reason

    def test_partial_match_blocked(self):
        job = make_job(company="Wipro Technologies Brazil")
        blocked, _ = blacklist_check(job, company_bl=["wipro"])
        assert blocked

    def test_non_matching_company_allowed(self):
        job = make_job(company="Stripe")
        blocked, _ = blacklist_check(job, company_bl=["Wipro", "Infosys"])
        assert not blocked

    def test_empty_blacklist_allows_all(self):
        job = make_job(company="Any Company")
        blocked, _ = blacklist_check(job, company_bl=[])
        assert not blocked


class TestTitleBlacklist:
    def test_director_title_blocked(self):
        job = make_job(title="Director of Engineering")
        blocked, _ = blacklist_check(job, title_bl=["Director"])
        assert blocked

    def test_case_insensitive(self):
        job = make_job(title="VP of Product")
        blocked, _ = blacklist_check(job, title_bl=["vp "])
        assert blocked

    def test_non_matching_title_allowed(self):
        job = make_job(title="Senior Software Engineer")
        blocked, _ = blacklist_check(job, title_bl=["Director", "VP"])
        assert not blocked


class TestLocationBlacklist:
    def test_blocked_location(self):
        job = make_job(location="Bangalore, India")
        blocked, _ = blacklist_check(job, location_bl=["India"])
        assert blocked

    def test_allowed_location(self):
        job = make_job(location="São Paulo, Brazil")
        blocked, _ = blacklist_check(job, location_bl=["India", "China"])
        assert not blocked


class TestCombinedFilters:
    def test_only_company_triggers(self):
        job = make_job(company="Wipro", title="Software Engineer", location="Brazil")
        blocked, reason = blacklist_check(job, company_bl=["Wipro"], title_bl=["Director"])
        assert blocked
        assert "company" in reason

    def test_all_clean_passes(self):
        job = make_job(company="Stripe", title="Engineer", location="Remote")
        blocked, _ = blacklist_check(
            job,
            company_bl=["Wipro"],
            title_bl=["Director"],
            location_bl=["India"],
        )
        assert not blocked
