from audit.models import AuditEvent


def log_audit_event(
    *,
    event_type: str,
    message: str,
    actor=None,
    channel: str = "",
    source: str = "",
    entity_type: str = "",
    entity_id: str | int = "",
    status: str = "info",
    metadata: dict | None = None,
) -> AuditEvent:
    return AuditEvent.objects.create(
        event_type=event_type,
        actor=actor,
        channel=channel,
        source=source,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id != "" else "",
        status=status,
        message=message[:255],
        metadata=metadata or {},
    )
