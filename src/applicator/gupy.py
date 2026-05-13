import asyncio
import random
from pathlib import Path
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.browser import SharedBrowser
from src.scrapers.linkedin import Job
from src.ai.question_answerer import QuestionAnswerer

MAX_STEPS = 8


class GupyApplicator:
    def __init__(self, browser: SharedBrowser, resume_path: str, qa: QuestionAnswerer):
        self.browser = browser
        self.resume_path = resume_path
        self.qa = qa

    @retry(
        retry=retry_if_exception_type((PlaywrightTimeout, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        reraise=True,
    )
    async def apply(self, job: Job, cover_letter: str = "") -> bool:
        page = await self.browser.gupy_page()
        try:
            await page.goto(job.url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 3))

            apply_btn = (
                await page.query_selector('a[data-testid="job-apply-button"]') or
                await page.query_selector('button:has-text("Candidatar")') or
                await page.query_selector('a:has-text("Candidatar")')
            )
            if not apply_btn:
                logger.warning(f"Apply button not found: {job.title} @ {job.company}")
                return False

            await apply_btn.click()
            await asyncio.sleep(2)

            return await self._fill_application(page, cover_letter)
        except PlaywrightTimeout:
            logger.warning(f"Timeout on {job.title} @ {job.company} — will retry")
            raise
        except Exception as e:
            logger.error(f"Error applying on Gupy ({job.title} @ {job.company}): {e}")
            return False
        finally:
            await page.close()

    async def _fill_application(self, page: Page, cover_letter: str) -> bool:
        for step in range(MAX_STEPS):
            await asyncio.sleep(1.5)

            # resume upload
            file_input = await page.query_selector('input[type="file"]')
            if file_input and Path(self.resume_path).exists():
                await file_input.set_input_files(self.resume_path)
                await asyncio.sleep(1)

            # cover letter
            if cover_letter:
                for selector in (
                    'textarea[name*="cover"]',
                    'textarea[placeholder*="resentação"]',
                    'textarea[placeholder*="carta"]',
                ):
                    area = await page.query_selector(selector)
                    if area and not await area.input_value():
                        await area.fill(cover_letter)
                        break

            # free-text inputs
            for inp in await page.query_selector_all('input[type="text"]:visible'):
                if await inp.input_value():
                    continue
                label = await _get_label(page, inp)
                if label:
                    await inp.fill(self.qa.answer(label))
                    await asyncio.sleep(0.3)

            # finish / next
            finish_btn = (
                await page.query_selector('button:has-text("Enviar")') or
                await page.query_selector('button:has-text("Finalizar")') or
                await page.query_selector('button:has-text("Candidatar")')
            )
            if finish_btn:
                await finish_btn.click()
                await asyncio.sleep(2)
                logger.info("Application submitted on Gupy")
                return True

            next_btn = (
                await page.query_selector('button:has-text("Próximo")') or
                await page.query_selector('button:has-text("Continuar")')
            )
            if next_btn:
                await next_btn.click()
            else:
                break

        return False


async def _get_label(page: Page, element) -> str:
    try:
        el_id = await element.get_attribute("id")
        if el_id:
            label_el = await page.query_selector(f'label[for="{el_id}"]')
            if label_el:
                return (await label_el.inner_text()).strip()
        placeholder = await element.get_attribute("placeholder") or ""
        aria = await element.get_attribute("aria-label") or ""
        return placeholder or aria
    except Exception:
        return ""
