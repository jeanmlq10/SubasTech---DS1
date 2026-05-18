from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Category, Service, TechnicianProfile, Zone


class TechnicianOnboardingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()
        self.technician = self.user_model.objects.create_user(
            username="tech",
            password="Password123",
            role="technician",
        )
        self.zone = Zone.objects.create(name="Riomar", city="Barranquilla")

    def test_technician_can_complete_onboarding(self):
        self.client.force_authenticate(self.technician)

        response = self.client.post(
            "/api/technician/onboarding/",
            {
                "bio": "Electricista residencial certificado.",
                "availability_status": "available",
                "response_time_minutes": 20,
                "zone_ids": [self.zone.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["onboarding_complete"])
        profile = TechnicianProfile.objects.get(user=self.technician)
        self.assertEqual(profile.zones.first(), self.zone)

    def test_client_cannot_complete_technician_onboarding(self):
        client_user = self.user_model.objects.create_user(username="client", password="Password123", role="client")
        self.client.force_authenticate(client_user)

        response = self.client.post("/api/technician/onboarding/", {"bio": "Nope"}, format="json")

        self.assertEqual(response.status_code, 403)


class TechnicianServiceCrudTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()
        self.category = Category.objects.create(name="Electrician", slug="electrician")
        self.technician = self.user_model.objects.create_user(
            username="tech",
            password="Password123",
            role="technician",
        )
        self.profile = TechnicianProfile.objects.create(user=self.technician)

    def test_technician_can_create_update_and_delete_own_service(self):
        self.client.force_authenticate(self.technician)

        create_response = self.client.post(
            "/api/technician/services/",
            {
                "category_id": self.category.id,
                "title": "Instalacion de tomacorrientes",
                "description": "Instalacion y revision electrica residencial.",
                "base_price": "75000.00",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        service_id = create_response.json()["id"]
        service = Service.objects.get(pk=service_id)
        self.assertEqual(service.technician, self.profile)

        update_response = self.client.patch(
            f"/api/technician/services/{service_id}/",
            {"base_price": "90000.00"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        service.refresh_from_db()
        self.assertEqual(str(service.base_price), "90000.00")

        delete_response = self.client.delete(f"/api/technician/services/{service_id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Service.objects.filter(pk=service_id).exists())

    def test_technician_only_sees_own_services(self):
        other_user = self.user_model.objects.create_user(username="other", password="Password123", role="technician")
        other_profile = TechnicianProfile.objects.create(user=other_user)
        Service.objects.create(
            technician=other_profile,
            category=self.category,
            title="Otro servicio",
            description="No debe aparecer.",
            base_price=50000,
        )
        Service.objects.create(
            technician=self.profile,
            category=self.category,
            title="Mi servicio",
            description="Debe aparecer.",
            base_price=80000,
        )
        self.client.force_authenticate(self.technician)

        response = self.client.get("/api/technician/services/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["title"], "Mi servicio")


class SeedInitialDataTests(TestCase):
    def test_seed_initial_data_is_idempotent(self):
        from django.core.management import call_command

        call_command("seed_initial_data")
        first_category_count = Category.objects.count()
        first_zone_count = Zone.objects.count()

        call_command("seed_initial_data")

        self.assertEqual(Category.objects.count(), first_category_count)
        self.assertEqual(Zone.objects.count(), first_zone_count)
        self.assertTrue(Category.objects.filter(slug="electrician").exists())
        self.assertTrue(Zone.objects.filter(slug="barranquilla-riomar").exists())


class AdminCatalogPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_user(username="catalog-admin", password="Password123", role="admin")
        self.regular_user = self.user_model.objects.create_user(username="catalog-client", password="Password123", role="client")

    def test_admin_can_create_category_and_zone(self):
        self.client.force_authenticate(self.admin)

        category_response = self.client.post(
            "/api/categories/",
            {"name": "Painter", "description": "Painting services", "is_active": True},
            format="json",
        )
        zone_response = self.client.post(
            "/api/zones/",
            {"name": "Miramar", "city": "Barranquilla", "is_active": True},
            format="json",
        )

        self.assertEqual(category_response.status_code, 201)
        self.assertEqual(zone_response.status_code, 201)

    def test_non_admin_cannot_create_category(self):
        self.client.force_authenticate(self.regular_user)

        response = self.client.post(
            "/api/categories/",
            {"name": "Painter", "description": "Painting services", "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_non_admin_cannot_create_service_from_public_services_endpoint(self):
        category = Category.objects.create(name="Plumber", slug="plumber")
        technician_user = self.user_model.objects.create_user(username="tech-public", password="Password123", role="technician")
        technician = TechnicianProfile.objects.create(user=technician_user)
        self.client.force_authenticate(self.regular_user)

        response = self.client.post(
            "/api/services/",
            {
                "technician_id": technician.id,
                "category_id": category.id,
                "title": "Instalacion de llave",
                "description": "Servicio no autorizado desde endpoint publico.",
                "base_price": "55000.00",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_technician_cannot_update_another_technician_profile(self):
        technician_user = self.user_model.objects.create_user(username="owner-tech", password="Password123", role="technician")
        other_user = self.user_model.objects.create_user(username="other-tech", password="Password123", role="technician")
        profile = TechnicianProfile.objects.create(user=technician_user, bio="Original bio")
        TechnicianProfile.objects.create(user=other_user)
        self.client.force_authenticate(other_user)

        response = self.client.patch(
            f"/api/technicians/{profile.id}/",
            {"bio": "Intento de cambio"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)


class DemoSeedTests(TestCase):
    def test_seed_demo_data_creates_project_demo_records_idempotently(self):
        from django.core.management import call_command
        from django.contrib.auth import get_user_model
        from disputes.models import Dispute
        from leads.models import ServiceLead

        call_command("seed_demo_data")
        call_command("seed_demo_data")

        user_model = get_user_model()
        self.assertTrue(user_model.objects.filter(username="demo_admin", role="admin").exists())
        self.assertTrue(user_model.objects.filter(username="demo_arbiter", role="arbiter").exists())
        self.assertTrue(user_model.objects.filter(username="tech_carlos", role="technician").exists())
        self.assertGreaterEqual(TechnicianProfile.objects.filter(is_verified=True).count(), 3)
        self.assertGreaterEqual(Service.objects.filter(is_active=True).count(), 3)
        self.assertGreaterEqual(ServiceLead.objects.count(), 3)
        self.assertGreaterEqual(Dispute.objects.count(), 1)
