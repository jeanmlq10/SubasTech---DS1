from django.contrib import admin

from .models import Category, Service, ServicePhoto, TechnicianAvailability, TechnicianProfile, Zone

admin.site.register(Category)
admin.site.register(Zone)
admin.site.register(TechnicianProfile)
admin.site.register(Service)
admin.site.register(TechnicianAvailability)
admin.site.register(ServicePhoto)
