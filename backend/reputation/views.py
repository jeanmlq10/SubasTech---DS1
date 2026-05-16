from rest_framework import permissions, viewsets

from .models import Penalty, Rating
from .serializers import PenaltySerializer, RatingSerializer


class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.select_related("technician", "client", "service")
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)


class PenaltyViewSet(viewsets.ModelViewSet):
    queryset = Penalty.objects.select_related("technician")
    serializer_class = PenaltySerializer
    permission_classes = [permissions.IsAdminUser]
