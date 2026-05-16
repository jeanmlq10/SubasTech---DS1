from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.db.models import Avg, Count, Q, Sum

from catalog.models import Service, TechnicianProfile


@dataclass(frozen=True)
class RecommendationRequest:
    category: str | None = None
    location: str | None = None
    urgency: str = "normal"
    limit: int = 5


def _normalize(value: Decimal | float | int | None, max_value: float) -> float:
    if value is None:
        return 0.0
    return min(float(value), max_value) / max_value


def calculate_technician_score(technician: TechnicianProfile, urgency: str = "normal", zone_match: bool = False) -> float:
    rating_score = _normalize(getattr(technician, "avg_rating", None), 5) * 40
    completion_score = _normalize(technician.service_completion_rate, 100) * 25
    availability_score = 15 if technician.availability_status == TechnicianProfile.AvailabilityStatus.AVAILABLE else 0
    zone_score = 10 if zone_match else 0
    response_score = max(0, 10 - min(technician.response_time_minutes, 120) / 12)
    penalty_points = getattr(technician, "active_penalty_points", 0) or 0
    urgency_bonus = 5 if urgency == "high" and technician.availability_status == TechnicianProfile.AvailabilityStatus.AVAILABLE else 0
    verification_bonus = 5 if technician.is_verified else 0

    score = rating_score + completion_score + availability_score + zone_score + response_score + urgency_bonus + verification_bonus - penalty_points
    return round(min(max(score, 0), 100), 2)


def recommend_services(request: RecommendationRequest) -> Iterable[dict]:
    services = Service.objects.filter(is_active=True, technician__is_verified=True).select_related(
        "category", "technician__user"
    ).prefetch_related("technician__zones", "technician__penalties")

    if request.category:
        services = services.filter(Q(category__slug__icontains=request.category) | Q(category__name__icontains=request.category))

    if request.location:
        services = services.filter(
            Q(technician__zones__name__icontains=request.location) | Q(technician__zones__slug__icontains=request.location)
        )

    services = services.annotate(
        avg_rating=Avg("technician__ratings__score"),
        rating_count=Count("technician__ratings", distinct=True),
        active_penalty_points=Sum("technician__penalties__points", filter=Q(technician__penalties__is_active=True)),
    ).distinct()

    recommendations = []
    for service in services:
        technician = service.technician
        technician.avg_rating = service.avg_rating
        technician.active_penalty_points = service.active_penalty_points or 0
        zone_match = bool(request.location and any(request.location.lower() in zone.name.lower() for zone in technician.zones.all()))
        recommendations.append(
            {
                "service_id": service.id,
                "service_title": service.title,
                "category": service.category.name,
                "base_price": str(service.base_price),
                "technician_id": technician.id,
                "technician_name": technician.user.get_full_name() or technician.user.username,
                "availability_status": technician.availability_status,
                "response_time_minutes": technician.response_time_minutes,
                "rating_average": round(float(service.avg_rating or 0), 2),
                "rating_count": service.rating_count,
                "score": calculate_technician_score(technician, urgency=request.urgency, zone_match=zone_match),
            }
        )

    return sorted(recommendations, key=lambda item: item["score"], reverse=True)[: request.limit]
