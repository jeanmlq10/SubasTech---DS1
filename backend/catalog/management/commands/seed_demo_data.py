from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from catalog.models import Category, Service, TechnicianProfile, Zone
from disputes.models import Dispute
from leads.models import ServiceLead
from reputation.models import Rating

DEMO_PASSWORD = "Subastech123!"

USERS = [
    {"username": "demo_admin", "role": "admin", "email": "admin@subastech.demo", "first_name": "Admin", "last_name": "SubasTech"},
    {"username": "demo_arbiter", "role": "arbiter", "email": "arbiter@subastech.demo", "first_name": "Ana", "last_name": "Arbitro"},
    {"username": "demo_client", "role": "client", "email": "client@subastech.demo", "first_name": "Camila", "last_name": "Cliente", "phone_number": "573001112233"},
    {"username": "tech_carlos", "role": "technician", "email": "carlos@subastech.demo", "first_name": "Carlos", "last_name": "Mendoza", "phone_number": "573002223344"},
    {"username": "tech_laura", "role": "technician", "email": "laura@subastech.demo", "first_name": "Laura", "last_name": "Perez", "phone_number": "573003334455"},
    {"username": "tech_miguel", "role": "technician", "email": "miguel@subastech.demo", "first_name": "Miguel", "last_name": "Rojas", "phone_number": "573004445566"},
]

TECHNICIANS = {
    "tech_carlos": {
        "bio": "Electricista residencial con experiencia en urgencias, tableros y tomacorrientes.",
        "category": "electrician",
        "service": "Electricista urgente residencial",
        "description": "Diagnostico y reparacion de fallas electricas, breakers, tomacorrientes y cortos.",
        "base_price": 85000,
        "zones": ["barranquilla-riomar", "barranquilla-alto-prado"],
        "response_time_minutes": 15,
        "service_completion_rate": 96,
        "rating": 5,
    },
    "tech_laura": {
        "bio": "Tecnica en electrodomesticos y aires acondicionados para hogares.",
        "category": "appliance-repair",
        "service": "Reparacion de lavadoras y neveras",
        "description": "Diagnostico, mantenimiento y reparacion de electrodomesticos de uso domestico.",
        "base_price": 95000,
        "zones": ["barranquilla-villa-santos", "barranquilla-riomar"],
        "response_time_minutes": 30,
        "service_completion_rate": 91,
        "rating": 4,
    },
    "tech_miguel": {
        "bio": "Plomero para fugas, banos, griferia y tuberias.",
        "category": "plumber",
        "service": "Plomeria y fugas residenciales",
        "description": "Atencion de fugas, destapes, banos, lavaplatos y reparaciones de tuberia.",
        "base_price": 70000,
        "zones": ["barranquilla-boston", "barranquilla-ciudad-jardin"],
        "response_time_minutes": 25,
        "service_completion_rate": 88,
        "rating": 4,
    },
}


class Command(BaseCommand):
    help = "Seed demo users and data for presenting SubasTech end-to-end."

    def handle(self, *args, **options):
        call_command("seed_initial_data")
        user_model = get_user_model()
        users = self._seed_users(user_model)
        services = self._seed_technicians(users)
        self._seed_ratings(users, services)
        self._seed_leads(users, services)
        self._seed_disputes(users, services)
        self._print_credentials()

    def _seed_users(self, user_model):
        users = {}
        for data in USERS:
            defaults = {
                "role": data["role"],
                "email": data["email"],
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "phone_number": data.get("phone_number", ""),
                "is_active": True,
            }
            if data["role"] == "admin":
                defaults["is_staff"] = True
            user, _created = user_model.objects.update_or_create(username=data["username"], defaults=defaults)
            user.set_password(DEMO_PASSWORD)
            user.save()
            users[data["username"]] = user
        return users

    def _seed_technicians(self, users):
        services = {}
        for username, data in TECHNICIANS.items():
            profile, _created = TechnicianProfile.objects.update_or_create(
                user=users[username],
                defaults={
                    "bio": data["bio"],
                    "is_verified": True,
                    "availability_status": TechnicianProfile.AvailabilityStatus.AVAILABLE,
                    "response_time_minutes": data["response_time_minutes"],
                    "completed_services": 24,
                    "service_completion_rate": data["service_completion_rate"],
                },
            )
            profile.zones.set(Zone.objects.filter(slug__in=data["zones"]))
            category = Category.objects.get(slug=data["category"])
            service, _created = Service.objects.update_or_create(
                technician=profile,
                title=data["service"],
                defaults={
                    "category": category,
                    "description": data["description"],
                    "base_price": data["base_price"],
                    "is_active": True,
                },
            )
            services[username] = service
        return services

    def _seed_ratings(self, users, services):
        client = users["demo_client"]
        for username, service in services.items():
            score = TECHNICIANS[username]["rating"]
            Rating.objects.update_or_create(
                technician=service.technician,
                client=client,
                service=service,
                defaults={"score": score, "comment": "Servicio demo para presentacion SubasTech."},
            )

    def _seed_leads(self, users, services):
        lead_data = [
            ("tech_carlos", "573001112233", "Necesito un electricista urgente en Riomar", "electrician", "riomar", "high"),
            ("tech_laura", "573005556677", "Mi lavadora no centrifuga en Villa Santos", "appliance-repair", "villa santos", "normal"),
            ("tech_miguel", "573006667788", "Tengo una fuga de agua en Boston", "plumber", "boston", "high"),
        ]
        for username, phone, message, category, location, urgency in lead_data:
            service = services[username]
            ServiceLead.objects.update_or_create(
                technician=service.technician,
                service=service,
                client_phone=phone,
                message=message,
                defaults={
                    "client_name": "Cliente demo",
                    "category": category,
                    "location": location,
                    "urgency": urgency,
                    "status": ServiceLead.Status.NEW,
                    "metadata": {"demo": True},
                },
            )

    def _seed_disputes(self, users, services):
        Dispute.objects.update_or_create(
            client=users["demo_client"],
            technician=services["tech_laura"].technician,
            service=services["tech_laura"],
            title="Servicio incompleto en electrodomestico",
            defaults={
                "description": "La lavadora quedo con el mismo fallo despues de la visita y necesito revision del caso.",
                "ai_summary": "Cliente reporta que la lavadora mantiene el fallo despues del servicio.",
                "priority": "high",
                "status": Dispute.Status.OPEN,
                "decision": Dispute.Decision.PENDING,
            },
        )

    def _print_credentials(self):
        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("Password for all demo users: Subastech123!")
        for data in USERS:
            self.stdout.write(f"- {data['username']} ({data['role']})")
