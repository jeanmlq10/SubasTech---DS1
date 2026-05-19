from dataclasses import dataclass

import requests
from django.conf import settings


@dataclass(frozen=True)
class TelegramSendResult:
    sent: bool
    dry_run: bool
    payload: dict
    response: dict | None = None
    error: str | None = None


class TelegramBotClient:
    def __init__(self):
        self.bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        self.dry_run = getattr(settings, "TELEGRAM_DRY_RUN", True)

    def send_message(self, payload: dict) -> TelegramSendResult:
        if self.dry_run or not self.bot_token:
            return TelegramSendResult(sent=False, dry_run=True, payload=payload)

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return TelegramSendResult(
                sent=True,
                dry_run=False,
                payload=payload,
                response=response.json(),
            )
        except requests.RequestException as exc:
            return TelegramSendResult(
                sent=False,
                dry_run=False,
                payload=payload,
                error=str(exc),
            )
