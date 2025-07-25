# odstránil som import z allauth.conftest
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import (ClubSerializer, CategorySerializer,
                          UserMeUpdateSerializer,CategorySerializer2, UserCategoryRoleSerializer)

from rest_framework import status
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from .models import UserCategoryRole, Category, User, Club, TrainingAttendance
from rest_framework import generics
from .helpers import send_push_notification
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
    roles = UserCategoryRoleSerializer(
        roles_qs.exclude(category__isnull=True), many=True
    ).data
    assigned_categories = list(set(
        role.category.name for role in roles_qs if role.category
    ))
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

from .helpers import send_push_notification
from .models import User

from .helpers import send_push_notification  # nezabudni na import
from .models import User  # už asi máš, ale pre istotu

from .helpers import send_push_notification
from .models import UserCategoryRole, Role

import logging
logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_training_view(request):
    serializer = TrainingCreateSerializer(data=request.data)
    if serializer.is_valid():
        training = serializer.save(
            created_by=request.user,
            club=request.user.club
        )

        logger.info("✅ Tréning vytvorený:", training.description)
        logger.info("➡️ Kategória:", training.category.name)

        players = User.objects.filter(
            roles__category=training.category,
            roles__role=Role.PLAYER
        ).exclude(expo_push_token=None).distinct()

        logger.info(f"➡️ Posielam notifikácie {players.count()} hráčom")

        for player in players:
            logger.info(f"📤 Posielam na {player.username} → {player.expo_push_token}")
            try:
                logger.info(f"👉 Token hráča {player.username}: {player.expo_push_token}")

                response = send_push_notification(
                    player.expo_push_token,
                    "Nový tréning",
                    f"{training.description} - {training.date.strftime('%d.%m.%Y %H:%M')} v {training.location}"
                )
                logger.info(f"✅ Odpoveď: {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"❌ Chyba pri posielaní na {player.username}: {str(e)}")

        return Response({"success": True, "id": training.id}, status=status.HTTP_201_CREATED)

    logger.warning("❌ CHYBA PRI VYTVORENÍ TRÉNINGU:", serializer.errors)
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def training_detail_view(request, training_id):
    try:
        training = Training.objects.get(id=training_id)
    except Training.DoesNotExist:
        return Response({"error": "Tréning neexistuje"}, status=status.HTTP_404_NOT_FOUND)

    attendances = TrainingAttendance.objects.filter(training=training).select_related('user')
    all_players = User.objects.filter(
        roles__category=training.category,
        roles__role='player'
    ).distinct()

    present = []
    absent = []
    unknown = []

    for player in all_players:
        att = next((a for a in attendances if a.user_id == player.id), None)
        full_name = f"{player.first_name} {player.last_name}".strip() or player.username

        player_data = {
            "id": player.id,
            "name": full_name,
            "number": player.number,
            "birth_date": player.birth_date,
        }

        if att:
            if att.status == 'present':
                present.append(player_data)
            elif att.status == 'absent':
                absent.append(player_data)
        else:
            unknown.append(player_data)
    return Response({
        "id": training.id,
        "description": training.description,
        "date": training.date.isoformat(),
        "location": training.location,
        "created_by": training.created_by.username if training.created_by else "Neznámy",
        "players": {
            "present": present,
            "absent": absent,
            "unknown": unknown
        }
    })

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_expo_push_token(request):
    token = request.data.get("token")
    logger.info(f"🔔 Prišiel request na uloženie tokenu od {request.user.username}")
    logger.info(f"📦 Token z requestu: {token}")

    if not token:
        logger.info("❌ Token neprišiel")
        return Response({"error": "Token je povinný"}, status=400)

    User.objects.filter(expo_push_token=token).exclude(id=request.user.id).update(expo_push_token=None)
    request.user.expo_push_token = token
    request.user.save()

    logger.info(f"✅ Token {token} uložený pre používateľa {request.user.username}")
    return Response({"success": True})

from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['POST'])
def test_push(request):
    token = request.data.get("token")  # teraz už bude fungovať
    if not token:
        return Response({"error": "Token is required"}, status=400)

    from .helpers import send_push_notification
    send_push_notification(token, "Test Notifikácia", "Toto je test.")

    return Response({"success": True})