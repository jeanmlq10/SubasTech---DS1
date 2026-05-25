from django.core.management.base import BaseCommand
from django.utils import timezone

from auctions.models import Auction


class Command(BaseCommand):
    help = "Mark open auctions as expired when expires_at has passed."

    def handle(self, *args, **options):
        now = timezone.now()
        updated = Auction.objects.filter(
            status=Auction.Status.OPEN,
            expires_at__lt=now,
        ).update(status=Auction.Status.EXPIRED)
        self.stdout.write(self.style.SUCCESS(f"Expired {updated} auction(s)."))
