from decimal import Decimal

from django.db.models import Avg, Count, Sum

from disputes.models import Dispute
from leads.models import ServiceLead

from .models import Penalty


def calculate_technician_reputation(profile) -> dict:
    ratings = profile.ratings.aggregate(average_rating=Avg("score"), rating_count=Count("id"))
    active_penalties = profile.penalties.filter(is_active=True).aggregate(total=Sum("points"))
    actionable_leads = profile.leads.exclude(status=ServiceLead.Status.NEW)
    completed_services = actionable_leads.filter(status=ServiceLead.Status.CLOSED).count()
    completion_denominator = actionable_leads.count()
    completion_rate = Decimal("0")
    if completion_denominator:
        completion_rate = (Decimal(completed_services) / Decimal(completion_denominator)) * Decimal("100")

    penalty_points = active_penalties["total"] or 0
    average_rating = ratings["average_rating"] or 0
    reputation_score = max(
        0,
        min(
            100,
            round(
                float(
                    (Decimal(str(average_rating)) / Decimal("5")) * Decimal("60")
                    + completion_rate * Decimal("0.3")
                    + min(completed_services, 20)
                    - penalty_points * 4
                ),
                2,
            ),
        ),
    )

    return {
        "average_rating": round(float(average_rating), 2),
        "rating_count": ratings["rating_count"] or 0,
        "completed_services": completed_services,
        "service_completion_rate": completion_rate.quantize(Decimal("0.01")),
        "active_penalty_points": penalty_points,
        "reputation_score": reputation_score,
    }


def refresh_technician_reputation(profile) -> dict:
    summary = calculate_technician_reputation(profile)
    profile.completed_services = summary["completed_services"]
    profile.service_completion_rate = summary["service_completion_rate"]
    profile.save(update_fields=["completed_services", "service_completion_rate", "updated_at"])
    return summary


def evaluate_automatic_penalties(profile) -> list[Penalty]:
    active_rules: dict[str, dict] = {}

    for lead in profile.leads.all():
        if lead.metadata.get("outcome") == "no_show":
            active_rules[f"lead-no-show-{lead.id}"] = {
                "code": Penalty.Code.NO_SHOW,
                "reason": f"No show recorded for lead #{lead.id}",
                "points": 3,
                "metadata": {"automatic": True, "source": "lead", "lead_id": lead.id},
            }
        if lead.metadata.get("cancellation_timing") == "late":
            active_rules[f"lead-late-cancellation-{lead.id}"] = {
                "code": Penalty.Code.LATE_CANCELLATION,
                "reason": f"Late cancellation recorded for lead #{lead.id}",
                "points": 2,
                "metadata": {"automatic": True, "source": "lead", "lead_id": lead.id},
            }

    for dispute_id in profile.disputes.filter(
        status=Dispute.Status.RESOLVED,
        decision=Dispute.Decision.FAVOR_CLIENT,
    ).values_list("id", flat=True):
        active_rules[f"dispute-{dispute_id}"] = {
            "code": Penalty.Code.LOST_DISPUTE,
            "reason": f"Dispute #{dispute_id} resolved in favor of the client",
            "points": 2,
            "metadata": {"automatic": True, "source": "dispute", "dispute_id": dispute_id},
        }

    summary = calculate_technician_reputation(profile)
    if summary["rating_count"] >= 3 and summary["average_rating"] < 3:
        active_rules["low-reputation"] = {
            "code": Penalty.Code.LOW_REPUTATION,
            "reason": "Technician average rating dropped below 3.0",
            "points": 3,
            "metadata": {"automatic": True, "source": "ratings"},
        }

    existing_automatic = {
        _automatic_penalty_key(penalty): penalty
        for penalty in profile.penalties.filter(metadata__automatic=True)
    }
    synced_penalties: list[Penalty] = []

    for key, payload in active_rules.items():
        penalty = existing_automatic.pop(key, None)
        if penalty:
            changed = False
            for field in ("code", "reason", "points", "metadata"):
                if getattr(penalty, field) != payload[field]:
                    setattr(penalty, field, payload[field])
                    changed = True
            if not penalty.is_active:
                penalty.is_active = True
                changed = True
            if changed:
                penalty.save(update_fields=["code", "reason", "points", "metadata", "is_active", "updated_at"])
        else:
            penalty = Penalty.objects.create(technician=profile, is_active=True, **payload)
        synced_penalties.append(penalty)

    for stale_penalty in existing_automatic.values():
        if stale_penalty.is_active:
            stale_penalty.is_active = False
            stale_penalty.save(update_fields=["is_active", "updated_at"])

    refresh_technician_reputation(profile)
    return synced_penalties


def _automatic_penalty_key(penalty: Penalty) -> str:
    metadata = penalty.metadata or {}
    if penalty.code == Penalty.Code.NO_SHOW and metadata.get("lead_id"):
        return f"lead-no-show-{metadata['lead_id']}"
    if penalty.code == Penalty.Code.LATE_CANCELLATION and metadata.get("lead_id"):
        return f"lead-late-cancellation-{metadata['lead_id']}"
    if penalty.code == Penalty.Code.LOST_DISPUTE and metadata.get("dispute_id"):
        return f"dispute-{metadata['dispute_id']}"
    if penalty.code == Penalty.Code.LOW_REPUTATION:
        return "low-reputation"
    return f"manual-{penalty.id}"
