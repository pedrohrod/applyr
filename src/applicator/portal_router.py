from __future__ import annotations
import asyncio
import random
import urllib.parse
from loguru import logger

from src.browser import SharedBrowser
from src.scrapers.linkedin import Job
from src.ai.question_answerer import QuestionAnswerer
from src.applicator.greenhouse import GreenhouseApplicator
from src.applicator.lever import LeverApplicator

PORTAL_PATTERNS: dict[str, list[str]] = {
    "greenhouse": ["boards.greenhouse.io", "grnh.se"],
    "lever": ["jobs.lever.co", "lever.co/"],
    "workday": ["myworkdayjobs.com", "wd1.myworkdayjobs", "wd3.myworkdayjobs"],
}


class PortalRouter:
    def __init__(self, browser: SharedBrowser, resume_path: str, qa: QuestionAnswerer):
        self.browser = browser
        self.greenhouse = GreenhouseApplicator(browser, resume_path, qa)
        self.lever = LeverApplicator(browser, resume_path, qa)

    def detect(self, url: str) -> str | None:
        """Return portal name or None for unrecognised URLs."""
        lower = url.lower()
        for portal, patterns in PORTAL_PATTERNS.items():
            if any(p in lower for p in patterns):
                return portal
        return None

    async def apply(self, job: Job, cover_letter: str = "") -> bool:
        apply_url = job.extra.get("apply_url", "")

        # if we didn't capture the external URL at scraping time, try now
        if not apply_url or "linkedin.com" in apply_url:
            apply_url = await self._resolve_external_url(job.url)

        if not apply_url:
            logger.warning(f"Could not resolve external apply URL for {job.title} @ {job.company} — skipping")
            return False

        portal = self.detect(apply_url)

        if portal == "greenhouse":
            return await self.greenhouse.apply(job, apply_url, cover_letter)
        if portal == "lever":
            return await self.lever.apply(job, apply_url, cover_letter)
        if portal == "workday":
            logger.info(f"Workday not yet supported — skipping {job.title} @ {job.company}")
            return False

        logger.warning(f"Unsupported portal for '{apply_url}' — skipping {job.title} @ {job.company}")
        return False

    async def _resolve_external_url(self, linkedin_job_url: str) -> str:
        """Navigate to the LinkedIn job page and extract the external apply URL."""
        page = await self.browser.linkedin_page()
        try:
            await page.goto(linkedin_job_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 3))

            for sel in (
                'a.jobs-apply-button[href]',
                'a[data-tracking-control-name*="apply"][href]',
                '.job-details-jobs-unified-top-card__apply-button a[href]',
                'a[href*="externalApply"]',
            ):
                el = await page.query_selector(sel)
                if not el:
                    continue
                href = await el.get_attribute("href") or ""
                if not href:
                    continue
                decoded = _decode_linkedin_redirect(href)
                if decoded and "linkedin.com" not in decoded:
                    return decoded
        except Exception as e:
            logger.debug(f"Could not resolve external URL from {linkedin_job_url}: {e}")
        finally:
            await page.close()
        return ""


def _decode_linkedin_redirect(href: str) -> str:
    """Extract the real external URL from LinkedIn's /jobs/view/externalApply?url=... wrapper."""
    if "url=" in href:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        urls = qs.get("url", [])
        if urls:
            return urllib.parse.unquote(urls[0])
    return href
