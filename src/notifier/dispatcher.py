from __future__ import annotations
import asyncio
from loguru import logger
from src.notifier.base import Notifier


class NotificationDispatcher:
    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers

    async def _broadcast(self, subject: str, body: str) -> None:
        if not self.notifiers:
            return
        results = await asyncio.gather(
            *[n.send(subject, body) for n in self.notifiers],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Notifier error (suppressed): {r}")

    async def notify_applied(self, job_title: str, company: str, platform: str, score: int, url: str) -> None:
        subject = f"✅ Applied: {job_title} @ {company}"
        body = (
            f"Job: {job_title}\n"
            f"Company: {company}\n"
            f"Platform: {platform}\n"
            f"Match score: {score}/100\n"
            f"URL: {url}"
        )
        await self._broadcast(subject, body)

    async def notify_failed(self, job_title: str, company: str, reason: str) -> None:
        subject = f"❌ Failed: {job_title} @ {company}"
        body = f"Job: {job_title}\nCompany: {company}\nReason: {reason}"
        await self._broadcast(subject, body)

    @classmethod
    def from_settings(cls, settings: dict) -> NotificationDispatcher:
        import os
        notifiers: list[Notifier] = []
        notif = settings.get("notifications", {})

        if notif.get("telegram", {}).get("enabled"):
            from src.notifier.telegram import TelegramNotifier
            notifiers.append(TelegramNotifier(
                bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
                chat_id=os.environ["TELEGRAM_CHAT_ID"],
            ))

        if notif.get("email", {}).get("enabled"):
            from src.notifier.email import EmailNotifier
            email_cfg = notif["email"]
            username = os.environ["SMTP_USERNAME"]
            to_addr = email_cfg.get("to") or os.environ.get("NOTIFY_TO") or username
            notifiers.append(EmailNotifier(
                smtp_host=email_cfg.get("smtp_host", "smtp.gmail.com"),
                smtp_port=email_cfg.get("smtp_port", 587),
                username=username,
                password=os.environ["SMTP_PASSWORD"],
                to_address=to_addr,
            ))

        if notifiers:
            logger.info(f"Notifications enabled with {len(notifiers)} notifier(s)")
        return cls(notifiers)
