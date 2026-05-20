from django.contrib import admin

from .models import Category, Service, ServicePhoto, TechnicianAvailability, TechnicianDocument, TechnicianProfile, Zone

admin.site.register(Category)
admin.site.register(Zone)
admin.site.register(TechnicianProfile)
admin.site.register(TechnicianDocument)
admin.site.register(Service)
admin.site.register(TechnicianAvailability)
admin.site.register(ServicePhoto)
