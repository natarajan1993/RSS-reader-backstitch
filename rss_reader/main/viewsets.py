from rest_framework import viewsets
from rest_framework import permissions

from .serializers import FeedSerializer
from .models import Feed

class FeedViewSet(viewsets.ModelViewSet):
    queryset = Feed.objects.all()
    serializer_class = FeedSerializer
    # permission_classes = [permissions.IsAuthenticated]