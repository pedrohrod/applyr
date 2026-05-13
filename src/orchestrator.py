import asyncio
import random
import os
from loguru import logger

from src.scrapers.linkedin import LinkedInScraper, Job
from src.scrapers.gupy import GupyScraper
from src.ai.resume_parser import parse_resume
from src.ai.llm_provider import create_provider
from src.ai.matcher import JobMatcher
from src.ai.cover_letter import CoverLetterGenerator
from src.ai.question_answerer import QuestionAnswerer
from src.applicator.linkedin import LinkedInApplicator
from src.applicator.gupy import GupyApplicator
from src.tracker.db import Tracker


class Orchestrator:
    def __init__(self, settings: dict, profile: dict):
        self.settings = settings
        self.profile = profile

        provider = create_provider()

        linkedin_email = os.environ.get("LINKEDIN_EMAIL", "")
        linkedin_password = os.environ.get("LINKEDIN_PASSWORD", "")
        gupy_email = os.environ.get("GUPY_EMAIL", linkedin_email)
        gupy_password = os.environ.get("GUPY_PASSWORD", linkedin_password)

        resume_path = "resume/resume.pdf"
        self.resume_text = parse_resume(resume_path)

        self.matcher = JobMatcher(provider)
        self.cover_gen = CoverLetterGenerator(provider)
        self.qa = QuestionAnswerer(provider, profile)

        self.linkedin_scraper = LinkedInScraper(linkedin_email, linkedin_password)
        self.gupy_scraper = GupyScraper()

        self.linkedin_applicator = LinkedInApplicator(linkedin_email, linkedin_password, resume_path, self.qa)
        self.gupy_applicator = GupyApplicator(gupy_email, gupy_password, resume_path, self.qa)

        db_url = f"sqlite:///{settings['tracking']['database']}"
        csv_path = settings["tracking"].get("csv_path") if settings["tracking"].get("export_csv") else None
        self.tracker = Tracker(db_url, csv_path)

        m = settings["matching"]
        self.threshold = m["threshold"]
        self.max_jobs = m["max_jobs_per_run"]

        app = settings["application"]
        self.delay = app["delay_between_seconds"]
        self.randomize = app["randomize_delay"]
        self.attach_cover_letter = app["attach_cover_letter"]
        self.max_per_session = app.get("max_per_session", 50)

        f = settings.get("filters", {})
        self.company_blacklist = [c.lower() for c in f.get("company_blacklist", [])]
        self.title_blacklist = [t.lower() for t in f.get("title_blacklist", [])]
        self.location_blacklist = [l.lower() for l in f.get("location_blacklist", [])]
        self.apply_once_at_company = f.get("apply_once_at_company", True)

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------
    def _is_blacklisted(self, job: Job) -> tuple[bool, str]:
        company_lower = job.company.lower()
        for term in self.company_blacklist:
            if term in company_lower:
                return True, f"empresa na blacklist: '{term}'"

        title_lower = job.title.lower()
        for term in self.title_blacklist:
            if term in title_lower:
                return True, f"título na blacklist: '{term}'"

        location_lower = job.location.lower()
        for term in self.location_blacklist:
            if term in location_lower:
                return True, f"localização na blacklist: '{term}'"

        return False, ""

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------
    async def run(self) -> None:
        logger.info("=== Iniciando workflow de aplicação de vagas ===")
        js = self.settings["job_search"]
        keywords = js["keywords"]
        locations = js.get("locations", ["Brasil"])
        platforms = self.settings["platforms"]

        jobs: list[Job] = []

        if platforms.get("linkedin", {}).get("enabled"):
            ln_jobs = await self.linkedin_scraper.scrape_jobs(
                keywords, locations[0], self.max_jobs
            )
            jobs.extend(ln_jobs)

        if platforms.get("gupy", {}).get("enabled"):
            gupy_jobs = await self.gupy_scraper.scrape_jobs(keywords, self.max_jobs)
            jobs.extend(gupy_jobs)

        logger.info(f"Total de vagas coletadas: {len(jobs)}")

        ln_limit = platforms.get("linkedin", {}).get("daily_limit", 40)
        gupy_limit = platforms.get("gupy", {}).get("daily_limit", 30)
        daily_counts: dict[str, int] = {"linkedin": 0, "gupy": 0}
        companies_this_session: set[str] = set()
        total_applied = 0

        for job in jobs:
            if total_applied >= self.max_per_session:
                logger.info(f"Limite de {self.max_per_session} aplicações por sessão atingido.")
                break

            # já aplicou antes?
            if self.tracker.already_applied(job.id):
                logger.debug(f"Já aplicado: {job.title} @ {job.company}")
                continue

            # limite diário por plataforma
            limit = ln_limit if job.platform == "linkedin" else gupy_limit
            if daily_counts.get(job.platform, 0) >= limit:
                logger.debug(f"Limite diário atingido para {job.platform}")
                continue

            # apply_once_at_company
            if self.apply_once_at_company and job.company.lower() in companies_this_session:
                logger.debug(f"Já aplicou na {job.company} nessa sessão — pulando")
                self.tracker.record(job, 0, "skipped", notes="apply_once_at_company")
                continue

            # blacklists
            blocked, reason = self._is_blacklisted(job)
            if blocked:
                logger.debug(f"Bloqueado ({reason}): {job.title} @ {job.company}")
                self.tracker.record(job, 0, "skipped", notes=reason)
                continue

            # scoring com IA
            match = self.matcher.score(self.resume_text, {
                "title": job.title,
                "company": job.company,
                "description": job.description,
                "requirements": job.requirements,
            })
            logger.info(
                f"[score={match.score:3d}] {job.title} @ {job.company} ({job.platform}) — {match.recommendation}"
            )

            if match.score < self.threshold:
                self.tracker.record(job, match.score, "skipped", notes=match.recommendation)
                continue

            # cover letter
            cover_letter = ""
            if self.attach_cover_letter:
                cover_letter = self.cover_gen.generate(
                    self.resume_text,
                    {"title": job.title, "company": job.company, "description": job.description},
                    self.profile,
                )

            # aplicar
            success = False
            if job.platform == "linkedin":
                success = await self.linkedin_applicator.apply(job, cover_letter)
            elif job.platform == "gupy":
                success = await self.gupy_applicator.apply(job, cover_letter)

            status = "applied" if success else "failed"
            self.tracker.record(job, match.score, status, cover_letter, match.recommendation)

            if success:
                total_applied += 1
                daily_counts[job.platform] = daily_counts.get(job.platform, 0) + 1
                companies_this_session.add(job.company.lower())

            # delay anti-bot
            delay = self.delay
            if self.randomize:
                delay = random.uniform(delay * 0.5, delay * 1.5)
            await asyncio.sleep(delay)

        stats = self.tracker.stats()
        logger.info(
            f"=== Sessão concluída === "
            f"Aplicados: {stats['applied']} | Pulados: {stats['skipped']} | "
            f"Falhas: {stats['failed']} | Total histórico: {stats['total']}"
        )
