from django.urls import path
from .views import SignInRequestView, SignUpView, SignInView, MeView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('auth/signup/', SignUpView.as_view(), name='signup'),
    path('auth/signin/', SignInView.as_view(), name='signin'),
    path('auth/signinrequest/', SignInRequestView.as_view(), name='signin-request'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
]