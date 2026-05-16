from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Rating(models.Model):
    technician = models.ForeignKey("catalog.TechnicianProfile", on_delete=models.CASCADE, related_name="ratings")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings_given")
    service = models.ForeignKey("catalog.Service", on_delete=models.SET_NULL, null=True, blank=True, related_name="ratings")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Penalty(models.Model):
    technician = models.ForeignKey("catalog.TechnicianProfile", on_delete=models.CASCADE, related_name="penalties")
    reason = models.CharField(max_length=180)
    points = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
