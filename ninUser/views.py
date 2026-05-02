from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError
from django.contrib.auth import authenticate
from django.utils import timezone

from .models import User, UserProfile,UserDevice
from .serializers import (
    SignInRequestSerializer, SignUpSerializer, SignInSerializer,
    UserSerializer, AuthResponseSerializer
)
from .firebase import verify_firebase_token


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class SignUpView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SignUpSerializer 
    

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        password = serializer.validated_data['password']
        # id_token = serializer.validated_data['id_token']
        phone_number = serializer.validated_data['phone_number']
        name = serializer.validated_data['name']
        platform = serializer.validated_data['platform']
        device_name = serializer.validated_data['device_name']
        device_id = serializer.validated_data['device_id']


        # try:
        #     decoded_token = verify_firebase_token(id_token)
        # except ExpiredIdTokenError:
        #     return Response({'detail': 'Firebase token has expired.'}, status=status.HTTP_401_UNAUTHORIZED)
        # except InvalidIdTokenError:
        #     return Response({'detail': 'Invalid Firebase token.'}, status=status.HTTP_401_UNAUTHORIZED)

        # firebase_phone = decoded_token.get('phone_number')
        # if firebase_phone != phone_number:
        #     return Response(
        #         {'detail': 'Phone number does not match the verified token.'},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )

        if User.objects.filter(phone_number=phone_number).exists():
            return Response(
                {'detail': 'An account with this phone number already exists. Please sign in.'},
                status=status.HTTP_409_CONFLICT
            )

        user = User.objects.create_user(
            phone_number=phone_number,
            name=name,
            is_verified=True,
            password=password
        )
        UserProfile.objects.create(user=user, display_name=name)
        UserDevice.objects.create(user=user, platform=platform, device_name=device_name, device_id=device_id)

        tokens = get_tokens_for_user(user)
        return Response(
            AuthResponseSerializer({'user': user, 'tokens': tokens}).data,
            status=status.HTTP_201_CREATED
        )

class SignInRequestView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SignInRequestSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data["phone_number"]
        password = serializer.validated_data["password"]

        # 🔐 Authenticate user
        user = authenticate(username=phone_number, password=password)

        if user is None:
            return Response(
                {"detail": "Invalid phone number or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # # Optional: update last login
        # user.last_login = timezone.now()
        # user.save()

        # return Response(
        #     {
        #         "detail": "Authentication successful",
        #         "user_phone": str(user.phone_number)
        #     },
        #     status=status.HTTP_200_OK
        # )
        user.update_last_seen()

        tokens = get_tokens_for_user(user)
        return Response(
            AuthResponseSerializer({'user': user, 'tokens': tokens}).data,
            status=status.HTTP_200_OK
        )
    

class SignInView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SignInSerializer        
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        id_token = serializer.validated_data['id_token']

        try:
            decoded_token = verify_firebase_token(id_token)
        except ExpiredIdTokenError:
            return Response({'detail': 'Firebase token has expired.'}, status=status.HTTP_401_UNAUTHORIZED)
        except InvalidIdTokenError:
            return Response({'detail': 'Invalid Firebase token.'}, status=status.HTTP_401_UNAUTHORIZED)

        phone_number = decoded_token.get('phone_number')
        if not phone_number:
            return Response({'detail': 'Token does not contain a phone number.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {'detail': 'No account found. Please sign up first.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        

        user.update_last_seen()

        tokens = get_tokens_for_user(user)
        return Response(
            AuthResponseSerializer({'user': user, 'tokens': tokens}).data,
            status=status.HTTP_200_OK
        )


class MeView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer          # ← Swagger reads response from here

    def get(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)