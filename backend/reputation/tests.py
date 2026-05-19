from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Service, TechnicianProfile
from disputes.models import Dispute
from leads.models import ServiceLead

from .models import Penalty, Rating
from .services import calculate_technician_reputation, evaluate_automatic_penalties, refresh_technician_reputation


class ReputationWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="rep-admin", password="Password123", role="admin")
        self.client_user = user_model.objects.create_user(
            username="rep-client",
            password="Password123",
            role="client",
            phone_number="573001112233",
        )
        self.other_client = user_model.objects.create_user(
            username="rep-client-2",
            password="Password123",
            role="client",
            phone_number="573001112244",
        )
        self.tech_user = user_model.objects.create_user(username="rep-tech", password="Password123", role="technician")
        self.tech_user_2 = user_model.objects.create_user(username="rep-tech-2", password="Password123", role="technician")
        self.category = Category.objects.create(name="HVAC", slug="hvac")
        self.profile = TechnicianProfile.objects.create(user=self.tech_user, is_verified=True)
        self.other_profile = TechnicianProfile.objects.create(user=self.tech_user_2, is_verified=True)
        self.service = Service.objects.create(
            technician=self.profile,
            category=self.category,
            title="Mantenimiento aire",
            description="Servicio tecnico",
            base_price=120000,
        )
        self.lead = ServiceLead.objects.create(
            technician=self.profile,
            client_user=self.client_user,
            service=self.service,
            client_phone=self.client_user.phone_number,
            client_name="Cliente demo",
            message="Necesito servicio",
            status=ServiceLead.Status.CLOSED,
            metadata={},
        )

    def test_client_can_rate_technician_once_per_service(self):
        self.client.force_authenticate(self.client_user)

        first = self.client.post(
            "/api/ratings/",
            {
                "target_role": Rating.TargetRole.TECHNICIAN,
                "technician": self.profile.id,
                "service": self.service.id,
                "score": 5,
                "comment": "Muy buen servicio",
            },
            format="json",
        )
        duplicate = self.client.post(
            "/api/ratings/",
            {
                "target_role": Rating.TargetRole.TECHNICIAN,
                "technician": self.profile.id,
                "service": self.service.id,
                "score": 4,
            },
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(Rating.objects.count(), 1)

    def test_technician_can_rate_linked_client_once_per_lead(self):
        self.client.force_authenticate(self.tech_user)

        response = self.client.post(
            "/api/ratings/",
            {
                "target_role": Rating.TargetRole.CLIENT,
                "client": self.client_user.id,
                "lead": self.lead.id,
                "score": 4,
                "comment": "Cliente puntual",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        rating = Rating.objects.get()
        self.assertEqual(rating.author, self.tech_user)
        self.assertEqual(rating.client, self.client_user)
        self.assertEqual(rating.lead, self.lead)

    def test_technician_cannot_rate_unlinked_client(self):
        self.client.force_authenticate(self.tech_user)

        response = self.client.post(
            "/api/ratings/",
            {
                "target_role": Rating.TargetRole.CLIENT,
                "client": self.other_client.id,
                "lead": self.lead.id,
                "score": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_reputation_summary_updates_completed_services(self):
        Rating.objects.create(
            author=self.client_user,
            technician=self.profile,
            service=self.service,
            lead=self.lead,
            target_role=Rating.TargetRole.TECHNICIAN,
            score=5,
        )

        summary = refresh_technician_reputation(self.profile)
        self.profile.refresh_from_db()

        self.assertEqual(summary["average_rating"], 5.0)
        self.assertEqual(summary["completed_services"], 1)
        self.assertEqual(str(self.profile.service_completion_rate), "100.00")

    def test_automatic_penalties_cover_dispute_and_lead_flags(self):
        self.lead.metadata = {"outcome": "no_show", "cancellation_timing": "late"}
        self.lead.save(update_fields=["metadata", "updated_at"])
        Dispute.objects.create(
            client=self.client_user,
            technician=self.profile,
            service=self.service,
            title="Incumplimiento",
            description="No asistio",
            status=Dispute.Status.RESOLVED,
            decision=Dispute.Decision.FAVOR_CLIENT,
        )
        Rating.objects.create(
            author=self.client_user,
            technician=self.profile,
            service=self.service,
            lead=self.lead,
            target_role=Rating.TargetRole.TECHNICIAN,
            score=1,
        )
        Rating.objects.create(
            author=self.other_client,
            technician=self.profile,
            service=Service.objects.create(
                technician=self.profile,
                category=self.category,
                title="Mantenimiento secundario",
                description="Otro servicio tecnico",
                base_price=90000,
            ),
            target_role=Rating.TargetRole.TECHNICIAN,
            score=2,
        )
        third_client = get_user_model().objects.create_user(username="rep-client-3", password="Password123", role="client")
        Rating.objects.create(
            author=third_client,
            technician=self.profile,
            service=Service.objects.create(
                technician=self.profile,
                category=self.category,
                title="Visita adicional",
                description="Otro servicio",
                base_price=30000,
            ),
            target_role=Rating.TargetRole.TECHNICIAN,
            score=2,
        )

        penalties = evaluate_automatic_penalties(self.profile)
        codes = {penalty.code for penalty in penalties}
        summary = calculate_technician_reputation(self.profile)

        self.assertIn(Penalty.Code.NO_SHOW, codes)
        self.assertIn(Penalty.Code.LATE_CANCELLATION, codes)
        self.assertIn(Penalty.Code.LOST_DISPUTE, codes)
        self.assertIn(Penalty.Code.LOW_REPUTATION, codes)
        self.assertGreater(summary["active_penalty_points"], 0)

    def test_admin_can_read_and_create_penalties(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/penalties/",
            {
                "technician": self.profile.id,
                "code": Penalty.Code.MANUAL,
                "reason": "Revision manual",
                "points": 1,
                "metadata": {"source": "admin"},
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Penalty.objects.filter(technician=self.profile, reason="Revision manual").exists())

    def test_technician_can_only_see_their_own_penalties(self):
        Penalty.objects.create(technician=self.profile, code=Penalty.Code.MANUAL, reason="Propia", points=1)
        Penalty.objects.create(technician=self.other_profile, code=Penalty.Code.MANUAL, reason="Ajena", points=1)

        self.client.force_authenticate(self.tech_user)
        response = self.client.get("/api/penalties/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["reason"], "Propia")
