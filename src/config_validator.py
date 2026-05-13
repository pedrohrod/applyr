from __future__ import annotations
import os
import sys
from pathlib import Path
import yaml
from loguru import logger


VALID_LANGUAGES = {"auto", "en", "pt", "es", "de", "fr"}

REQUIRED_BY_PROVIDER = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "gemini": ["GEMINI_API_KEY"],
    "ollama": ["LLM_API_URL"],
}

REQUIRED_PLATFORM_VARS = {
    "linkedin": ["LINKEDIN_EMAIL", "LINKEDIN_PASSWORD"],
    "gupy": ["GUPY_EMAIL", "GUPY_PASSWORD"],
}

VALID_DATE_POSTED = {"all_time", "month", "week", "24_hours"}
VALID_DISTANCES = {0, 5, 10, 25, 50, 100}


def validate(settings: dict, resume_path: str = "resume/resume.pdf") -> None:
    errors: list[str] = []

    # LLM provider
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider not in REQUIRED_BY_PROVIDER:
        errors.append(
            f"LLM_PROVIDER='{provider}' is invalid. Valid: {', '.join(REQUIRED_BY_PROVIDER)}"
        )
    else:
        for var in REQUIRED_BY_PROVIDER[provider]:
            if not os.environ.get(var):
                errors.append(f"Missing env var: {var} (required for provider '{provider}')")

    # Platform credentials
    platforms = settings.get("platforms", {})
    for platform, vars_ in REQUIRED_PLATFORM_VARS.items():
        if platforms.get(platform, {}).get("enabled"):
            for var in vars_:
                if not os.environ.get(var):
                    errors.append(f"Missing env var: {var} (required because {platform} is enabled)")

    # Resume file
    if not Path(resume_path).exists():
        errors.append(f"Resume not found: {resume_path} — place your PDF there before running.")

    # Matching threshold
    threshold = settings.get("matching", {}).get("threshold", 70)
    if not isinstance(threshold, int) or not (0 <= threshold <= 100):
        errors.append(f"matching.threshold must be an integer between 0 and 100, got: {threshold!r}")

    # date_posted
    date_posted = settings.get("job_search", {}).get("date_posted", "month")
    if date_posted not in VALID_DATE_POSTED:
        errors.append(f"job_search.date_posted='{date_posted}' is invalid. Valid: {', '.join(VALID_DATE_POSTED)}")

    # distance
    distance = settings.get("job_search", {}).get("distance", 0)
    if distance not in VALID_DISTANCES:
        errors.append(f"job_search.distance={distance} is invalid. Valid: {sorted(VALID_DISTANCES)}")

    # daily limits sanity
    for platform in ("linkedin", "gupy"):
        limit = platforms.get(platform, {}).get("daily_limit", 1)
        if not isinstance(limit, int) or limit < 1:
            errors.append(f"platforms.{platform}.daily_limit must be a positive integer, got: {limit!r}")

    # keywords must not be empty if any platform is enabled
    if any(platforms.get(p, {}).get("enabled") for p in ("linkedin", "gupy")):
        keywords = settings.get("job_search", {}).get("keywords", [])
        if not keywords:
            errors.append("job_search.keywords cannot be empty when any platform is enabled")

    # language
    lang = settings.get("language", "auto")
    if lang not in VALID_LANGUAGES:
        errors.append(f"language='{lang}' is invalid. Valid: {', '.join(sorted(VALID_LANGUAGES))}")

    # notification env vars (only warn, not fatal — notifications are optional)
    notif = settings.get("notifications", {})
    if notif.get("telegram", {}).get("enabled"):
        for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            if not os.environ.get(var):
                errors.append(f"Missing env var: {var} (required because notifications.telegram is enabled)")
    if notif.get("email", {}).get("enabled"):
        for var in ("SMTP_USERNAME", "SMTP_PASSWORD", "NOTIFY_TO"):
            if not os.environ.get(var):
                errors.append(f"Missing env var: {var} (required because notifications.email is enabled)")

    if errors:
        logger.error("Configuration errors found — fix them before running:\n")
        for i, err in enumerate(errors, 1):
            logger.error(f"  {i}. {err}")
        sys.exit(1)

    logger.info("Configuration validated successfully")
