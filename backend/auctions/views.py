from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import User
from appointments.models import Appointment
from appointments.services import create_appointment
from audit.models import AuditEvent
from audit.services import log_audit_event
from leads.models import ServiceLead

from .models import Auction, Bid
from .serializers import AuctionAwardSerializer, AuctionSerializer, BidSerializer


def _is_admin(user):
    return user.is_staff or user.is_superuser or user.role == User.Role.ADMIN


class AuctionViewSet(viewsets.ModelViewSet):
    serializer_class = AuctionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Auction.objects.select_related("client", "category", "zone", "winning_bid")
            .prefetch_related("bids__technician__user", "bids__service")
            .distinct()
        )
        user = self.request.user
        if _is_admin(user):
            return queryset
        if user.role == User.Role.CLIENT:
            return queryset.filter(client=user)
        profile = getattr(user, "technician_profile", None)
        if profile:
            return queryset.filter(Q(status=Auction.Status.OPEN) | Q(bids__technician=profile)).distinct()
        return Auction.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != User.Role.CLIENT and not _is_admin(user):
            raise PermissionDenied("Only clients can create auctions.")
        serializer.save(client=user, source=Auction.Source.DASHBOARD, status=Auction.Status.OPEN)

    def perform_update(self, serializer):
        auction = serializer.instance
        user = self.request.user
        if not _is_admin(user) and auction.client_id != user.id:
            raise PermissionDenied("Only the auction owner can update it.")
        if auction.status != Auction.Status.OPEN:
            raise ValidationError({"status": "Only open auctions can be updated."})
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not _is_admin(user) and instance.client_id != user.id:
            raise PermissionDenied("Only the auction owner can delete it.")
        if instance.status != Auction.Status.OPEN:
            raise ValidationError({"status": "Only open auctions can be deleted."})
        instance.delete()

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        auction = self.get_object()
        if not _is_admin(request.user) and auction.client_id != request.user.id:
            raise PermissionDenied("Only the auction owner can cancel it.")
        if auction.status != Auction.Status.OPEN:
            raise ValidationError({"status": "Only open auctions can be cancelled."})

        auction.status = Auction.Status.CANCELLED
        auction.save(update_fields=["status", "updated_at"])
        auction.bids.filter(status=Bid.Status.PENDING).update(status=Bid.Status.REJECTED)
        return Response(AuctionSerializer(auction, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def award(self, request, pk=None):
        auction = self.get_object()
        if not _is_admin(request.user) and auction.client_id != request.user.id:
            raise PermissionDenied("Only the auction owner can award it.")
        if auction.status != Auction.Status.OPEN:
            raise ValidationError({"status": "Only open auctions can be awarded."})

        serializer = AuctionAwardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bid = serializer.validated_data["bid_id"]
        if bid.auction_id != auction.id:
            raise ValidationError({"bid_id": "The selected bid does not belong to this auction."})
        if bid.status != Bid.Status.PENDING:
            raise ValidationError({"bid_id": "Only pending bids can be awarded."})

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
                source=ServiceLead.Source.DASHBOARD,
                status=ServiceLead.Status.ACCEPTED,
                metadata={
                    "auction_id": auction.id,
                    "bid_id": bid.id,
                    "amount": str(bid.amount),
                    "source": "auction_award",
                },
            )
            if bid.available_from is not None:
                try:
                    appointment = create_appointment(
                        client=auction.client,
                        technician=bid.technician,
                        service=bid.service,
                        lead=lead,
                        scheduled_start=bid.available_from,
                        scheduled_end=bid.available_from + timedelta(minutes=bid.estimated_minutes),
                        status=Appointment.Status.CONFIRMED,
                        metadata={
                            "source": "auction_award",
                            "auction_id": auction.id,
                            "bid_id": bid.id,
                            "client_address": auction.location,
                            "request_text": auction.description,
                        },
                        actor=request.user,
                    )
                    lead.metadata = {**lead.metadata, "appointment_id": appointment.id}
                    lead.save(update_fields=["metadata", "updated_at"])
                except DjangoValidationError as exc:
                    raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc

        log_audit_event(
            event_type=AuditEvent.EventType.LEAD_STATUS_CHANGED,
            actor=request.user,
            source="auctions.award",
            entity_type="auction",
            entity_id=auction.id,
            status="success",
            message="Auction awarded and lead created",
            metadata={"bid_id": bid.id, "lead_id": lead.id, "technician_id": bid.technician_id},
        )
        return Response(AuctionSerializer(auction, context={"request": request}).data)


class BidViewSet(viewsets.ModelViewSet):
    serializer_class = BidSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Bid.objects.select_related("auction__client", "auction__category", "technician__user", "service")
        user = self.request.user
        if _is_admin(user):
            return queryset
        profile = getattr(user, "technician_profile", None)
        if profile:
            return queryset.filter(technician=profile)
        if user.role == User.Role.CLIENT:
            return queryset.filter(auction__client=user)
        return Bid.objects.none()

    def perform_create(self, serializer):
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile:
            raise PermissionDenied("Only technicians can create bids.")
        try:
            serializer.save(technician=profile, status=Bid.Status.PENDING)
        except IntegrityError as exc:
            raise ValidationError({"auction": "You already created a bid for this auction."}) from exc

    def perform_update(self, serializer):
        bid = serializer.instance
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile or bid.technician_id != profile.id:
            raise PermissionDenied("Only the bid owner can update it.")
        if bid.status != Bid.Status.PENDING:
            raise ValidationError({"status": "Only pending bids can be updated."})
        serializer.save()

    def perform_destroy(self, instance):
        profile = getattr(self.request.user, "technician_profile", None)
        if not profile or instance.technician_id != profile.id:
            raise PermissionDenied("Only the bid owner can delete it.")
        if instance.status != Bid.Status.PENDING:
            raise ValidationError({"status": "Only pending bids can be deleted."})
        instance.delete()

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        bid = self.get_object()
        profile = getattr(request.user, "technician_profile", None)
        if not profile or bid.technician_id != profile.id:
            raise PermissionDenied("Only the bid owner can withdraw it.")
        if bid.status != Bid.Status.PENDING:
            raise ValidationError({"status": "Only pending bids can be withdrawn."})
        bid.status = Bid.Status.WITHDRAWN
        bid.save(update_fields=["status", "updated_at"])
        return Response(BidSerializer(bid, context={"request": request}).data, status=status.HTTP_200_OK)
