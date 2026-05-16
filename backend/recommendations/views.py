from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import RecommendationRequest, recommend_services


class RecommendationInputSerializer(serializers.Serializer):
    category = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    urgency = serializers.ChoiceField(choices=["low", "normal", "high"], default="normal")
    limit = serializers.IntegerField(default=5, min_value=1, max_value=10)


class RecommendationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RecommendationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        recommendation_request = RecommendationRequest(
            category=payload.get("category") or None,
            location=payload.get("location") or None,
            urgency=payload.get("urgency", "normal"),
            limit=payload.get("limit", 5),
        )
        return Response({"results": list(recommend_services(recommendation_request))})
