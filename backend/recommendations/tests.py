from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Service, TechnicianProfile, Zone
from reputation.models import Rating
from .services import RecommendationRequest, recommend_services


class RecommendationEngineTests(TestCase):
    def test_recommends_verified_available_technician_by_category_and_zone(self):
        user_model = get_user_model()
        category = Category.objects.create(name="Electrician", slug="electrician")
        zone = Zone.objects.create(name="Riomar", city="Barranquilla")
        tech_user = user_model.objects.create_user(
            username="tech1",
            password="Password123",
            role="technician",
            first_name="Carlos",
            last_name="Mendoza",
        )
        client = user_model.objects.create_user(username="client1", password="Password123", role="client")
        profile = TechnicianProfile.objects.create(
            user=tech_user,
            is_verified=True,
            availability_status=TechnicianProfile.AvailabilityStatus.AVAILABLE,
            response_time_minutes=15,
            completed_services=30,
            service_completion_rate=95,
        )
        profile.zones.add(zone)
        service = Service.objects.create(
            technician=profile,
            category=category,
            title="Instalacion electrica",
            description="Servicio residencial",
            base_price=80000,
        )
        Rating.objects.create(technician=profile, client=client, service=service, score=5)

        results = list(recommend_services(RecommendationRequest(category="electrician", location="Riomar", urgency="high")))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["technician_name"], "Carlos Mendoza")
        self.assertEqual(results[0]["score"], 100)
