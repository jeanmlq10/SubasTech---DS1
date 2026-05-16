from django.core.management.base import BaseCommand

from catalog.models import Category, Zone


CATEGORIES = [
    {
        "name": "Electrician",
        "slug": "electrician",
        "description": "Electrical installations, outages, breakers, outlets and urgent home electrical repairs.",
    },
    {
        "name": "Plumber",
        "slug": "plumber",
        "description": "Leaks, pipes, faucets, toilets, bathrooms and kitchen plumbing repairs.",
    },
    {
        "name": "Appliance Repair",
        "slug": "appliance-repair",
        "description": "Repair for washers, refrigerators, stoves, air conditioners and home appliances.",
    },
    {
        "name": "Locksmith",
        "slug": "locksmith",
        "description": "Door locks, keys, lockouts and residential locksmith services.",
    },
    {
        "name": "HVAC Technician",
        "slug": "hvac-technician",
        "description": "Air conditioning maintenance, installation, cleaning and diagnostics.",
    },
    {
        "name": "General Handyman",
        "slug": "general-handyman",
        "description": "Small home repairs, mounting, maintenance and general technical support.",
    },
]

ZONES = [
    {"name": "Riomar", "slug": "barranquilla-riomar", "city": "Barranquilla"},
    {"name": "Alto Prado", "slug": "barranquilla-alto-prado", "city": "Barranquilla"},
    {"name": "Norte Centro Historico", "slug": "barranquilla-norte-centro-historico", "city": "Barranquilla"},
    {"name": "El Prado", "slug": "barranquilla-el-prado", "city": "Barranquilla"},
    {"name": "Villa Santos", "slug": "barranquilla-villa-santos", "city": "Barranquilla"},
    {"name": "Ciudad Jardin", "slug": "barranquilla-ciudad-jardin", "city": "Barranquilla"},
    {"name": "Boston", "slug": "barranquilla-boston", "city": "Barranquilla"},
    {"name": "Soledad", "slug": "soledad", "city": "Soledad"},
]


class Command(BaseCommand):
    help = "Seed initial SubasTech service categories and coverage zones."

    def handle(self, *args, **options):
        category_count = 0
        zone_count = 0

        for category in CATEGORIES:
            _obj, created = Category.objects.update_or_create(
                slug=category["slug"],
                defaults={
                    "name": category["name"],
                    "description": category["description"],
                    "is_active": True,
                },
            )
            category_count += int(created)

        for zone in ZONES:
            _obj, created = Zone.objects.update_or_create(
                slug=zone["slug"],
                defaults={
                    "name": zone["name"],
                    "city": zone["city"],
                    "is_active": True,
                },
            )
            zone_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(CATEGORIES)} categories, {len(ZONES)} zones ({category_count + zone_count} new)."
            )
        )
