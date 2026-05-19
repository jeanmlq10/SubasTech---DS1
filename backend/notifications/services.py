from .models import Notification
from .templates import MESSAGE_TEMPLATES


def render_notification_template(template_name: str, context: dict | None = None) -> dict:
    if template_name not in MESSAGE_TEMPLATES:
        raise KeyError(f"Unknown notification template: {template_name}")
    return MESSAGE_TEMPLATES[template_name](context or {})


def create_notification(
    *,
    user,
    title: str | None = None,
    message: str | None = None,
    channel: str = Notification.Channel.DASHBOARD,
    metadata: dict | None = None,
    template_name: str | None = None,
    context: dict | None = None,
) -> Notification:
    if template_name:
        rendered = render_notification_template(template_name, context=context)
        title = rendered["title"]
        message = rendered["message"]
    if not title or not message:
        raise ValueError("Notification title and message are required.")
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        channel=channel,
        metadata=metadata or {},
    )


def build_telegram_message_payload(
    *,
    chat_id: int,
    text: str,
    preview_url: bool = False,
    buttons: list[dict] | None = None,
) -> dict:
    payload = {
        "chat_id": chat_id,
        "text": text[:4096],
        "disable_web_page_preview": not preview_url,
    }
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {
                        "text": button["text"],
                        "url": button["url"],
                    }
                ]
                for button in buttons
            ]
        }
    return payload
