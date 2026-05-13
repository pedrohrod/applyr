import asyncio
import random
from pathlib import Path
from loguru import logger
from playwright.async_api import async_playwright, Page
from src.scrapers.linkedin import Job
from src.ai.question_answerer import QuestionAnswerer


class LinkedInApplicator:
    BASE = "https://www.linkedin.com"

    def __init__(self, email: str, password: str, resume_path: str, qa: QuestionAnswerer):
        self.email = email
        self.password = password
        self.resume_path = resume_path
        self.qa = qa

    async def apply(self, job: Job, cover_letter: str = "") -> bool:
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
                await page.goto(job.url, wait_until="domcontentloaded")
                await asyncio.sleep(random.uniform(2, 3))

                easy_apply_btn = await page.query_selector('button[aria-label*="Easy Apply"]')
                if not easy_apply_btn:
                    logger.warning(f"Botão Easy Apply não encontrado para: {job.title}")
                    return False

                await easy_apply_btn.click()
                await asyncio.sleep(1.5)

                success = await self._fill_application(page, cover_letter)
                return success
            except Exception as e:
                logger.error(f"Erro ao aplicar em {job.title} @ {job.company}: {e}")
                return False
            finally:
                await browser.close()

    async def _login(self, page: Page) -> None:
        await page.goto(f"{self.BASE}/login", wait_until="networkidle")
        await page.fill("#username", self.email)
        await page.fill("#password", self.password)
        await page.click('[type="submit"]')
        await page.wait_for_url("**/feed**", timeout=15000)

    async def _fill_application(self, page: Page, cover_letter: str) -> bool:
        max_steps = 10
        for step in range(max_steps):
            await asyncio.sleep(1)

            # upload de currículo
            resume_input = await page.query_selector('input[type="file"]')
            if resume_input and Path(self.resume_path).exists():
                await resume_input.set_input_files(self.resume_path)
                await asyncio.sleep(1)

            # cover letter
            if cover_letter:
                cl_area = await page.query_selector('textarea[id*="cover"]')
                if not cl_area:
                    cl_area = await page.query_selector('textarea[placeholder*="cover"]')
                if cl_area:
                    await cl_area.fill(cover_letter)

            # perguntas de texto livre
            text_inputs = await page.query_selector_all('input[type="text"]:visible, textarea:visible')
            for inp in text_inputs:
                label = await self._get_label(page, inp)
                if not label:
                    continue
                current_val = await inp.input_value()
                if current_val:
                    continue
                answer = self.qa.answer(label)
                await inp.fill(answer)
                await asyncio.sleep(0.3)

            # radio buttons / selects
            await self._handle_selects(page)

            # verificar botões de ação
            submit_btn = await page.query_selector('button[aria-label="Submit application"]')
            if submit_btn:
                await submit_btn.click()
                logger.info("Aplicação submetida com sucesso no LinkedIn")
                return True

            next_btn = await page.query_selector('button[aria-label="Continue to next step"]')
            review_btn = await page.query_selector('button[aria-label="Review your application"]')

            if next_btn:
                await next_btn.click()
            elif review_btn:
                await review_btn.click()
            else:
                logger.warning(f"Não encontrou botão de avançar no passo {step + 1}")
                break

        return False

    async def _handle_selects(self, page: Page) -> None:
        selects = await page.query_selector_all("select:visible")
        for sel in selects:
            label = await self._get_label(page, sel)
            options = await sel.query_selector_all("option")
            option_texts = []
            for opt in options:
                text = await opt.inner_text()
                option_texts.append(text.strip())
            option_texts = [o for o in option_texts if o and o != "Select an option"]
            if not option_texts:
                continue
            answer = self.qa.answer(label or "Selecione uma opção", option_texts)
            best = option_texts[0]
            for opt in option_texts:
                if opt.lower() == answer.lower():
                    best = opt
                    break
            await sel.select_option(label=best)

    async def _get_label(self, page: Page, element) -> str:
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
