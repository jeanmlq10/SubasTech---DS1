from django.contrib import admin

from .models import Penalty, Rating

admin.site.register(Rating)
admin.site.register(Penalty)
