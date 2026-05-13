import asyncio
import aiohttp
from loguru import logger
from src.scrapers.linkedin import Job


class GupyScraper:
    API = "https://portal.api.gupy.io/api/job"

    async def scrape_jobs(self, keywords: list[str], max_jobs: int = 50) -> list[Job]:
        jobs: list[Job] = []
        async with aiohttp.ClientSession() as session:
            for keyword in keywords:
                if len(jobs) >= max_jobs:
                    break
                found = await self._search(session, keyword, max_jobs - len(jobs))
                jobs.extend(found)
        seen: set[str] = set()
        unique = [j for j in jobs if not (j.id in seen or seen.add(j.id))]
        logger.info(f"Gupy: {len(unique)} unique jobs found")
        return unique

    async def _search(self, session: aiohttp.ClientSession, keyword: str, limit: int) -> list[Job]:
        jobs: list[Job] = []
        offset, per_page = 0, 10
        while len(jobs) < limit:
            try:
                async with session.get(
                    self.API,
                    params={"jobName": keyword, "limit": per_page, "offset": offset},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        break
                    items = (await resp.json()).get("data", [])
                    if not items:
                        break
                    for item in items:
                        if len(jobs) >= limit:
                            break
                        job = self._parse_job(item)
                        if job:
                            jobs.append(job)
                    if len(items) < per_page:
                        break
                    offset += per_page
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Gupy API error (keyword={keyword}): {e}")
                break
        return jobs

    def _parse_job(self, item: dict) -> Job | None:
        try:
            job_id = str(item.get("id", ""))
            title = item.get("name", "")
            if not title:
                return None
            company = item.get("careerPageName", "") or item.get("company", {}).get("name", "")
            city, state = item.get("city", ""), item.get("state", "")
            location = f"{city}, {state}".strip(", ")
            career_page = item.get("careerPageName", "").lower().replace(" ", "-")
            return Job(
                id=job_id,
                title=title,
                company=company,
                location=location,
                url=f"https://{career_page}.gupy.io/jobs/{job_id}",
                description=item.get("description", "") or "",
                requirements=item.get("prerequisites", "") or "",
                platform="gupy",
                easy_apply=True,
            )
        except Exception as e:
            logger.debug(f"Failed to parse Gupy job: {e}")
            return None
