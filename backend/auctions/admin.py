from django.contrib import admin

from .models import Auction, Bid


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "client", "category", "status", "source", "created_at")
    list_filter = ("status", "source", "category")
    search_fields = ("title", "description", "client__username", "client__email")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("id", "auction", "technician", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("auction__title", "technician__user__username", "technician__user__email")
