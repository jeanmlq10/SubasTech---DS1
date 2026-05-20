from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction

from appointments.models import Appointment
from appointments.services import create_appointment
from audit.models import AuditEvent
from audit.services import log_audit_event
from leads.models import ServiceLead

from .models import Auction, Bid


def award_auction_bid(*, auction: Auction, bid: Bid, actor, source: str = "auction_award"):
    if auction.status != Auction.Status.OPEN:
        raise ValidationError({"status": "Only open auctions can be awarded."})
    if bid.auction_id != auction.id:
        raise ValidationError({"bid_id": "The selected bid does not belong to this auction."})
    if bid.status != Bid.Status.PENDING:
        raise ValidationError({"bid_id": "Only pending bids can be awarded."})

    appointment = None
    with transaction.atomic():
        Bid.objects.filter(auction=auction, status=Bid.Status.PENDING).exclude(pk=bid.pk).update(status=Bid.Status.REJECTED)
        bid.status = Bid.Status.ACCEPTED
        bid.save(update_fields=["status", "updated_at"])
        auction.status = Auction.Status.AWARDED
        auction.winning_bid = bid
        auction.save(update_fields=["status", "winning_bid", "updated_at"])
        lead = ServiceLead.objects.create(
            technician=bid.technician,
            client_user=auction.client,
            service=bid.service,
            client_name=auction.client.get_full_name() or auction.client.username,
            client_phone=auction.client.phone_number or "",
            message=auction.description,
            category=auction.category.name,
            location=auction.location or (str(auction.zone) if auction.zone_id else ""),
            urgency=auction.urgency,
            source=ServiceLead.Source.TELEGRAM if auction.source == Auction.Source.TELEGRAM else ServiceLead.Source.DASHBOARD,
            status=ServiceLead.Status.ACCEPTED,
            metadata={
                "auction_id": auction.id,
                "bid_id": bid.id,
                "amount": str(bid.amount),
                "source": source,
            },
        )
        if bid.available_from is not None:
            appointment = create_appointment(
                client=auction.client,
                technician=bid.technician,
                service=bid.service,
                lead=lead,
                scheduled_start=bid.available_from,
                scheduled_end=bid.available_from + timedelta(minutes=bid.estimated_minutes),
                status=Appointment.Status.CONFIRMED,
                metadata={
                    "source": source,
                    "auction_id": auction.id,
                    "bid_id": bid.id,
                    "client_address": (auction.metadata or {}).get("client_address") or getattr(auction.client, "address", "") or auction.location,
                    "request_text": auction.description,
                },
                actor=actor,
                skip_availability_check=True,
            )
            lead.metadata = {**lead.metadata, "appointment_id": appointment.id}
            lead.save(update_fields=["metadata", "updated_at"])

    log_audit_event(
        event_type=AuditEvent.EventType.LEAD_STATUS_CHANGED,
        actor=actor,
        source=source,
        entity_type="auction",
        entity_id=auction.id,
        status="success",
        message="Auction awarded and lead created",
        metadata={"bid_id": bid.id, "lead_id": lead.id, "technician_id": bid.technician_id},
    )
    return lead, appointment
