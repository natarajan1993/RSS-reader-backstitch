from django.urls import path, include, re_path
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path('', views.home,name='home'),
    path('landing/',views.landing, name='landing'),

    path('feeds/', views.get_feeds, name='feeds'),
    path('add_feed/', views.add_feed, name='add_feed'),
    path('update/<int:feed_id>', views.update_feed, name='update_feed'),
    path('delete/<int:feed_id>', views.delete_feed, name='delete_feed'),

    path('accounts/login/', auth_views.LoginView.as_view(redirect_authenticated_user=True),{'template_name':'login.html'}, name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(),{'next_page':'home'}, name='logout'),
    path('accounts/signup/', views.signup_view, name="signup"),

    path('password-reset/',auth_views.PasswordResetView.as_view(template_name="registration/password_reset.html"), name="password_reset"),
    path('password-reset/done/',auth_views.PasswordResetDoneView.as_view(template_name="main/password_reset_done.html"), name="password_reset_done"),
    path('password-reset-confirm/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(template_name="main/password_reset_confirm.html"), name="password_reset_confirm"),
    path('password-reset-complete/',auth_views.PasswordResetCompleteView.as_view(template_name="main/password_reset_complete.html"), name="password_reset_complete"),
]

