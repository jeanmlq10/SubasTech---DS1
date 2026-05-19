from datetime import time

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from catalog.models import Category, Service, TechnicianAvailability, TechnicianProfile, Zone
from disputes.models import Dispute
from leads.models import ServiceLead
from reputation.models import Rating

DEMO_PASSWORD = "Subastech123!"

USERS = [
    {"username": "demo_admin", "role": "admin", "email": "admin@subastech.demo", "first_name": "Admin", "last_name": "SubasTech"},
    {"username": "demo_client", "role": "client", "email": "client@subastech.demo", "first_name": "Camila", "last_name": "Cliente", "phone_number": "573001112233"},
    # Electricistas
    {"username": "tech_carlos", "role": "technician", "email": "carlos@subastech.demo", "first_name": "Carlos", "last_name": "Mendoza", "phone_number": "573002223344"},
    {"username": "tech_ana", "role": "technician", "email": "ana@subastech.demo", "first_name": "Ana", "last_name": "Torres", "phone_number": "573002223345"},
    {"username": "tech_roberto", "role": "technician", "email": "roberto@subastech.demo", "first_name": "Roberto", "last_name": "Silva", "phone_number": "573002223346"},
    # Plomeros
    {"username": "tech_maria", "role": "technician", "email": "maria@subastech.demo", "first_name": "María", "last_name": "González", "phone_number": "573003334455"},
    {"username": "tech_pedro", "role": "technician", "email": "pedro@subastech.demo", "first_name": "Pedro", "last_name": "Ramírez", "phone_number": "573003334456"},
    {"username": "tech_lucia", "role": "technician", "email": "lucia@subastech.demo", "first_name": "Lucía", "last_name": "Herrera", "phone_number": "573003334457"},
    # Cerrajeros
    {"username": "tech_jorge", "role": "technician", "email": "jorge@subastech.demo", "first_name": "Jorge", "last_name": "Castro", "phone_number": "573004445566"},
    {"username": "tech_sofia", "role": "technician", "email": "sofia@subastech.demo", "first_name": "Sofía", "last_name": "Mendez", "phone_number": "573004445567"},
    {"username": "tech_andres", "role": "technician", "email": "andres@subastech.demo", "first_name": "Andrés", "last_name": "Vargas", "phone_number": "573004445568"},
    # Mantenimiento General
    {"username": "tech_valentina", "role": "technician", "email": "valentina@subastech.demo", "first_name": "Valentina", "last_name": "Ríos", "phone_number": "573005556677"},
    {"username": "tech_diego", "role": "technician", "email": "diego@subastech.demo", "first_name": "Diego", "last_name": "Morales", "phone_number": "573005556678"},
    {"username": "tech_camila", "role": "technician", "email": "camila@subastech.demo", "first_name": "Camila", "last_name": "Ortiz", "phone_number": "573005556679"},
]

TECHNICIANS = {
    # Electricistas
    "tech_carlos": {
        "bio": "Electricista residencial con experiencia en urgencias, tableros y tomacorrientes.",
        "category": "electrician",
        "service": "Electricista urgente residencial",
        "description": "Diagnóstico y reparación de fallas eléctricas, breakers, tomacorrientes y cortos.",
        "base_price": 85000,
        "zones": ["barranquilla-riomar"],
        "response_time_minutes": 15,
        "service_completion_rate": 96,
        "rating": 5,
    },
    "tech_ana": {
        "bio": "Especialista en instalaciones eléctricas residenciales y comerciales.",
        "category": "electrician",
        "service": "Instalación eléctrica comercial",
        "description": "Instalaciones, reparaciones y revisión de sistemas eléctricos.",
        "base_price": 95000,
        "zones": ["barranquilla-alto-prado"],
        "response_time_minutes": 20,
        "service_completion_rate": 94,
        "rating": 5,
    },
    "tech_roberto": {
        "bio": "Electricista con 15 años de experiencia en mantenimiento industrial.",
        "category": "electrician",
        "service": "Electricista industrial",
        "description": "Mantenimiento y reparación de sistemas eléctricos de alta tensión.",
        "base_price": 110000,
        "zones": ["barranquilla-villa-santos"],
        "response_time_minutes": 30,
        "service_completion_rate": 98,
        "rating": 5,
    },
    # Plomeros
    "tech_maria": {
        "bio": "Plomera especializada en fugas, destapes y reparaciones de tuberías.",
        "category": "plumber",
        "service": "Plomería y fugas residenciales",
        "description": "Atención de fugas, destapes, baños, lavaplatos y reparaciones de tubería.",
        "base_price": 70000,
        "zones": ["barranquilla-riomar"],
        "response_time_minutes": 20,
        "service_completion_rate": 92,
        "rating": 4,
    },
    "tech_pedro": {
        "bio": "Técnico en plomería sanitaria y sistemas de agua caliente.",
        "category": "plumber",
        "service": "Agua caliente y calefacción",
        "description": "Instalación y reparación de sistemas de agua caliente y calefacción.",
        "base_price": 90000,
        "zones": ["barranquilla-alto-prado"],
        "response_time_minutes": 25,
        "service_completion_rate": 89,
        "rating": 4,
    },
    "tech_lucia": {
        "bio": "Plomera experta en sistemas de drenaje y tratamiento de agua.",
        "category": "plumber",
        "service": "Sistemas de drenaje",
        "description": "Diseño e instalación de sistemas de drenaje y tratamiento de aguas.",
        "base_price": 100000,
        "zones": ["barranquilla-villa-santos"],
        "response_time_minutes": 30,
        "service_completion_rate": 91,
        "rating": 4,
    },
    # Cerrajeros
    "tech_jorge": {
        "bio": "Cerrajero especialista en cerraduras de seguridad y automatización.",
        "category": "locksmith",
        "service": "Cerraduras de seguridad",
        "description": "Instalación y reparación de cerraduras, llaves y sistemas de acceso.",
        "base_price": 75000,
        "zones": ["barranquilla-riomar"],
        "response_time_minutes": 15,
        "service_completion_rate": 95,
        "rating": 5,
    },
    "tech_sofia": {
        "bio": "Cerrajera con experiencia en cerraduras inteligentes y acceso biométrico.",
        "category": "locksmith",
        "service": "Cerraduras inteligentes",
        "description": "Instalación de cerraduras inteligentes, biométricas y sistemas modernos.",
        "base_price": 120000,
        "zones": ["barranquilla-alto-prado"],
        "response_time_minutes": 25,
        "service_completion_rate": 97,
        "rating": 5,
    },
    "tech_andres": {
        "bio": "Cerrajero urgente disponible 24/7 para emergencias de cerraduras.",
        "category": "locksmith",
        "service": "Cerrajería urgente 24/7",
        "description": "Servicio de emergencia para cerraduras, puertas atascadas y llaves perdidas.",
        "base_price": 85000,
        "zones": ["barranquilla-villa-santos"],
        "response_time_minutes": 10,
        "service_completion_rate": 100,
        "rating": 5,
    },
    # Mantenimiento General
    "tech_valentina": {
        "bio": "Técnica de mantenimiento general con experiencia en reparaciones varias.",
        "category": "general-handyman",
        "service": "Mantenimiento general residencial",
        "description": "Reparaciones varias, montajes, mantenimiento preventivo y pequeños arreglos.",
        "base_price": 60000,
        "zones": ["barranquilla-riomar"],
        "response_time_minutes": 30,
        "service_completion_rate": 90,
        "rating": 4,
    },
    "tech_diego": {
        "bio": "Técnico mantenedor especializado en reparaciones de inmuebles.",
        "category": "general-handyman",
        "service": "Reparaciones y mantenimiento",
        "description": "Reparaciones estructurales, pintura, carpintería y mantenimiento general.",
        "base_price": 70000,
        "zones": ["barranquilla-alto-prado"],
        "response_time_minutes": 35,
        "service_completion_rate": 88,
        "rating": 4,
    },
    "tech_camila": {
        "bio": "Técnica de multiservicios: carpintería, pintura y reparaciones variadas.",
        "category": "general-handyman",
        "service": "Multiservicios del hogar",
        "description": "Carpintería, pintura, cortinas, estanterías y reparaciones de múltiples tipos.",
        "base_price": 75000,
        "zones": ["barranquilla-villa-santos"],
        "response_time_minutes": 40,
        "service_completion_rate": 86,
        "rating": 4,
    },
}

AVAILABILITIES = {
    "tech_carlos": [
        {"weekday": 1, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
    "tech_pedro": [
        {"weekday": 2, "start_time": time(10, 0), "end_time": time(13, 0)},
    ],
    "tech_sofia": [
        {"weekday": 3, "start_time": time(8, 0), "end_time": time(11, 0)},
    ],
    "tech_camila": [
        {"weekday": 4, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
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
            for availability in AVAILABILITIES.get(username, []):
                TechnicianAvailability.objects.update_or_create(
                    technician=profile,
                    weekday=availability["weekday"],
                    start_time=availability["start_time"],
                    end_time=availability["end_time"],
                    defaults={"is_active": True},
                )
            services[username] = service
        return services

    def _seed_ratings(self, users, services):
        client = users["demo_client"]
        for username, service in services.items():
            score = TECHNICIANS[username]["rating"]
            Rating.objects.update_or_create(
                author=client,
                technician=service.technician,
                service=service,
                target_role=Rating.TargetRole.TECHNICIAN,
                defaults={"score": score, "comment": "Servicio demo para presentación SubasTech."},
            )

    def _seed_leads(self, users, services):
        lead_data = [
            ("tech_carlos", "573001112233", "Necesito un electricista urgente en Riomar", "electrician", "Riomar", "high"),
            ("tech_maria", "573005556677", "Tengo una fuga de agua en Alto Prado", "plumber", "Alto Prado", "high"),
            ("tech_jorge", "573006667788", "Cerrajería urgente en Villa Santos", "locksmith", "Villa Santos", "high"),
        ]
        for username, phone, message, category, location, urgency in lead_data:
            service = services[username]
            ServiceLead.objects.update_or_create(
                technician=service.technician,
                service=service,
                client_phone=phone,
                message=message,
                defaults={
                    "client_user": users["demo_client"] if phone == users["demo_client"].phone_number else None,
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
            technician=services["tech_valentina"].technician,
            service=services["tech_valentina"],
            title="Servicio incompleto en mantenimiento",
            defaults={
                "description": "El mantenimiento fue incompleto y quedó pendiente la pintura de la sala.",
                "ai_summary": "Cliente reporta que el servicio de mantenimiento quedó incompleto.",
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