import json
import os
from dataclasses import dataclass
from urllib import error, request


@dataclass(frozen=True)
class WhatsAppSendResult:
    sent: bool
    dry_run: bool
    payload: dict
    response: dict | None = None
    error: str | None = None


class WhatsAppCloudClient:
    def __init__(self):
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.api_version = os.getenv("WHATSAPP_API_VERSION", "v20.0")
        self.dry_run = os.getenv("WHATSAPP_DRY_RUN", "True").lower() == "true"

    def send_text(self, to: str, body: str) -> WhatsAppSendResult:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body[:4096]},
        }

        if self.dry_run or not self.access_token or not self.phone_number_id:
            return WhatsAppSendResult(sent=False, dry_run=True, payload=payload)

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        http_request = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=10) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            return WhatsAppSendResult(sent=True, dry_run=False, payload=payload, response=response_payload)
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            return WhatsAppSendResult(sent=False, dry_run=False, payload=payload, error=str(exc))
