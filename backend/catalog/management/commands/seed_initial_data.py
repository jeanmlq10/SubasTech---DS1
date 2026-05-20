from django.core.management.base import BaseCommand
from django.utils.text import slugify

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

def zone(name: str, city: str = "Barranquilla", slug: str | None = None) -> dict:
    return {"name": name, "slug": slug or slugify(f"{city}-{name}"), "city": city}


# Official neighborhood lists by Barranquilla locality, sourced from the
# Alcaldia de Barranquilla public locality pages.
NORTE_CENTRO_HISTORICO_ZONES = [
    "Abajo",
    "Alameda del Rio",
    "Alto Prado",
    "Altos del Prado",
    "America",
    "Barlovento",
    "Bellavista",
    "Bethania",
    "Boston",
    "Campo Alegre",
    "Centro",
    "Ciudad Jardin",
    "Colombia",
    "El Castillo",
    "El Golf",
    "El Porvenir",
    "El Prado",
    "El Recreo",
    "El Rosario",
    "El Tabor",
    "Granadillo",
    "La Campina",
    "La Concepcion",
    "La Cumbre",
    "La Loma",
    "Las Delicias",
    "Las Mercedes",
    "Las Nubes",
    "Los Alpes",
    "Los Jobos",
    "Los Nogales",
    "Miramar",
    "Modelo",
    "Montecristo",
    "Nuevo Horizonte",
    "Paraiso",
    "San Francisco",
    "Santa Ana",
    "Villa Country",
    "Villanueva",
    "Zona Franca",
    "Zona Industrial",
]

RIOMAR_ZONES = [
    "Riomar",
    "Las Tres Ave Maria",
    "Altamira",
    "Altos de Riomar",
    "San Salvador",
    "Altos del Limon",
    "San Vicente",
    "Andalucia",
    "Santa Monica",
    "Corregimiento Eduardo Santos",
    "La Playa",
    "Siape",
    "El Limoncito",
    "Solaire Norte",
    "El Poblado",
    "Villa Campestre",
    "La Floresta",
    "Villa Carolina",
    "Las Flores",
    "Villa del Este",
    "Villa Santos",
]

METROPOLITANA_ZONES = [
    "Buenos Aires",
    "Carrizal",
    "Cevillar",
    "Ciudadela 20 de Julio",
    "El Santuario",
    "Kennedy",
    "La Sierra",
    "La Sierrita",
    "Las Americas",
    "Las Cayenas",
    "Las Gardenias",
    "Las Granjas",
    "Los Continentes",
    "Los Girasoles",
    "San Luis",
    "Santa Maria",
    "Santo Domingo de Guzman",
    "Sevilla Real",
    "Siete de Abril",
    "Sinai",
    "Veinte de Julio",
    "Villa San Carlos",
    "Villa San Pedro",
    "Villa Sevilla",
    "Villa Valery",
]

SURORIENTE_ZONES = [
    "Atlantico",
    "Bellarena",
    "Boyaca",
    "Chiquinquira",
    "El Campito",
    "El Limon",
    "El Milagro",
    "Primero de Mayo",
    "El Ferry",
    "El Parque Sector Barranquilla",
    "Jose Antonio Galan",
    "La Arboraya",
    "La Chinita",
    "La Luz",
    "La Magdalena",
    "La Union",
    "La Victoria",
    "Las Dunas",
    "Las Nieves",
    "Las Palmas",
    "Las Palmeras",
    "Los Laureles",
    "Los Trupillos",
    "Moderno",
    "Montes",
    "Pasadena",
    "Rebolo",
    "San Jose",
    "San Nicolas",
    "San Roque",
    "Santa Helena",
    "Simon Bolivar",
    "Tayrona",
    "Universal I",
    "Universal II",
    "Villa Blanca",
    "Villa del Carmen",
]

SUROCCIDENTE_ZONES = [
    "Alfonso Lopez",
    "Bernardo Hoyos",
    "Buena Esperanza",
    "California",
    "Caribe Verde",
    "Carlos Meisel",
    "Ciudad Modesto",
    "Ciudadela de la Salud",
    "Ciudadela de Paz",
    "Colina Campestre",
    "Cordialidad",
    "Corregimiento de Juan Mina",
    "Cuchilla de Villate",
    "El Bosque",
    "El Carmen",
    "El Eden",
    "El Pueblo",
    "El Romance",
    "El Rubi",
    "El Silencio",
    "El Valle",
    "Evaristo Sourdis",
    "Gerlein y Villate",
    "Kalamary",
    "La Ceiba",
    "La Esmeralda",
    "La Florida",
    "La Gloria",
    "La Libertad",
    "La Manga",
    "La Paz",
    "La Pradera",
    "Las Colinas",
    "Las Estrellas",
    "Las Malvinas",
    "Las Terrazas",
    "Lipaya",
    "Loma Fresca",
    "Los Andes",
    "Los Angeles I",
    "Los Angeles II",
    "Los Angeles III",
    "Los Olivos I",
    "Los Olivos II",
    "Los Pinos",
    "Los Rosales",
    "Lucero",
    "Me Quejo",
    "Mercedes Sur",
    "Nueva Colombia",
    "Nueva Granada",
    "Olaya",
    "Pinar del Rio",
    "Por Fin",
    "Pumarejo",
    "San Felipe",
    "San Isidro",
    "San Pedro Alejandrino",
    "San Pedro Sector I",
    "Santo Domingo",
    "Siete de Agosto",
    "Villa del Rosario",
    "Villa Flor",
    "Villas de la Cordialidad",
    "Villas de San Pablo",
]

ZONES = [
    *(zone(name) for name in NORTE_CENTRO_HISTORICO_ZONES),
    *(zone(name) for name in RIOMAR_ZONES),
    *(zone(name) for name in METROPOLITANA_ZONES),
    *(zone(name) for name in SURORIENTE_ZONES),
    *(zone(name) for name in SUROCCIDENTE_ZONES),
    zone("Soledad", "Soledad", slug="soledad"),
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

        for zone_data in ZONES:
            _obj, created = Zone.objects.update_or_create(
                name=zone_data["name"],
                city=zone_data["city"],
                defaults={
                    "slug": zone_data["slug"],
                    "is_active": True,
                },
            )
            zone_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(CATEGORIES)} categories, {len(ZONES)} zones ({category_count + zone_count} new)."
            )
        )
