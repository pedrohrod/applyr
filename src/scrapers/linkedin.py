import asyncio
import random
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
    ) -> list[Job]:
        jobs: list[Job] = []
        page = await self.browser.linkedin_page()
        try:
            for keyword in keywords:
                if len(jobs) >= max_jobs:
                    break
                found = await self._search_keyword(page, keyword, location, max_jobs - len(jobs))
                jobs.extend(found)
        except Exception as e:
            logger.error(f"LinkedIn scraping error: {e}")
        finally:
            await page.close()

        seen: set[str] = set()
        unique = [j for j in jobs if not (j.id in seen or seen.add(j.id))]
        logger.info(f"LinkedIn: {len(unique)} unique jobs found")
        return unique

    async def _search_keyword(self, page: Page, keyword: str, location: str, limit: int) -> list[Job]:
        jobs: list[Job] = []
        url = (
            f"{self.BASE}/jobs/search/?keywords={keyword.replace(' ', '%20')}"
            f"&location={location.replace(' ', '%20')}&f_LF=f_AL"
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
                job = await self._extract_card(page, card)
                if job:
                    jobs.append(job)
            next_btn = await page.query_selector('button[aria-label="Next"]')
            if not next_btn:
                break
            await next_btn.click()
            await asyncio.sleep(random.uniform(2, 3))
        return jobs

    async def _extract_card(self, page: Page, card) -> Job | None:
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

            return Job(
                id=job_id or current_url,
                title=title,
                company=company,
                location=location,
                url=current_url,
                description=description,
                platform="linkedin",
                easy_apply=easy_apply,
            )
        except Exception as e:
            logger.debug(f"Failed to extract job card: {e}")
            return None


async def _text(page: Page, selector: str) -> str:
    try:
        el = await page.query_selector(selector)
        if el:
            return (await el.inner_text()).strip()
    except Exception:
        pass
    return ""
