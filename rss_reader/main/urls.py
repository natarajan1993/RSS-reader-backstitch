from django.urls import path, include
from rest_framework import routers

from . import views

urlpatterns = [
    path('', views.home,name='home'),
    path('feeds/', views.get_feeds, name='feeds'),
    path('add_feed/', views.add_feed, name='add_feed'),
    path('update/<int:feed_id>', views.update_feed, name='update_feed'),
    path('delete/<int:feed_id>', views.delete_feed, name='delete_feed')
    # path('api/feeds', views.FeedAPIView.as_view(),name='api-feed'),
]

