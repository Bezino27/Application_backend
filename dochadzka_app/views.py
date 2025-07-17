# odstránil som import z allauth.conftest
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import (ClubSerializer, CategorySerializer,
                          UserMeUpdateSerializer,CategorySerializer2)

from rest_framework import status
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from .models import UserCategoryRole, Category, User, Club, TrainingAttendance  # predpokladám, že máš UserProfile model
from rest_framework import generics

User = get_user_model()


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user

    if request.method == 'PUT':
        print("PRIJATÉ ÚDAJE:", request.data)
        serializer = UserMeUpdateSerializer(user, data=request.data, partial=True)  # ⬅️ dôležité
        if serializer.is_valid():
            serializer.save()
            print("ULOŽENÉ ÚDAJE:", serializer.validated_data)
            return Response({'detail': 'Údaje boli aktualizované'})
        print("CHYBY SERIALIZERA:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Pôvodné GET zostáva
    roles_qs = UserCategoryRole.objects.filter(user=user)
    roles = list(set(role.role for role in roles_qs))
    assigned_categories = list(set(role.category.name for role in roles_qs))
    club_serialized = ClubSerializer(user.club).data if user.club else None

    data = {
        'username': user.username,
        'name': f"{user.first_name} {user.last_name}",
        'email': user.email,
        'email_2': user.email_2,
        'birth_date': user.birth_date,
        'number': user.number,
        'roles': roles,
        'assigned_categories': assigned_categories,
        'club': club_serialized,
        'height': user.height,
        'weight': user.weight,
        'side': user.side,
    }

    return Response(data)

class RegisterView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        role = request.data.get('role')

        if not username or not password or not role:
            return Response({'error': 'Missing username, password, or role'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'User already exists'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password)

        # Tu vytvoríš UserProfile a priradíš rolu podľa toho, ako máš modely
        # Príklad (ak máš UserProfile model s FK na User):
        User.objects.create(user=user, role=role)

        return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)


@csrf_exempt  # Dočasne vypne CSRF ochranu, ak testuješ cez Postman/React
def login_view(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({"message": "Login successful", "username": user.username})
        else:
            return JsonResponse({"message": "Login failed"}, status=401)
    return JsonResponse({"message": "Method not allowed"}, status=405)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_categories(request, club_id):
    # Skontrolujeme, či klub s daným id existuje
    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        return Response({"detail": "Club not found."}, status=404)

    # Filtrovanie kategórií podľa club_id
    categories = Category.objects.filter(club=club)
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Training, Category
from .serializers import TrainingCreateSerializer
from datetime import datetime

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_training_view(request):
    serializer = TrainingCreateSerializer(data=request.data)
    if serializer.is_valid():
        training = serializer.save(
            created_by=request.user,
            club=request.user.club  # uprav podľa tvojej štruktúry
        )
        return Response({"success": True, "id": training.id}, status=status.HTTP_201_CREATED)

    print("CHYBA PRI VYTVORENÍ TRÉNINGU:", serializer.errors)  # 👈 pridaj tento výpis
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from dochadzka_app.models import Training, Category
from dochadzka_app.serializers import TrainingSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def player_trainings_view(request):
    user = request.user
    club = user.club

    # Získaj kategórie, kde je hráč
    categories = Category.objects.filter(club=club, user_roles__user=user).distinct()

    # Tréningy + optimalizované načítanie FK a M2M
    trainings = Training.objects.filter(
        category__in=categories,
        club=club
    ).select_related('category').prefetch_related('attendances').order_by('date')

    serializer = TrainingSerializer(trainings, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_training_attendance(request):
    user = request.user
    training_id = request.data.get('training_id')
    status_value = request.data.get('status')

    if status_value not in ['present', 'absent', 'unknown']:
        return Response({"error": "Neplatný status"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        training = Training.objects.get(id=training_id)
    except Training.DoesNotExist:
        return Response({"error": "Tréning nenájdený"}, status=status.HTTP_404_NOT_FOUND)

    attendance, created = TrainingAttendance.objects.get_or_create(
        user=user,
        training=training,
        defaults={'status': status_value}
    )

    if not created:
        attendance.status = status_value
        attendance.save()

    return Response({"message": "Účasť bola úspešne zaznamenaná", "status": status_value})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_categories_view(request):
    user = request.user
    categories = Category.objects.filter(players__user=user).distinct()
    serializer = CategorySerializer2(categories, many=True)
    return Response(serializer.data)