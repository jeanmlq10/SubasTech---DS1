from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import interpret_message


class InterpretationInputSerializer(serializers.Serializer):
    message = serializers.CharField()


class InterpretMessageAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InterpretationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(interpret_message(serializer.validated_data["message"]))
