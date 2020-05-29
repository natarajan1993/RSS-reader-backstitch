from django.contrib import admin
from django.urls import path, include
from rest_framework import routers

from main.viewsets import FeedViewSet

router = routers.DefaultRouter()
router.register(r'feeds',FeedViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('api/', include(router.urls)),
]
