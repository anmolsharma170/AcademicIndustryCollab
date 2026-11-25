"""URL routes for authentication and onboarding."""

from django.urls import path

from .views import OnboardingView, PortalLoginView, PortalLogoutView, PortalRegisterView

app_name = "accounts"

urlpatterns = [
    path("login/", PortalLoginView.as_view(), name="login"),
    path("register/", PortalRegisterView.as_view(), name="register"),
    path("logout/", PortalLogoutView.as_view(), name="logout"),
    path("onboarding/", OnboardingView.as_view(), name="onboarding"),
]
