from __future__ import annotations
import asyncio
import random
from pathlib import Path
from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.browser import SharedBrowser
from src.scrapers.linkedin import Job
from src.ai.question_answerer import QuestionAnswerer


class GreenhouseApplicator:
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
            logger.warning(f"Timeout on Greenhouse apply: {job.title} @ {job.company}")
            return False
        except Exception as e:
            logger.error(f"Greenhouse apply error ({job.title}): {e}")
            return False
        finally:
            await page.close()

    async def _fill_form(self, page: Page, job: Job, cover_letter: str) -> bool:
        profile = self.qa.profile
        personal = profile.get("personal", {})
        name_parts = personal.get("name", "").split(None, 1)
        first = name_parts[0] if name_parts else ""
        last = name_parts[1] if len(name_parts) > 1 else ""

        await _fill_if_empty(page, "input#first_name", first)
        await _fill_if_empty(page, "input#last_name", last)
        await _fill_if_empty(page, "input#email", personal.get("email", ""))
        await _fill_if_empty(page, "input#phone", personal.get("phone", ""))
        await _fill_if_empty(page, 'input[name*="linkedin"]', personal.get("linkedin_url", ""))

        # resume upload — Greenhouse uses a hidden file input
        for sel in ('input[name="job_application[resume]"]', 'input[type="file"]'):
            file_input = await page.query_selector(sel)
            if file_input and Path(self.resume_path).exists():
                await file_input.set_input_files(self.resume_path)
                await asyncio.sleep(1)
                break

        # cover letter
        if cover_letter:
            for sel in ("textarea#cover_letter_text", "textarea#cover_letter", "textarea[name*='cover']"):
                cl = await page.query_selector(sel)
                if cl:
                    await cl.fill(cover_letter)
                    break

        # custom free-text questions
        for inp in await page.query_selector_all('input[type="text"]:visible, textarea:visible'):
            if await inp.input_value():
                continue
            label = await _get_label(page, inp)
            if label:
                await inp.fill(self.qa.answer(label))
                await asyncio.sleep(0.3)

        # selects (standard HTML, not Select2)
        for sel_el in await page.query_selector_all("select:visible"):
            label = await _get_label(page, sel_el)
            options = [
                (await o.inner_text()).strip()
                for o in await sel_el.query_selector_all("option")
            ]
            options = [o for o in options if o and o.lower() not in ("", "please select", "select")]
            if not options:
                continue
            answer = self.qa.answer(label or "Select", options)
            best = next((o for o in options if o.lower() == answer.lower()), options[0])
            try:
                await sel_el.select_option(label=best)
            except Exception:
                pass

        # submit
        for sub_sel in ('input[type="submit"]', 'button[type="submit"]'):
            submit = await page.query_selector(sub_sel)
            if submit:
                await submit.click()
                await asyncio.sleep(3)
                break

        # success detection
        url = page.url.lower()
        if "confirmation" in url or "thank" in url or "submitted" in url:
            logger.info(f"Greenhouse application submitted: {job.title} @ {job.company}")
            return True

        for msg_sel in ('.confirmation', '[class*="confirmation"]', 'h2', 'h1'):
            el = await page.query_selector(msg_sel)
            if el:
                text = (await el.inner_text()).lower()
                if any(w in text for w in ("thank", "received", "submitted", "confirmed")):
                    logger.info(f"Greenhouse application submitted: {job.title} @ {job.company}")
                    return True

        logger.warning(f"Greenhouse submission uncertain for {job.title} @ {job.company}")
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
