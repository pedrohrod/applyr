from __future__ import annotations
import asyncio
import random
from pathlib import Path
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.browser import SharedBrowser, is_captcha
from src.scrapers.linkedin import Job
from src.ai.question_answerer import QuestionAnswerer

CAPTCHA_WAIT = 90   # seconds to wait when captcha is detected mid-apply
MAX_STEPS = 10


class LinkedInApplicator:
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
        page = await self.browser.linkedin_page()
        try:
            await page.goto(job.url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 3))

            if await is_captcha(page):
                logger.warning(f"CAPTCHA detected before applying to {job.title} — waiting {CAPTCHA_WAIT}s")
                await asyncio.sleep(CAPTCHA_WAIT)
                await page.reload()
                if await is_captcha(page):
                    logger.error("CAPTCHA persists — skipping this job")
                    return False

            easy_apply_btn = await page.query_selector('button[aria-label*="Easy Apply"]')
            if not easy_apply_btn:
                logger.warning(f"Easy Apply button not found: {job.title} @ {job.company}")
                return False

            await easy_apply_btn.click()
            await asyncio.sleep(1.5)

            return await self._fill_application(page, cover_letter)
        except PlaywrightTimeout:
            logger.warning(f"Timeout on {job.title} @ {job.company} — will retry")
            raise
        except Exception as e:
            logger.error(f"Error applying to {job.title} @ {job.company}: {e}")
            return False
        finally:
            await page.close()

    async def _fill_application(self, page: Page, cover_letter: str) -> bool:
        for step in range(MAX_STEPS):
            await asyncio.sleep(1)

            if await is_captcha(page):
                logger.warning(f"CAPTCHA during form filling (step {step + 1}) — waiting {CAPTCHA_WAIT}s")
                await asyncio.sleep(CAPTCHA_WAIT)
                if await is_captcha(page):
                    return False

            # resume upload
            resume_input = await page.query_selector('input[type="file"]')
            if resume_input and Path(self.resume_path).exists():
                await resume_input.set_input_files(self.resume_path)
                await asyncio.sleep(1)

            # cover letter
            if cover_letter:
                cl_area = await page.query_selector('textarea[id*="cover"]') or \
                          await page.query_selector('textarea[placeholder*="cover"]')
                if cl_area:
                    await cl_area.fill(cover_letter)

            # free-text inputs
            for inp in await page.query_selector_all('input[type="text"]:visible, textarea:visible'):
                label = await _get_label(page, inp)
                if not label:
                    continue
                if await inp.input_value():
                    continue
                answer = self.qa.answer(label)
                await inp.fill(answer)
                await asyncio.sleep(0.3)

            # selects
            for sel in await page.query_selector_all("select:visible"):
                label = await _get_label(page, sel)
                options_els = await sel.query_selector_all("option")
                option_texts = [
                    t for t in [
                        ((await o.inner_text()).strip()) for o in options_els
                    ] if t and t != "Select an option"
                ]
                if not option_texts:
                    continue
                answer = self.qa.answer(label or "Select an option", option_texts)
                best = next((o for o in option_texts if o.lower() == answer.lower()), option_texts[0])
                try:
                    await sel.select_option(label=best)
                except Exception:
                    pass

            # navigation
            submit_btn = await page.query_selector('button[aria-label="Submit application"]')
            if submit_btn:
                await submit_btn.click()
                logger.info("Application submitted on LinkedIn")
                return True

            next_btn = await page.query_selector('button[aria-label="Continue to next step"]')
            review_btn = await page.query_selector('button[aria-label="Review your application"]')

            if next_btn:
                await next_btn.click()
            elif review_btn:
                await review_btn.click()
            else:
                logger.warning(f"No navigation button found at step {step + 1}")
                break

        return False


async def _get_label(page: Page, element) -> str:
    try:
        el_id = await element.get_attribute("id")
        if el_id:
            label_el = await page.query_selector(f'label[for="{el_id}"]')
            if label_el:
                return (await label_el.inner_text()).strip()
        aria = await element.get_attribute("aria-label") or ""
        placeholder = await element.get_attribute("placeholder") or ""
        return aria or placeholder
    except Exception:
        return ""
