from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import User
from notifications.services import build_telegram_message_payload
from telegram_bot.client import TelegramBotClient

from .models import Auction, Bid
from .serializers import AuctionAwardSerializer, AuctionSerializer, BidSerializer
from .services import award_auction_bid


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
        if getattr(user, "auction_blocked", False) and not _is_admin(user):
            raise PermissionDenied("Tu cuenta tiene restringida la creación de subastas por disputas perdidas.")
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

        try:
            award_auction_bid(auction=auction, bid=bid, actor=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
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
            bid = serializer.save(technician=profile, status=Bid.Status.PENDING)
        except IntegrityError as exc:
            raise ValidationError({"auction": "You already created a bid for this auction."}) from exc
        _notify_telegram_auction_bid(bid)

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


def _notify_telegram_auction_bid(bid: Bid) -> None:
    auction = bid.auction
    chat_id = (auction.metadata or {}).get("chat_id")
    if auction.source != Auction.Source.TELEGRAM or not chat_id or auction.status != Auction.Status.OPEN:
        return

    technician_name = bid.technician.user.get_full_name() or bid.technician.user.username
    available_from = bid.available_from.strftime("%Y-%m-%d %H:%M") if bid.available_from else "Sin horario propuesto"
    message = (
        f"Nueva oferta para tu solicitud #{auction.id}\n\n"
        f"Tecnico: {technician_name}\n"
        f"Servicio: {bid.service.title if bid.service else 'Servicio tecnico'}\n"
        f"Precio: ${int(bid.amount):,}".replace(",", ".")
        + f"\nTiempo estimado: {bid.estimated_minutes} min\n"
        f"Horario propuesto: {available_from}\n\n"
        "Para aceptar esta oferta responde exactamente:\n"
        f"ACEPTO: {technician_name}"
    )
    TelegramBotClient().send_message(build_telegram_message_payload(chat_id=int(chat_id), text=message, preview_url=False))
