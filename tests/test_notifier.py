from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.notifier.dispatcher import NotificationDispatcher
from src.notifier.telegram import TelegramNotifier
from src.notifier.email import EmailNotifier


# ---------------------------------------------------------------------------
# NotificationDispatcher
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatcher_broadcasts_to_all_notifiers():
    n1 = AsyncMock()
    n2 = AsyncMock()
    dispatcher = NotificationDispatcher([n1, n2])
    await dispatcher.notify_applied("Dev", "Acme", "linkedin", 85, "https://example.com")
    n1.send.assert_awaited_once()
    n2.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatcher_swallows_notifier_errors():
    failing = AsyncMock()
    failing.send.side_effect = Exception("network error")
    ok = AsyncMock()
    dispatcher = NotificationDispatcher([failing, ok])
    # should not raise
    await dispatcher.notify_applied("Dev", "Acme", "linkedin", 85, "https://example.com")
    ok.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatcher_notify_failed():
    n = AsyncMock()
    dispatcher = NotificationDispatcher([n])
    await dispatcher.notify_failed("Dev", "Acme", "timeout")
    n.send.assert_awaited_once()
    subject, body = n.send.call_args[0]
    assert "failed" in subject.lower() or "failed" in body.lower()


def test_from_settings_empty():
    settings = {"notifications": {"telegram": {"enabled": False}, "email": {"enabled": False}}}
    d = NotificationDispatcher.from_settings(settings)
    assert len(d.notifiers) == 0


def test_from_settings_no_notifications_key():
    d = NotificationDispatcher.from_settings({})
    assert len(d.notifiers) == 0


def test_from_settings_telegram(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    settings = {"notifications": {"telegram": {"enabled": True}, "email": {"enabled": False}}}
    d = NotificationDispatcher.from_settings(settings)
    assert any(isinstance(n, TelegramNotifier) for n in d.notifiers)


def test_from_settings_email(monkeypatch):
    monkeypatch.setenv("SMTP_USERNAME", "u@g.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("NOTIFY_TO", "dest@g.com")
    settings = {
        "notifications": {
            "telegram": {"enabled": False},
            "email": {
                "enabled": True,
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
            },
        }
    }
    d = NotificationDispatcher.from_settings(settings)
    assert any(isinstance(n, EmailNotifier) for n in d.notifiers)


# ---------------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telegram_posts_correct_url():
    notifier = TelegramNotifier(bot_token="mytoken", chat_id="999")

    mock_response = AsyncMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    mock_response.status = 200

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.post = MagicMock(return_value=mock_response)

    with patch("src.notifier.telegram.aiohttp.ClientSession", return_value=mock_session):
        await notifier.send("subject", "body")

    call_args = mock_session.post.call_args
    assert "mytoken" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["chat_id"] == "999"
    assert "subject" in payload["text"]


# ---------------------------------------------------------------------------
# EmailNotifier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_calls_send_sync():
    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        username="u@example.com",
        password="pw",
        to_address="dest@example.com",
    )
    with patch.object(notifier, "_send_sync") as mock_sync:
        await notifier.send("Hello", "World")
        mock_sync.assert_called_once_with("Hello", "World")
