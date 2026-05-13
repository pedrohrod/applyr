from __future__ import annotations
import asyncio
import random
import os
from loguru import logger

from src.browser import SharedBrowser
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

        # shared browser — login once, reuse across all scraping + applying
        self.browser = SharedBrowser()
        self._linkedin_email = linkedin_email
        self._linkedin_password = linkedin_password
        self._gupy_email = gupy_email
        self._gupy_password = gupy_password

        self.linkedin_scraper = LinkedInScraper(self.browser)
        self.gupy_scraper = GupyScraper()

        self.linkedin_applicator = LinkedInApplicator(self.browser, resume_path, self.qa)
        self.gupy_applicator = GupyApplicator(self.browser, resume_path, self.qa)

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
        self.location_blacklist = [loc.lower() for loc in f.get("location_blacklist", [])]
        self.apply_once_at_company = f.get("apply_once_at_company", True)

    def _is_blacklisted(self, job: Job) -> tuple[bool, str]:
        for term in self.company_blacklist:
            if term in job.company.lower():
                return True, f"company blacklisted: '{term}'"
        for term in self.title_blacklist:
            if term in job.title.lower():
                return True, f"title blacklisted: '{term}'"
        for term in self.location_blacklist:
            if term in job.location.lower():
                return True, f"location blacklisted: '{term}'"
        return False, ""

    async def run(self) -> None:
        logger.info("=== Starting applyr workflow ===")

        await self.browser.start()
        try:
            await self._run_workflow()
        finally:
            await self.browser.close()

    async def _run_workflow(self) -> None:
        platforms = self.settings["platforms"]
        js = self.settings["job_search"]
        keywords = js["keywords"]
        locations = js.get("locations", ["Brazil"])

        # login once per platform
        if platforms.get("linkedin", {}).get("enabled"):
            ok = await self.browser.login_linkedin(self._linkedin_email, self._linkedin_password)
            if not ok:
                logger.error("LinkedIn login failed — disabling LinkedIn for this run")
                platforms["linkedin"]["enabled"] = False

        if platforms.get("gupy", {}).get("enabled"):
            ok = await self.browser.login_gupy(self._gupy_email, self._gupy_password)
            if not ok:
                logger.warning("Gupy login failed — will attempt applications anyway")

        # scrape
        jobs: list[Job] = []
        if platforms.get("linkedin", {}).get("enabled"):
            jobs.extend(await self.linkedin_scraper.scrape_jobs(keywords, locations[0], self.max_jobs))
        if platforms.get("gupy", {}).get("enabled"):
            jobs.extend(await self.gupy_scraper.scrape_jobs(keywords, self.max_jobs))

        logger.info(f"Total jobs collected: {len(jobs)}")

        ln_limit = platforms.get("linkedin", {}).get("daily_limit", 40)
        gupy_limit = platforms.get("gupy", {}).get("daily_limit", 30)
        daily_counts: dict[str, int] = {"linkedin": 0, "gupy": 0}
        companies_this_session: set[str] = set()
        total_applied = 0

        for job in jobs:
            if total_applied >= self.max_per_session:
                logger.info(f"Session limit of {self.max_per_session} reached.")
                break

            if self.tracker.should_skip(job.id):
                logger.debug(f"Skipping (already handled): {job.title} @ {job.company}")
                continue

            limit = ln_limit if job.platform == "linkedin" else gupy_limit
            if daily_counts.get(job.platform, 0) >= limit:
                logger.debug(f"Daily limit reached for {job.platform}")
                continue

            if self.apply_once_at_company and job.company.lower() in companies_this_session:
                logger.debug(f"Already applied to {job.company} this session — skipping")
                self.tracker.record(job, 0, "skipped", notes="apply_once_at_company")
                continue

            blocked, reason = self._is_blacklisted(job)
            if blocked:
                logger.debug(f"Blocked ({reason}): {job.title} @ {job.company}")
                self.tracker.record(job, 0, "skipped", notes=reason)
                continue

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

            cover_letter = ""
            if self.attach_cover_letter:
                cover_letter = self.cover_gen.generate(
                    self.resume_text,
                    {"title": job.title, "company": job.company, "description": job.description},
                    self.profile,
                )

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

            delay = self.delay
            if self.randomize:
                delay = random.uniform(delay * 0.5, delay * 1.5)
            await asyncio.sleep(delay)

        stats = self.tracker.stats()
        logger.info(
            f"=== Session complete === "
            f"Applied: {stats['applied']} | Skipped: {stats['skipped']} | "
            f"Failed: {stats['failed']} | Total history: {stats['total']}"
        )
