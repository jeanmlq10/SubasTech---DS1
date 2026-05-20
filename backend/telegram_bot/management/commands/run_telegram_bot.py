import time
import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram_bot.views import _process_chat_message, send_telegram_message

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Corre el bot de Telegram en modo polling"

    def handle(self, *args, **kwargs):
        token = settings.TELEGRAM_BOT_TOKEN
        offset = self._skip_pending_updates(token)
        self.stdout.write("Bot corriendo... Presiona Ctrl+C para detener.")
        while True:
            try:
                updates = requests.get(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                    timeout=35
                ).json()
                for update in updates.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")
                    message_id = message.get("message_id")
                    if chat_id and text:
                        _session, _intent, reply, processed = _process_chat_message(
                            int(chat_id),
                            text,
                            telegram_message_id=message_id,
                        )
                        if processed:
                            send_telegram_message(chat_id, reply)
            except Exception as e:
                logger.error(f"Error en polling: {e}")
                time.sleep(5)

    def _skip_pending_updates(self, token: str) -> int:
        """
        Ignore stale backlog on startup so a restarted polling worker does not
        replay old Telegram updates and send repeated bot messages.
        """
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"timeout": 1},
                timeout=5,
            ).json()
        except Exception as exc:
            logger.warning("No se pudo consultar backlog inicial de Telegram: %s", exc)
            return 0

        results = response.get("result", [])
        if not results:
            return 0

        latest_update_id = max(update["update_id"] for update in results)
        logger.info("Saltando %s update(s) pendientes y retomando desde %s.", len(results), latest_update_id + 1)
        return latest_update_id + 1
