from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.applicator.portal_router import PortalRouter, _decode_linkedin_redirect
from src.scrapers.linkedin import Job


def make_router():
    browser = MagicMock()
    qa = MagicMock()
    return PortalRouter(browser, "resume/resume.pdf", qa)


def make_job(apply_url: str = "", easy_apply: bool = False) -> Job:
    return Job(
        id="test_1",
        title="Software Engineer",
        company="Acme",
        location="Remote",
        url="https://www.linkedin.com/jobs/view/12345",
        easy_apply=easy_apply,
        extra={"apply_url": apply_url},
    )


# ---------------------------------------------------------------------------
# URL detection
# ---------------------------------------------------------------------------

def test_detect_greenhouse():
    r = make_router()
    assert r.detect("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"


def test_detect_grnh_shortlink():
    r = make_router()
    assert r.detect("https://grnh.se/abc123") == "greenhouse"


def test_detect_lever():
    r = make_router()
    assert r.detect("https://jobs.lever.co/acme/abc-def") == "lever"


def test_detect_workday():
    r = make_router()
    assert r.detect("https://acme.myworkdayjobs.com/jobs/listing/123") == "workday"


def test_detect_unknown_returns_none():
    r = make_router()
    assert r.detect("https://careers.example.com/apply?id=1") is None


def test_detect_is_case_insensitive():
    r = make_router()
    assert r.detect("https://BOARDS.GREENHOUSE.IO/acme/jobs/1") == "greenhouse"


# ---------------------------------------------------------------------------
# LinkedIn redirect decoder
# ---------------------------------------------------------------------------

def test_decode_linkedin_redirect_extracts_url():
    href = "https://www.linkedin.com/jobs/view/externalApply/123?url=https%3A%2F%2Fboards.greenhouse.io%2Facme%2Fjobs%2F456"
    assert _decode_linkedin_redirect(href) == "https://boards.greenhouse.io/acme/jobs/456"


def test_decode_linkedin_redirect_returns_href_unchanged_when_no_param():
    href = "https://boards.greenhouse.io/acme/jobs/456"
    assert _decode_linkedin_redirect(href) == href


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_routes_to_greenhouse():
    r = make_router()
    r.greenhouse.apply = AsyncMock(return_value=True)
    job = make_job("https://boards.greenhouse.io/acme/jobs/1")
    result = await r.apply(job, "cover letter")
    r.greenhouse.apply.assert_awaited_once()
    assert result is True


@pytest.mark.asyncio
async def test_apply_routes_to_lever():
    r = make_router()
    r.lever.apply = AsyncMock(return_value=True)
    job = make_job("https://jobs.lever.co/acme/abc")
    result = await r.apply(job, "cover letter")
    r.lever.apply.assert_awaited_once()
    assert result is True


@pytest.mark.asyncio
async def test_apply_returns_false_for_workday():
    r = make_router()
    job = make_job("https://acme.myworkdayjobs.com/jobs/123")
    result = await r.apply(job)
    assert result is False


@pytest.mark.asyncio
async def test_apply_returns_false_for_unsupported_portal():
    r = make_router()
    job = make_job("https://careers.example.com/apply")
    result = await r.apply(job)
    assert result is False


@pytest.mark.asyncio
async def test_apply_returns_false_when_no_url_and_resolve_fails():
    r = make_router()
    r._resolve_external_url = AsyncMock(return_value="")
    job = make_job("")
    result = await r.apply(job)
    assert result is False


@pytest.mark.asyncio
async def test_apply_resolves_url_when_linkedin_url_stored():
    r = make_router()
    r._resolve_external_url = AsyncMock(return_value="https://boards.greenhouse.io/acme/jobs/1")
    r.greenhouse.apply = AsyncMock(return_value=True)
    job = make_job("https://www.linkedin.com/jobs/view/12345")
    result = await r.apply(job)
    r._resolve_external_url.assert_awaited_once()
    assert result is True
