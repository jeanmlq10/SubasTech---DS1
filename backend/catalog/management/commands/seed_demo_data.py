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
    {"username": "demo_arbiter", "role": "arbiter", "email": "arbiter@subastech.demo", "first_name": "Arbiter", "last_name": "SubasTech"},
    {"username": "demo_client", "role": "client", "email": "client@subastech.demo", "first_name": "Camila", "last_name": "Cliente", "phone_number": "573001112233"},
    # Electricistas
    {"username": "tech_carlos", "role": "technician", "email": "carlos@subastech.demo", "first_name": "Carlos", "last_name": "Mendoza", "phone_number": "573002223344"},
    {"username": "tech_ana", "role": "technician", "email": "ana@subastech.demo", "first_name": "Ana", "last_name": "Torres", "phone_number": "573002223345"},
    {"username": "tech_roberto", "role": "technician", "email": "roberto@subastech.demo", "first_name": "Roberto", "last_name": "Silva", "phone_number": "573002223346"},
    # Plomeros
    {"username": "tech_maria", "role": "technician", "email": "maria@subastech.demo", "first_name": "Maria", "last_name": "Gonzalez", "phone_number": "573003334455"},
    {"username": "tech_pedro", "role": "technician", "email": "pedro@subastech.demo", "first_name": "Pedro", "last_name": "Ramirez", "phone_number": "573003334456"},
    {"username": "tech_lucia", "role": "technician", "email": "lucia@subastech.demo", "first_name": "Lucia", "last_name": "Herrera", "phone_number": "573003334457"},
    # Cerrajeros
    {"username": "tech_jorge", "role": "technician", "email": "jorge@subastech.demo", "first_name": "Jorge", "last_name": "Castro", "phone_number": "573004445566"},
    {"username": "tech_sofia", "role": "technician", "email": "sofia@subastech.demo", "first_name": "Sofia", "last_name": "Mendez", "phone_number": "573004445567"},
    {"username": "tech_andres", "role": "technician", "email": "andres@subastech.demo", "first_name": "Andres", "last_name": "Vargas", "phone_number": "573004445568"},
    # Mantenimiento general
    {"username": "tech_valentina", "role": "technician", "email": "valentina@subastech.demo", "first_name": "Valentina", "last_name": "Rios", "phone_number": "573005556677"},
    {"username": "tech_diego", "role": "technician", "email": "diego@subastech.demo", "first_name": "Diego", "last_name": "Morales", "phone_number": "573005556678"},
    {"username": "tech_camila", "role": "technician", "email": "camila@subastech.demo", "first_name": "Camila", "last_name": "Ortiz", "phone_number": "573005556679"},
    # Cobertura demo por localidad
    {"username": "tech_natalia", "role": "technician", "email": "natalia@subastech.demo", "first_name": "Natalia", "last_name": "Mejia", "phone_number": "573005556680"},
    {"username": "tech_felipe", "role": "technician", "email": "felipe@subastech.demo", "first_name": "Felipe", "last_name": "Ruiz", "phone_number": "573005556681"},
    {"username": "tech_oscar", "role": "technician", "email": "oscar@subastech.demo", "first_name": "Oscar", "last_name": "Acosta", "phone_number": "573005556682"},
    {"username": "tech_paola", "role": "technician", "email": "paola@subastech.demo", "first_name": "Paola", "last_name": "Suarez", "phone_number": "573005556683"},
]

TECHNICIANS = {
    # Riomar
    "tech_carlos": {
        "bio": "Electricista residencial con experiencia en urgencias, tableros y tomacorrientes.",
        "category": "electrician",
        "service": "Electricista urgente residencial",
        "description": "Diagnostico y reparacion de fallas electricas, breakers, tomacorrientes y cortos.",
        "base_price": 85000,
        "zones": ["barranquilla-riomar"],
        "response_time_minutes": 15,
        "service_completion_rate": 96,
        "rating": 5,
    },
    "tech_roberto": {
        "bio": "Electricista con experiencia en mantenimiento industrial y atencion de contingencias.",
        "category": "electrician",
        "service": "Electricista industrial",
        "description": "Mantenimiento y reparacion de sistemas electricos de mayor carga.",
        "base_price": 110000,
        "zones": ["barranquilla-villa-santos"],
        "response_time_minutes": 30,
        "service_completion_rate": 98,
        "rating": 5,
    },
    "tech_jorge": {
        "bio": "Cerrajero especialista en cerraduras de seguridad y automatizacion.",
        "category": "locksmith",
        "service": "Cerraduras de seguridad",
        "description": "Instalacion y reparacion de cerraduras, llaves y sistemas de acceso.",
        "base_price": 75000,
        "zones": ["barranquilla-riomar"],
        "response_time_minutes": 15,
        "service_completion_rate": 95,
        "rating": 5,
    },
    "tech_valentina": {
        "bio": "Tecnica de mantenimiento general con experiencia en reparaciones varias.",
        "category": "general-handyman",
        "service": "Mantenimiento general residencial",
        "description": "Reparaciones varias, montajes, mantenimiento preventivo y pequenos arreglos.",
        "base_price": 60000,
        "zones": ["barranquilla-riomar"],
        "response_time_minutes": 30,
        "service_completion_rate": 90,
        "rating": 4,
    },
    # Norte Centro Historico
    "tech_ana": {
        "bio": "Especialista en instalaciones electricas residenciales y comerciales.",
        "category": "electrician",
        "service": "Instalacion electrica comercial",
        "description": "Instalaciones, reparaciones y revision de sistemas electricos.",
        "base_price": 95000,
        "zones": ["barranquilla-alto-prado"],
        "response_time_minutes": 20,
        "service_completion_rate": 94,
        "rating": 5,
    },
    "tech_pedro": {
        "bio": "Tecnico en plomeria sanitaria y sistemas de agua caliente.",
        "category": "plumber",
        "service": "Agua caliente y calefaccion",
        "description": "Instalacion y reparacion de sistemas de agua caliente y calefaccion.",
        "base_price": 90000,
        "zones": ["barranquilla-alto-prado"],
        "response_time_minutes": 25,
        "service_completion_rate": 89,
        "rating": 4,
    },
    "tech_sofia": {
        "bio": "Cerrajera con experiencia en cerraduras inteligentes y acceso biometrico.",
        "category": "locksmith",
        "service": "Cerraduras inteligentes",
        "description": "Instalacion de cerraduras inteligentes, biometricas y sistemas modernos.",
        "base_price": 120000,
        "zones": ["barranquilla-alto-prado"],
        "response_time_minutes": 25,
        "service_completion_rate": 97,
        "rating": 5,
    },
    "tech_diego": {
        "bio": "Tecnico mantenedor especializado en reparaciones de inmuebles.",
        "category": "general-handyman",
        "service": "Reparaciones y mantenimiento",
        "description": "Reparaciones estructurales, pintura, carpinteria y mantenimiento general.",
        "base_price": 70000,
        "zones": ["barranquilla-el-prado"],
        "response_time_minutes": 35,
        "service_completion_rate": 88,
        "rating": 4,
    },
    # Metropolitana
    "tech_maria": {
        "bio": "Plomera especializada en fugas, destapes y reparaciones de tuberias.",
        "category": "plumber",
        "service": "Plomeria y fugas residenciales",
        "description": "Atencion de fugas, destapes, banos, lavaplatos y reparaciones de tuberia.",
        "base_price": 70000,
        "zones": ["barranquilla-buenos-aires"],
        "response_time_minutes": 20,
        "service_completion_rate": 92,
        "rating": 4,
    },
    "tech_natalia": {
        "bio": "Tecnica de linea blanca con experiencia en diagnostico y reparacion en sitio.",
        "category": "appliance-repair",
        "service": "Reparacion de electrodomesticos",
        "description": "Revision y reparacion de neveras, lavadoras, estufas y pequenos electrodomesticos.",
        "base_price": 90000,
        "zones": ["barranquilla-buenos-aires"],
        "response_time_minutes": 25,
        "service_completion_rate": 93,
        "rating": 5,
    },
    # Suroriente
    "tech_lucia": {
        "bio": "Plomera experta en sistemas de drenaje y tratamiento de agua.",
        "category": "plumber",
        "service": "Sistemas de drenaje",
        "description": "Diseno e instalacion de sistemas de drenaje y tratamiento de aguas.",
        "base_price": 100000,
        "zones": ["barranquilla-la-luz"],
        "response_time_minutes": 30,
        "service_completion_rate": 91,
        "rating": 4,
    },
    "tech_felipe": {
        "bio": "Tecnico HVAC especializado en mantenimiento e instalacion de aire acondicionado.",
        "category": "hvac-technician",
        "service": "Aire acondicionado residencial",
        "description": "Mantenimiento preventivo, limpieza profunda y diagnostico de equipos de aire acondicionado.",
        "base_price": 105000,
        "zones": ["barranquilla-la-luz"],
        "response_time_minutes": 35,
        "service_completion_rate": 92,
        "rating": 5,
    },
    # Suroccidente
    "tech_andres": {
        "bio": "Cerrajero urgente disponible para emergencias de cerraduras.",
        "category": "locksmith",
        "service": "Cerrajeria urgente 24/7",
        "description": "Servicio de emergencia para cerraduras, puertas atascadas y llaves perdidas.",
        "base_price": 85000,
        "zones": ["barranquilla-la-pradera"],
        "response_time_minutes": 10,
        "service_completion_rate": 100,
        "rating": 5,
    },
    "tech_oscar": {
        "bio": "Maestro de obra y mantenimiento con experiencia en arreglos del hogar por demanda.",
        "category": "general-handyman",
        "service": "Mantenimiento locativo express",
        "description": "Ajustes locativos, resanes, pintura puntual y reparaciones varias en vivienda.",
        "base_price": 68000,
        "zones": ["barranquilla-la-pradera"],
        "response_time_minutes": 30,
        "service_completion_rate": 89,
        "rating": 4,
    },
    # Soledad
    "tech_camila": {
        "bio": "Tecnica de multiservicios para carpinteria, pintura y reparaciones variadas.",
        "category": "general-handyman",
        "service": "Multiservicios del hogar",
        "description": "Carpinteria, pintura, cortinas, estanterias y reparaciones de multiples tipos.",
        "base_price": 75000,
        "zones": ["soledad"],
        "response_time_minutes": 40,
        "service_completion_rate": 86,
        "rating": 4,
    },
    "tech_paola": {
        "bio": "Plomera residencial para fugas, griferia y mantenimientos preventivos en Soledad.",
        "category": "plumber",
        "service": "Plomeria residencial Soledad",
        "description": "Atencion de fugas, cambios de griferia, sanitarios y reparaciones hidraulicas.",
        "base_price": 72000,
        "zones": ["soledad"],
        "response_time_minutes": 20,
        "service_completion_rate": 94,
        "rating": 5,
    },
}

AVAILABILITIES = {
    "tech_carlos": [
        {"weekday": 1, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
    "tech_ana": [
        {"weekday": 1, "start_time": time(14, 0), "end_time": time(18, 0)},
    ],
    "tech_roberto": [
        {"weekday": 2, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
    "tech_maria": [
        {"weekday": 2, "start_time": time(14, 0), "end_time": time(18, 0)},
    ],
    "tech_pedro": [
        {"weekday": 2, "start_time": time(10, 0), "end_time": time(13, 0)},
    ],
    "tech_lucia": [
        {"weekday": 3, "start_time": time(14, 0), "end_time": time(18, 0)},
    ],
    "tech_jorge": [
        {"weekday": 3, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
    "tech_sofia": [
        {"weekday": 3, "start_time": time(8, 0), "end_time": time(11, 0)},
    ],
    "tech_andres": [
        {"weekday": 4, "start_time": time(14, 0), "end_time": time(18, 0)},
    ],
    "tech_valentina": [
        {"weekday": 4, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
    "tech_camila": [
        {"weekday": 4, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
    "tech_diego": [
        {"weekday": 5, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
    "tech_natalia": [
        {"weekday": 5, "start_time": time(14, 0), "end_time": time(18, 0)},
    ],
    "tech_felipe": [
        {"weekday": 6, "start_time": time(9, 0), "end_time": time(12, 0)},
    ],
    "tech_oscar": [
        {"weekday": 6, "start_time": time(14, 0), "end_time": time(18, 0)},
    ],
    "tech_paola": [
        {"weekday": 7, "start_time": time(9, 0), "end_time": time(12, 0)},
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
                defaults={"score": score, "comment": "Servicio demo para presentacion SubasTech."},
            )

    def _seed_leads(self, users, services):
        lead_data = [
            ("tech_carlos", "573001112233", "Necesito un electricista urgente en Riomar", "electrician", "Riomar", "high"),
            ("tech_ana", "573005556677", "Necesito revisar un corto en Alto Prado", "electrician", "Alto Prado", "high"),
            ("tech_natalia", "573006667788", "La nevera dejo de enfriar en Buenos Aires", "appliance-repair", "Buenos Aires", "normal"),
            ("tech_felipe", "573007778899", "Necesito mantenimiento del aire en La Luz", "hvac-technician", "La Luz", "normal"),
            ("tech_oscar", "573008889900", "Busco mantenimiento locativo en La Pradera", "general-handyman", "La Pradera", "normal"),
            ("tech_paola", "573009990011", "Tengo una fuga de agua en Soledad", "plumber", "Soledad", "high"),
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
                "description": "El mantenimiento fue incompleto y quedo pendiente la pintura de la sala.",
                "ai_summary": "Cliente reporta que el servicio de mantenimiento quedo incompleto.",
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
