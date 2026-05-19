import time
import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram_bot.views import extract_intent, handle_conversation, send_telegram_message

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Corre el bot de Telegram en modo polling"

    def handle(self, *args, **kwargs):
        token = settings.TELEGRAM_BOT_TOKEN
        offset = 0
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
                    if chat_id and text:
                        intent = extract_intent(text)
                        reply = handle_conversation(chat_id, text, intent)
                        send_telegram_message(chat_id, reply)
            except Exception as e:
                logger.error(f"Error en polling: {e}")
                time.sleep(5)
