from __future__ import annotations
import asyncio
import random
from pathlib import Path
from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.browser import SharedBrowser
from src.scrapers.linkedin import Job
from src.ai.question_answerer import QuestionAnswerer


class LeverApplicator:
    def __init__(self, browser: SharedBrowser, resume_path: str, qa: QuestionAnswerer):
        self.browser = browser
        self.resume_path = resume_path
        self.qa = qa

    async def apply(self, job: Job, apply_url: str, cover_letter: str = "") -> bool:
        page = await self.browser.portal_page()
        try:
            await page.goto(apply_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 3))
            return await self._fill_form(page, job, cover_letter)
        except PlaywrightTimeout:
            logger.warning(f"Timeout on Lever apply: {job.title} @ {job.company}")
            return False
        except Exception as e:
            logger.error(f"Lever apply error ({job.title}): {e}")
            return False
        finally:
            await page.close()

    async def _fill_form(self, page: Page, job: Job, cover_letter: str) -> bool:
        profile = self.qa.profile
        personal = profile.get("personal", {})

        # Lever uses a single "name" field (full name)
        await _fill_if_empty(page, 'input[name="name"]', personal.get("name", ""))
        await _fill_if_empty(page, 'input[name="email"]', personal.get("email", ""))
        await _fill_if_empty(page, 'input[name="phone"]', personal.get("phone", ""))
        await _fill_if_empty(page, 'input[name="org"]', personal.get("company", ""))
        await _fill_if_empty(page, 'input[name="urls[LinkedIn]"]', personal.get("linkedin_url", ""))

        # resume upload
        file_input = await page.query_selector('input[type="file"]')
        if file_input and Path(self.resume_path).exists():
            await file_input.set_input_files(self.resume_path)
            await asyncio.sleep(1)

        # cover letter / additional info
        if cover_letter:
            for sel in ('textarea[name="comments"]', 'textarea[name="summary"]', "textarea:visible"):
                cl = await page.query_selector(sel)
                if cl and not await cl.input_value():
                    await cl.fill(cover_letter)
                    break

        # custom questions — Lever wraps them in .application-field
        for field in await page.query_selector_all(".application-field"):
            inp = await field.query_selector("input[type='text']:visible, textarea:visible")
            if not inp or await inp.input_value():
                continue
            label_el = await field.query_selector("label")
            label = (await label_el.inner_text()).strip() if label_el else ""
            if label:
                await inp.fill(self.qa.answer(label))
                await asyncio.sleep(0.3)

        # selects
        for field in await page.query_selector_all(".application-field"):
            sel_el = await field.query_selector("select:visible")
            if not sel_el:
                continue
            label_el = await field.query_selector("label")
            label = (await label_el.inner_text()).strip() if label_el else ""
            options = [
                (await o.inner_text()).strip()
                for o in await sel_el.query_selector_all("option")
            ]
            options = [o for o in options if o and o.lower() not in ("", "select")]
            if not options:
                continue
            answer = self.qa.answer(label or "Select", options)
            best = next((o for o in options if o.lower() == answer.lower()), options[0])
            try:
                await sel_el.select_option(label=best)
            except Exception:
                pass

        # submit
        for sub_sel in ('button.template-btn-submit', 'button[type="submit"]', 'input[type="submit"]'):
            submit = await page.query_selector(sub_sel)
            if submit:
                await submit.click()
                await asyncio.sleep(3)
                break

        # success detection
        url = page.url.lower()
        if "confirmation" in url or "thank" in url:
            logger.info(f"Lever application submitted: {job.title} @ {job.company}")
            return True

        for msg_sel in ('.thanks-page', '.confirmation', 'h2', 'h1'):
            el = await page.query_selector(msg_sel)
            if el:
                text = (await el.inner_text()).lower()
                if any(w in text for w in ("thank", "received", "submitted", "application")):
                    logger.info(f"Lever application submitted: {job.title} @ {job.company}")
                    return True

        logger.warning(f"Lever submission uncertain for {job.title} @ {job.company}")
        return False


async def _fill_if_empty(page: Page, selector: str, value: str) -> None:
    if not value:
        return
    try:
        el = await page.query_selector(selector)
        if el and not await el.input_value():
            await el.fill(value)
            await asyncio.sleep(0.2)
    except Exception:
        pass
