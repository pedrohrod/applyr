import asyncio
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(settings: dict) -> None:
    log_cfg = settings.get("logging", {})
    logger.remove()
    logger.add(sys.stderr, level=log_cfg.get("level", "INFO"))
    log_file = log_cfg.get("file", "logs/apply-job.log")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logger.add(log_file, rotation="10 MB", retention="7 days", level="DEBUG")


async def main() -> None:
    settings = load_yaml("config/settings.yaml")
    profile = load_yaml("config/profile.yaml")
    setup_logging(settings)

    resume_path = Path("resume/resume.pdf")
    if not resume_path.exists():
        logger.error("Currículo não encontrado em resume/resume.pdf — coloque seu PDF lá e tente novamente.")
        sys.exit(1)

    from src.orchestrator import Orchestrator
    orchestrator = Orchestrator(settings, profile)
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
