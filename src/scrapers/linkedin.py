import asyncio
import random
from dataclasses import dataclass, field
from loguru import logger
from playwright.async_api import async_playwright, Page, BrowserContext


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

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    async def scrape_jobs(
        self,
        keywords: list[str],
        location: str = "Brasil",
        max_jobs: int = 50,
        experience_levels: list[str] | None = None,
    ) -> list[Job]:
        jobs: list[Job] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            try:
                await self._login(page)
                for keyword in keywords:
                    if len(jobs) >= max_jobs:
                        break
                    found = await self._search_keyword(page, keyword, location, max_jobs - len(jobs))
                    jobs.extend(found)
            except Exception as e:
                logger.error(f"Erro no scraping do LinkedIn: {e}")
            finally:
                await browser.close()
        seen = set()
        unique = []
        for j in jobs:
            if j.id not in seen:
                seen.add(j.id)
                unique.append(j)
        logger.info(f"LinkedIn: {len(unique)} vagas únicas encontradas")
        return unique

    async def _login(self, page: Page) -> None:
        logger.info("Fazendo login no LinkedIn...")
        await page.goto(f"{self.BASE}/login", wait_until="networkidle")
        await page.fill("#username", self.email)
        await page.fill("#password", self.password)
        await page.click('[type="submit"]')
        await page.wait_for_url("**/feed**", timeout=15000)
        logger.info("Login no LinkedIn realizado com sucesso")

    async def _search_keyword(self, page: Page, keyword: str, location: str, limit: int) -> list[Job]:
        jobs: list[Job] = []
        url = (
            f"{self.BASE}/jobs/search/?keywords={keyword.replace(' ', '%20')}"
            f"&location={location.replace(' ', '%20')}&f_LF=f_AL"  # f_AL = Easy Apply filter
        )
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(2, 4))

        for page_num in range(5):
            if len(jobs) >= limit:
                break
            cards = await page.query_selector_all(".job-card-container")
            if not cards:
                cards = await page.query_selector_all('[data-job-id]')
            for card in cards:
                if len(jobs) >= limit:
                    break
                job = await self._extract_card(page, card)
                if job:
                    jobs.append(job)
            # próxima página
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

            title = await self._text(page, ".job-details-jobs-unified-top-card__job-title")
            company = await self._text(page, ".job-details-jobs-unified-top-card__company-name")
            location = await self._text(page, ".job-details-jobs-unified-top-card__bullet")
            description = await self._text(page, ".jobs-description__content")
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
            logger.debug(f"Erro ao extrair card: {e}")
            return None

    async def _text(self, page: Page, selector: str) -> str:
        try:
            el = await page.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return ""
