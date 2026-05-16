from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Zone(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    city = models.CharField(max_length=120, default="Barranquilla")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["city", "name"]
        unique_together = ["name", "city"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.city}-{self.name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name}, {self.city}"


class TechnicianProfile(models.Model):
    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        BUSY = "busy", "Busy"
        OFFLINE = "offline", "Offline"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="technician_profile")
    bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    availability_status = models.CharField(max_length=20, choices=AvailabilityStatus.choices, default=AvailabilityStatus.OFFLINE)
    response_time_minutes = models.PositiveIntegerField(default=60)
    completed_services = models.PositiveIntegerField(default=0)
    service_completion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    zones = models.ManyToManyField(Zone, related_name="technicians", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_verified", "user__first_name", "user__username"]

    def __str__(self) -> str:
        return self.user.get_full_name() or self.user.username


class Service(models.Model):
    technician = models.ForeignKey(TechnicianProfile, on_delete=models.CASCADE, related_name="services")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="services")
    title = models.CharField(max_length=160)
    description = models.TextField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__name", "title"]

    def __str__(self) -> str:
        return f"{self.title} - {self.technician}"


class TechnicianAvailability(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 1, "Monday"
        TUESDAY = 2, "Tuesday"
        WEDNESDAY = 3, "Wednesday"
        THURSDAY = 4, "Thursday"
        FRIDAY = 5, "Friday"
        SATURDAY = 6, "Saturday"
        SUNDAY = 7, "Sunday"

    technician = models.ForeignKey(TechnicianProfile, on_delete=models.CASCADE, related_name="availability_windows")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]


class ServicePhoto(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="service-photos/")
    caption = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
