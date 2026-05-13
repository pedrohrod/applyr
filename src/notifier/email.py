from __future__ import annotations
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        to_address: str,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.to_address = to_address
        self.use_tls = use_tls

    async def send(self, subject: str, body: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sync, subject, body)

    def _send_sync(self, subject: str, body: str) -> None:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[applyr] {subject}"
            msg["From"] = self.username
            msg["To"] = self.to_address
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.username, self.to_address, msg.as_string())
        except Exception as e:
            logger.warning(f"Email notification error: {e}")
