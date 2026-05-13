from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class Notifier(Protocol):
    async def send(self, subject: str, body: str) -> None:
        ...
