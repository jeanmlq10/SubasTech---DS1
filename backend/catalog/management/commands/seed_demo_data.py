from datetime import time

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Q

from appointments.models import Appointment
from auctions.models import Auction
from catalog.models import Category, Service, TechnicianAvailability, TechnicianProfile, Zone
from disputes.models import Dispute
from leads.models import ServiceLead
from notifications.models import Notification
from reputation.models import Penalty, Rating
from telegram_bot.models import ChatSession


DEMO_PASSWORD = "Subastech123!"

CORE_USERS = [
    {"username": "demo_admin", "role": "admin", "email": "admin@subastech.demo", "first_name": "Admin", "last_name": "SubasTech"},
    {"username": "demo_arbiter", "role": "arbiter", "email": "arbiter@subastech.demo", "first_name": "Arbiter", "last_name": "SubasTech"},
    {"username": "demo_client", "role": "client", "email": "client@subastech.demo", "first_name": "Camila", "last_name": "Cliente", "phone_number": "573001112233"},
]

TECHNICIAN_SPECS = [
    # Riomar: multiple direct options for Telegram recommendations.
    ("tech_carlos", "Carlos", "Mendoza", "electrician", "Electricista urgente residencial", "Urgencias electricas, breakers, tomacorrientes y cortos.", 85000, ["barranquilla-riomar"], 15),
    ("tech_daniel", "Daniel", "Ariza", "electrician", "Electricista residencial Riomar", "Instalaciones, diagnostico y reparacion electrica en vivienda.", 78000, ["barranquilla-riomar"], 20),
    ("tech_lina", "Lina", "Caballero", "electrician", "Revision electrica express", "Revision de tableros, puntos electricos y fallas intermitentes.", 82000, ["barranquilla-riomar"], 25),
    ("tech_jorge", "Jorge", "Castro", "locksmith", "Cerrajeria Riomar", "Apertura de puertas, cambio de guardas y cerraduras de seguridad.", 75000, ["barranquilla-riomar"], 18),
    ("tech_valentina", "Valentina", "Rios", "general-handyman", "Mantenimiento general Riomar", "Reparaciones locativas, instalaciones menores y mantenimiento preventivo.", 65000, ["barranquilla-riomar"], 30),
    ("tech_maria", "Maria", "Gonzalez", "plumber", "Plomeria Riomar", "Fugas, griferia, sanitarios y tuberias residenciales.", 72000, ["barranquilla-riomar"], 22),
    # Boston: at least two technicians in the same zone, including locksmith.
    ("tech_boston_ana", "Ana", "Torres", "electrician", "Electricista Boston", "Revision de cortos, acometidas internas y mantenimiento electrico.", 76000, ["barranquilla-boston"], 25),
    ("tech_boston_pedro", "Pedro", "Ramirez", "plumber", "Plomeria Boston", "Destapes, fugas y reparaciones hidraulicas en apartamentos.", 69000, ["barranquilla-boston"], 20),
    ("tech_boston_sofia", "Sofia", "Mendez", "locksmith", "Cerrajeria Boston", "Cerrajeria residencial, puertas trabadas y llaves perdidas.", 70000, ["barranquilla-boston"], 15),
    ("tech_boston_diego", "Diego", "Morales", "general-handyman", "Mantenimiento Boston", "Arreglos pequenos, montaje de accesorios y pintura puntual.", 64000, ["barranquilla-boston"], 35),
    # Villa Santos.
    ("tech_roberto", "Roberto", "Silva", "electrician", "Electricista industrial y residencial", "Mantenimiento electrico de media carga y reparaciones urgentes.", 110000, ["barranquilla-villa-santos"], 30),
    ("tech_villa_paula", "Paula", "Mejia", "electrician", "Instalaciones electricas Villa Santos", "Instalacion de luminarias, puntos electricos y tableros.", 90000, ["barranquilla-villa-santos"], 28),
    ("tech_villa_lucia", "Lucia", "Herrera", "plumber", "Plomeria Villa Santos", "Reparacion de fugas, lavaplatos, banos y tuberias.", 76000, ["barranquilla-villa-santos"], 24),
    ("tech_villa_oscar", "Oscar", "Acosta", "general-handyman", "Mantenimiento residencial Villa Santos", "Reparaciones generales, soportes, pintura y resanes.", 68000, ["barranquilla-villa-santos"], 32),
    # Prado and Alto Prado.
    ("tech_alto_ana", "Ana Maria", "Santos", "electrician", "Electricista Alto Prado", "Instalaciones comerciales y residenciales certificadas.", 95000, ["barranquilla-alto-prado"], 20),
    ("tech_alto_pedro", "Pedro Luis", "Navas", "plumber", "Agua caliente y plomeria Alto Prado", "Sistemas de agua caliente, griferia y reparaciones sanitarias.", 90000, ["barranquilla-alto-prado"], 25),
    ("tech_alto_sofia", "Sofia", "Herrera", "locksmith", "Cerraduras inteligentes Alto Prado", "Instalacion de cerraduras digitales y sistemas de acceso.", 120000, ["barranquilla-alto-prado"], 25),
    ("tech_alto_felipe", "Felipe", "Ruiz", "hvac-technician", "Aire acondicionado Alto Prado", "Mantenimiento preventivo y diagnostico de aire acondicionado.", 105000, ["barranquilla-alto-prado"], 35),
    ("tech_prado_diego", "Diego", "Morales", "general-handyman", "Reparaciones El Prado", "Carpinteria menor, pintura y mantenimiento locativo.", 70000, ["barranquilla-el-prado"], 35),
    ("tech_prado_camila", "Camila", "Ortiz", "appliance-repair", "Electrodomesticos El Prado", "Revision de lavadoras, neveras, estufas y linea blanca.", 92000, ["barranquilla-el-prado"], 28),
    ("tech_prado_andres", "Andres", "Vargas", "locksmith", "Cerrajero El Prado", "Apertura, cambio de cilindros y mantenimiento de cerraduras.", 73000, ["barranquilla-el-prado"], 18),
    # Rebolo and surrounding south-east tests.
    ("tech_rebolo_andres", "Andres", "Perez", "locksmith", "Cerrajeria urgente Rebolo", "Emergencias de cerraduras, puertas atascadas y cambios de llave.", 68000, ["barranquilla-rebolo"], 12),
    ("tech_rebolo_julian", "Julian", "Marin", "locksmith", "Cerraduras de seguridad Rebolo", "Instalacion de cerraduras, chapas y refuerzos de seguridad.", 72000, ["barranquilla-rebolo"], 18),
    ("tech_rebolo_lucia", "Lucia", "Fuentes", "plumber", "Plomeria Rebolo", "Fugas visibles, destapes, sanitarios y reparaciones hidraulicas.", 65000, ["barranquilla-rebolo"], 20),
    ("tech_rebolo_nestor", "Nestor", "Diaz", "electrician", "Electricista Rebolo", "Cortos, puntos electricos, acometidas internas y revisiones.", 70000, ["barranquilla-rebolo"], 22),
    # La Pradera.
    ("tech_pradera_oscar", "Oscar", "Acosta", "general-handyman", "Mantenimiento locativo La Pradera", "Ajustes locativos, resanes y reparaciones varias en vivienda.", 68000, ["barranquilla-la-pradera"], 30),
    ("tech_pradera_elena", "Elena", "Pardo", "plumber", "Plomeria La Pradera", "Cambios de griferia, fugas y revision de banos.", 69000, ["barranquilla-la-pradera"], 25),
    ("tech_pradera_mateo", "Mateo", "Cortes", "electrician", "Electricista La Pradera", "Revision electrica residencial y cambios de accesorios.", 72000, ["barranquilla-la-pradera"], 26),
    ("tech_pradera_natalia", "Natalia", "Mejia", "appliance-repair", "Electrodomesticos La Pradera", "Diagnostico y reparacion de lavadoras y neveras.", 85000, ["barranquilla-la-pradera"], 32),
    # Buenos Aires and La Luz.
    ("tech_baires_natalia", "Natalia", "Mejia", "appliance-repair", "Reparacion de electrodomesticos Buenos Aires", "Neveras, lavadoras, estufas y diagnostico en sitio.", 90000, ["barranquilla-buenos-aires"], 25),
    ("tech_baires_mario", "Mario", "Lopez", "plumber", "Plomeria Buenos Aires", "Fugas, destapes y reparaciones hidraulicas residenciales.", 70000, ["barranquilla-buenos-aires"], 20),
    ("tech_baires_ivan", "Ivan", "Salcedo", "electrician", "Electricista Buenos Aires", "Instalaciones y reparaciones electricas en casa.", 76000, ["barranquilla-buenos-aires"], 24),
    ("tech_laluz_felipe", "Felipe", "Ruiz", "hvac-technician", "Aire acondicionado La Luz", "Limpieza, mantenimiento y diagnostico de minisplits.", 105000, ["barranquilla-la-luz"], 35),
    ("tech_laluz_paola", "Paola", "Suarez", "plumber", "Plomeria La Luz", "Reparaciones hidraulicas, sanitarios y tuberias.", 72000, ["barranquilla-la-luz"], 20),
    ("tech_laluz_jorge", "Jorge", "Escobar", "general-handyman", "Mantenimiento La Luz", "Instalaciones menores y reparaciones generales.", 62000, ["barranquilla-la-luz"], 34),
    # Soledad.
    ("tech_soledad_camila", "Camila", "Ortiz", "general-handyman", "Multiservicios Soledad", "Carpinteria, pintura, cortinas y reparaciones del hogar.", 75000, ["soledad"], 40),
    ("tech_soledad_paola", "Paola", "Suarez", "plumber", "Plomeria residencial Soledad", "Fugas, griferia, sanitarios y mantenimientos preventivos.", 72000, ["soledad"], 20),
    ("tech_soledad_rafael", "Rafael", "Mora", "electrician", "Electricista Soledad", "Cortos, breakers, puntos electricos y luminarias.", 76000, ["soledad"], 28),
    ("tech_soledad_sara", "Sara", "Leon", "locksmith", "Cerrajeria Soledad", "Aperturas, cambios de guardas y cerraduras residenciales.", 68000, ["soledad"], 18),
]

TRADE_BY_CATEGORY = {
    "electrician": "electrician",
    "plumber": "plumber",
    "locksmith": "locksmith",
    "general-handyman": "general-handyman",
    "appliance-repair": "general-handyman",
    "hvac-technician": "general-handyman",
}

USERS = CORE_USERS + [
    {
        "username": username,
        "role": "technician",
        "email": f"{username}@subastech.demo",
        "first_name": first_name,
        "last_name": last_name,
        "phone_number": f"57310{index:06d}",
        "technician_trade": TRADE_BY_CATEGORY[category],
    }
    for index, (username, first_name, last_name, category, *_rest) in enumerate(TECHNICIAN_SPECS, start=200001)
]


def build_technicians() -> dict:
    technicians = {}
    for username, _first_name, _last_name, category, service, description, base_price, zones, response_minutes in TECHNICIAN_SPECS:
        technicians[username] = {
            "bio": f"{service}. Atencion demo para pruebas de SubasTech.",
            "category": category,
            "service": service,
            "description": description,
            "base_price": base_price,
            "zones": zones,
            "response_time_minutes": response_minutes,
        }
    return technicians


TECHNICIANS = build_technicians()


def build_availabilities() -> dict:
    availabilities = {}
    for index, (username, *_rest) in enumerate(TECHNICIAN_SPECS):
        weekday = (index % 7) + 1
        start_hour = 8 + (index % 5)
        availabilities[username] = [
            {"weekday": weekday, "start_time": time(start_hour, 0), "end_time": time(start_hour + 4, 0)}
        ]
    return availabilities


AVAILABILITIES = build_availabilities()


class Command(BaseCommand):
    help = "Seed clean demo users, technicians and services for SubasTech manual testing."

    def handle(self, *args, **options):
        call_command("seed_initial_data")
        user_model = get_user_model()
        users = self._seed_users(user_model)
        self._clear_demo_activity(users)
        self._seed_technicians(users)
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
                "technician_trade": data.get("technician_trade", ""),
                "is_active": True,
                "is_staff": data["role"] in {"admin", "arbiter"},
            }
            user, _created = user_model.objects.update_or_create(username=data["username"], defaults=defaults)
            user.set_password(DEMO_PASSWORD)
            user.save()
            users[data["username"]] = user
        return users

    def _clear_demo_activity(self, users):
        demo_users = list(users.values())
        demo_profiles = TechnicianProfile.objects.filter(user__in=demo_users)

        Appointment.objects.filter(Q(client__in=demo_users) | Q(technician__in=demo_profiles)).delete()
        ServiceLead.objects.filter(Q(client_user__in=demo_users) | Q(technician__in=demo_profiles)).delete()
        Dispute.objects.filter(Q(client__in=demo_users) | Q(technician__in=demo_profiles)).delete()
        Auction.objects.filter(client__in=demo_users).delete()
        Rating.objects.filter(Q(author__in=demo_users) | Q(client__in=demo_users) | Q(technician__in=demo_profiles)).delete()
        Penalty.objects.filter(technician__in=demo_profiles).delete()
        Notification.objects.filter(user__in=demo_users).delete()
        ChatSession.objects.filter(user__in=demo_users).delete()

    def _seed_technicians(self, users):
        for username, data in TECHNICIANS.items():
            profile, _created = TechnicianProfile.objects.update_or_create(
                user=users[username],
                defaults={
                    "bio": data["bio"],
                    "is_verified": True,
                    "availability_status": TechnicianProfile.AvailabilityStatus.AVAILABLE,
                    "response_time_minutes": data["response_time_minutes"],
                    "completed_services": 0,
                    "service_completion_rate": 0,
                },
            )
            profile.zones.set(Zone.objects.filter(slug__in=data["zones"]))
            category = Category.objects.get(slug=data["category"])
            Service.objects.update_or_create(
                technician=profile,
                title=data["service"],
                defaults={
                    "category": category,
                    "description": data["description"],
                    "base_price": data["base_price"],
                    "is_active": True,
                },
            )
            self._seed_availability(profile, username)

    def _seed_availability(self, profile, username):
        TechnicianAvailability.objects.filter(technician=profile).delete()
        for availability in AVAILABILITIES.get(username, []):
            TechnicianAvailability.objects.create(
                technician=profile,
                weekday=availability["weekday"],
                start_time=availability["start_time"],
                end_time=availability["end_time"],
                is_active=True,
            )

    def _print_credentials(self):
        self.stdout.write(self.style.SUCCESS("Clean demo data ready."))
        self.stdout.write("Password for all demo users: Subastech123!")
        self.stdout.write("Transactional demo data reset: auctions=0, bids=0, leads=0, appointments=0, disputes=0, ratings=0.")
        self.stdout.write(f"Technicians seeded: {len(TECHNICIANS)}")
        for data in USERS:
            self.stdout.write(f"- {data['username']} ({data['role']})")
