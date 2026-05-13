import asyncio
import random
from pathlib import Path
from loguru import logger
from playwright.async_api import async_playwright, Page
from src.scrapers.linkedin import Job
from src.ai.question_answerer import QuestionAnswerer


class GupyApplicator:
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

                apply_btn = await page.query_selector('a[data-testid="job-apply-button"], button:has-text("Candidatar")')
                if not apply_btn:
                    logger.warning(f"Botão de candidatura não encontrado: {job.title}")
                    return False

                await apply_btn.click()
                await asyncio.sleep(2)

                return await self._fill_application(page, cover_letter)
            except Exception as e:
                logger.error(f"Erro ao aplicar na Gupy ({job.title} @ {job.company}): {e}")
                return False
            finally:
                await browser.close()

    async def _login(self, page: Page) -> None:
        await page.goto("https://portal.gupy.io/login", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await page.fill('input[name="email"]', self.email)
        await page.fill('input[name="password"]', self.password)
        submit = await page.query_selector('button[type="submit"]')
        if submit:
            await submit.click()
        await asyncio.sleep(3)

    async def _fill_application(self, page: Page, cover_letter: str) -> bool:
        max_steps = 8
        for step in range(max_steps):
            await asyncio.sleep(1.5)

            # upload de currículo
            file_input = await page.query_selector('input[type="file"]')
            if file_input and Path(self.resume_path).exists():
                await file_input.set_input_files(self.resume_path)
                await asyncio.sleep(1)

            # cover letter / apresentação
            if cover_letter:
                for selector in ['textarea[name*="cover"]', 'textarea[placeholder*="resentação"]', 'textarea']:
                    area = await page.query_selector(selector)
                    if area:
                        current = await area.input_value()
                        if not current:
                            await area.fill(cover_letter)
                        break

            # preenche inputs de texto vazios
            inputs = await page.query_selector_all('input[type="text"]:visible')
            for inp in inputs:
                val = await inp.input_value()
                if val:
                    continue
                label = await self._get_label(page, inp)
                if label:
                    answer = self.qa.answer(label)
                    await inp.fill(answer)
                    await asyncio.sleep(0.3)

            # botão finalizar
            finish_btn = await page.query_selector('button:has-text("Enviar"), button:has-text("Finalizar"), button:has-text("Candidatar")')
            if finish_btn:
                await finish_btn.click()
                await asyncio.sleep(2)
                logger.info("Aplicação submetida com sucesso na Gupy")
                return True

            # botão próximo
            next_btn = await page.query_selector('button:has-text("Próximo"), button:has-text("Continuar")')
            if next_btn:
                await next_btn.click()
            else:
                break

        return False

    async def _get_label(self, page: Page, element) -> str:
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
