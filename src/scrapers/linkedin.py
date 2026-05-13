from __future__ import annotations
import asyncio
import random
import urllib.parse
from dataclasses import dataclass, field
from loguru import logger
from playwright.async_api import Page

from src.browser import SharedBrowser, is_captcha

CAPTCHA_WAIT = 90


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    requirements: str = ""
    platform: str = "linkedin"
    easy_apply: bool = False
    extra: dict = field(default_factory=dict)


class LinkedInScraper:
    BASE = "https://www.linkedin.com"

    def __init__(self, browser: SharedBrowser):
        self.browser = browser

    async def scrape_jobs(
        self,
        keywords: list[str],
        location: str = "Brazil",
        max_jobs: int = 50,
        easy_apply_only: bool = True,
    ) -> list[Job]:
        jobs: list[Job] = []
        page = await self.browser.linkedin_page()
        try:
            for keyword in keywords:
                if len(jobs) >= max_jobs:
                    break
                found = await self._search_keyword(
                    page, keyword, location, max_jobs - len(jobs), easy_apply_only
                )
                jobs.extend(found)
        except Exception as e:
            logger.error(f"LinkedIn scraping error: {e}")
        finally:
            await page.close()

        seen: set[str] = set()
        unique = [j for j in jobs if not (j.id in seen or seen.add(j.id))]
        logger.info(f"LinkedIn: {len(unique)} unique jobs found")
        return unique

    async def _search_keyword(
        self,
        page: Page,
        keyword: str,
        location: str,
        limit: int,
        easy_apply_only: bool,
    ) -> list[Job]:
        jobs: list[Job] = []
        ea_filter = "&f_LF=f_AL" if easy_apply_only else ""
        url = (
            f"{self.BASE}/jobs/search/?keywords={keyword.replace(' ', '%20')}"
            f"&location={location.replace(' ', '%20')}{ea_filter}"
        )
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(2, 4))

        if await is_captcha(page):
            logger.warning(f"CAPTCHA during LinkedIn job search — waiting {CAPTCHA_WAIT}s")
            await asyncio.sleep(CAPTCHA_WAIT)
            await page.reload()
            if await is_captcha(page):
                logger.error("CAPTCHA persists on job search — skipping keyword")
                return []

        for _ in range(5):
            if len(jobs) >= limit:
                break
            cards = await page.query_selector_all(".job-card-container") or \
                    await page.query_selector_all('[data-job-id]')
            for card in cards:
                if len(jobs) >= limit:
                    break
                job = await self._extract_card(page, card, easy_apply_only)
                if job:
                    jobs.append(job)
            next_btn = await page.query_selector('button[aria-label="Next"]')
            if not next_btn:
                break
            await next_btn.click()
            await asyncio.sleep(random.uniform(2, 3))
        return jobs

    async def _extract_card(
        self, page: Page, card, easy_apply_only: bool = True
    ) -> Job | None:
        try:
            job_id = await card.get_attribute("data-job-id") or ""
            await card.click()
            await asyncio.sleep(random.uniform(1, 2))

            title = await _text(page, ".job-details-jobs-unified-top-card__job-title")
            company = await _text(page, ".job-details-jobs-unified-top-card__company-name")
            location = await _text(page, ".job-details-jobs-unified-top-card__bullet")
            description = await _text(page, ".jobs-description__content")
            current_url = page.url
            easy_apply = await page.query_selector('button[aria-label*="Easy Apply"]') is not None

            if not title or not company:
                return None

            # in easy_apply_only mode skip non-EA jobs entirely
            if easy_apply_only and not easy_apply:
                return None

            # try to extract the external apply URL for non-Easy-Apply jobs
            apply_url = current_url
            if not easy_apply:
                apply_url = await _extract_apply_url(page) or current_url

            return Job(
                id=job_id or current_url,
                title=title,
                company=company,
                location=location,
                url=current_url,
                description=description,
                platform="linkedin",
                easy_apply=easy_apply,
                extra={"apply_url": apply_url},
            )
        except Exception as e:
            logger.debug(f"Failed to extract job card: {e}")
            return None


async def _extract_apply_url(page: Page) -> str:
    """Try to get the external ATS URL from a non-Easy-Apply LinkedIn job detail panel."""
    for sel in (
        'a[href*="externalApply"]',
        'a.jobs-apply-button[href]',
        'a[data-tracking-control-name*="apply"][href]',
        '.job-details-jobs-unified-top-card__apply-button a[href]',
    ):
        el = await page.query_selector(sel)
        if not el:
            continue
        href = await el.get_attribute("href") or ""
        if not href:
            continue
        # LinkedIn wraps external URLs: /jobs/view/externalApply/ID?url=https%3A%2F%2F...
        if "url=" in href:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            urls = qs.get("url", [])
            if urls:
                decoded = urllib.parse.unquote(urls[0])
                if "linkedin.com" not in decoded:
                    return decoded
        if "linkedin.com" not in href:
            return href
    return ""


async def _text(page: Page, selector: str) -> str:
    try:
        el = await page.query_selector(selector)
        if el:
            return (await el.inner_text()).strip()
    except Exception:
        pass
    return ""
