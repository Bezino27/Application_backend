# odstránil som import z allauth.conftest
from django.shortcuts import get_object_or_404
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
        'id': user.id,
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



from .models import User  # už asi máš, ale pre istotu
from .models import UserCategoryRole, Role
import logging
logger = logging.getLogger(__name__)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Role, ExpoPushToken
from .serializers import TrainingCreateSerializer
from .helpers import send_push_notification  # tvoje posielanie
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_training_view(request):
    category_ids = request.data.get("category_ids")

    if not category_ids or not isinstance(category_ids, list):
        return Response({"error": "Musíš zadať aspoň jednu kategóriu."}, status=400)

    created_trainings = []

    for cat_id in category_ids:
        data = {
            "description": request.data.get("description"),
            "location": request.data.get("location"),
            "date": request.data.get("date"),
            "category": cat_id
        }

        serializer = TrainingCreateSerializer(data=data)
        if serializer.is_valid():
            training = serializer.save(
                created_by=request.user,
                club=request.user.club
            )

            logger.info(f"✅ Tréning vytvorený: {training.description}")
            logger.info(f"➡️ Kategória: {training.category.name}")

            # Všetci hráči danej kategórie
            players = User.objects.filter(
                roles__category=training.category,
                roles__role=Role.PLAYER
            ).distinct()

            logger.info(f"➡️ Posielam notifikácie hráčom ({players.count()})")

            for player in players:
                tokens = ExpoPushToken.objects.filter(user=player).values_list("token", flat=True)
                for token in tokens:
                    try:
                        response = send_push_notification(
                            token,
                            "Nový tréning",
                            f"{training.description} - {training.date.strftime('%d.%m.%Y %H:%M')} v {training.location}"
                        )
                        logger.info(f"📤 {player.username} → {token} → {response.status_code} - {response.text}")
                    except Exception as e:
                        logger.warning(f"❌ Chyba pri push {player.username} → {token}: {str(e)}")

            created_trainings.append(training.id)
        else:
            logger.warning(f"❌ Nevalidné dáta pre kategóriu {cat_id}: {serializer.errors}")

    if not created_trainings:
        return Response({"error": "Žiadny tréning nebol vytvorený."}, status=400)

    return Response({"success": True, "created_ids": created_trainings}, status=201)

# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
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
    training_id = request.data.get('training_id')
    user_id = request.data.get('user_id')  # ← nová možnosť
    status_value = request.data.get('status')

    if status_value not in ['present', 'absent', 'unknown']:
        return Response({"error": "Neplatný status"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        training = Training.objects.get(id=training_id)
    except Training.DoesNotExist:
        return Response({"error": "Tréning nenájdený"}, status=status.HTTP_404_NOT_FOUND)

    # Ak je tréner, môže meniť aj iným hráčom
    user_to_update = request.user
    if user_id and int(user_id) != request.user.id:
        is_coach = request.user.roles.filter(role='coach', category=training.category).exists()
        if not is_coach:
            return Response({"error": "Nemáš oprávnenie meniť účasť iným hráčom"}, status=status.HTTP_403_FORBIDDEN)
        try:
            user_to_update = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Používateľ nenájdený"}, status=status.HTTP_404_NOT_FOUND)

    attendance, created = TrainingAttendance.objects.get_or_create(
        user=user_to_update,
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
        training = Training.objects.select_related('category', 'created_by').get(id=training_id)
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
            elif att.status == 'unknown':
                unknown.append(player_data)
        else:
            unknown.append(player_data)

    return Response({
        "id": training.id,
        "description": training.description,
        "date": training.date.isoformat(),
        "location": training.location,
        "created_by": training.created_by.username if training.created_by else "Neznámy",
        "category_id": training.category.id,
        "category_name": training.category.name,
        "players": {
            "present": present,
            "absent": absent,
            "unknown": unknown
        }
    })

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import ExpoPushToken

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_expo_push_token(request):
    token = request.data.get("token")
    logger.info(f"🔔 Prišiel request na uloženie tokenu od {request.user.username}")
    logger.info(f"📦 Token z requestu: {token}")

    if not token:
        logger.info("❌ Token neprišiel")
        return Response({"error": "Token je povinný"}, status=400)

    # Ak token už existuje pre iného používateľa, zmaž ho
    ExpoPushToken.objects.filter(token=token).exclude(user=request.user).delete()

    # Ak token ešte neexistuje pre tohto usera, vytvor
    ExpoPushToken.objects.get_or_create(user=request.user, token=token)

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


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_training_view(request, training_id):
    training = get_object_or_404(Training, id=training_id)

    # Over, či používateľ je tréner v tejto kategórii
    is_coach = request.user.roles.filter(category=training.category, role=Role.COACH).exists()
    if not is_coach:
        return Response({"error": "Nemáš oprávnenie na zmazanie tohto tréningu."}, status=403)

    # Notifikuj hráčov o zmazaní
    players = User.objects.filter(
        roles__category=training.category,
        roles__role=Role.PLAYER
    ).distinct()

    logger.info(f"🗑️ Mazanie tréningu {training.id} – {training.description}")
    logger.info(f"➡️ Posielam notifikácie o zmazaní hráčom ({players.count()})")

    for player in players:
        tokens = ExpoPushToken.objects.filter(user=player).values_list("token", flat=True)
        for token in tokens:
            try:
                response = send_push_notification(
                    token,
                    "Zrušený tréning",
                    f"Tréning '{training.description}' bol zrušený."
                )
                logger.info(f"📤 {player.username} → {token} → {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"❌ Chyba pri push {player.username} → {token}: {str(e)}")

    training.delete()
    logger.info(f"✅ Tréning {training.id} úspešne zmazaný.")
    return Response({"success": True}, status=204)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def training_attendance_view(request, training_id):
    try:
        training = Training.objects.get(id=training_id)
    except Training.DoesNotExist:
        return Response({"error": "Tréning neexistuje"}, status=404)

    players = User.objects.filter(
        roles__category=training.category,
        roles__role='player'
    ).distinct()

    # načítaj všetky dochádzky pre tento tréning
    attendances = TrainingAttendance.objects.filter(training=training)
    attendance_map = {a.user_id: a.status for a in attendances}

    data = [
        {
            "id": player.id,
            "name": f"{player.first_name} {player.last_name}".strip() or player.username,
            "number": player.number,
            "birth_date": player.birth_date,
            "status": attendance_map.get(player.id, "unknown")  # ← pridaj status
        }
        for player in players
    ]

    return Response(data)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import User, Training, TrainingAttendance, Category

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def coach_players_attendance_view(request):
    user = request.user

    coach_categories = Category.objects.filter(user_roles__user=user, user_roles__role='coach').distinct()

    # Všetci hráči v týchto kategóriách
    players = User.objects.filter(
        roles__category__in=coach_categories,
        roles__role='player'
    ).distinct()

    # Odstráň používateľov, ktorí sú zároveň trénermi v tej istej kategórii
    filtered_players = []
    for player in players:
        player_roles = player.roles.filter(category__in=coach_categories)
        has_only_player_role = all(role.role == 'player' for role in player_roles)
        if has_only_player_role:
            filtered_players.append(player)

    response_data = []

    for player in filtered_players:
        player_categories = coach_categories.filter(user_roles__user=player).distinct()
        trainings_by_category = {}

        for cat in player_categories:
            trainings = Training.objects.filter(category=cat).order_by('-date')
            total = trainings.count()
            attendances = TrainingAttendance.objects.filter(user=player, training__in=trainings)
            present = attendances.filter(status='present').count()
            absent = attendances.filter(status='absent').count()
            unknown = total - (present + absent)

            percent = round((present / total) * 100) if total > 0 else 0

            trainings_serialized = []
            for t in trainings:
                att = attendances.filter(training=t).first()
                trainings_serialized.append({
                    'id': t.id,
                    'description': t.description,
                    'date': t.date.isoformat(),
                    'location': t.location,
                    'category': cat.id,
                    'category_name': cat.name,
                    'status': att.status if att else 'unknown',
                })

            trainings_by_category[cat.name] = {
                'total': total,
                'present': present,
                'absent': absent,
                'unknown': unknown,
                'percentage': percent,
                'trainings': trainings_serialized,
            }

        response_data.append({
            'player_id': player.id,
            'name': f"{player.first_name} {player.last_name}".strip() or player.username,
            'number': player.number,
            'birth_date': player.birth_date,
            'categories': trainings_by_category,
        })

    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def coach_trainings_view(request):
    user = request.user
    club = user.club

    # Získaj kategórie, kde má používateľ rolu coach
    coach_categories = Category.objects.filter(club=club, user_roles__user=user, user_roles__role='coach').distinct()

    # Získaj tréningy len pre tieto kategórie
    trainings = Training.objects.filter(
        category__in=coach_categories,
        club=club
    ).select_related('category').prefetch_related('attendances').order_by('date')

    serializer = TrainingSerializer(trainings, many=True, context={'request': request})
    return Response(serializer.data)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    user = request.user
    data = request.data
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not user.check_password(old_password):
        return Response({'detail': 'Zlé pôvodné heslo.'}, status=status.HTTP_400_BAD_REQUEST)

    if not new_password or len(new_password) < 6:
        return Response({'detail': 'Nové heslo musí mať aspoň 6 znakov.'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    return Response({'detail': 'Heslo úspešne zmenené.'})


# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User


# BACKEND - views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    data = request.data
    username = data.get('username')
    password = data.get('password')
    password2 = data.get('password2')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    birth_date = data.get('birth_date')
    club_id = data.get('club_id')

    if not all([username, password, password2, first_name, last_name, birth_date, club_id]):
        return Response({'detail': 'Vyplň všetky polia.'}, status=status.HTTP_400_BAD_REQUEST)

    if password != password2:
        return Response({'detail': 'Heslá sa nezhodujú.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'detail': 'Používateľské meno už existuje.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        return Response({'detail': 'Zvolený klub neexistuje.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        club=club
    )

    return Response({'detail': 'Registrácia prebehla úspešne.'}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_clubs(request):
    clubs = Club.objects.all()
    data = [{"id": club.id, "name": club.name} for club in clubs]
    return Response(data)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Message, MessageReaction
from .serializers import MessageSerializer, MessageReactionSerializer


from .models import ExpoPushToken  #
import logging
logger = logging.getLogger(__name__)  # pre logovanie chýb

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_messages_view(request, user_id):
    current_user = request.user

    if request.method == 'GET':
        # Parametre pre pagináciu
        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", 20))

        # Označíme prijaté správy ako prečítané
        Message.objects.filter(sender_id=user_id, recipient=current_user, read=False).update(read=True)

        # Vyber všetky správy medzi užívateľmi
        messages = Message.objects.filter(
            Q(sender=current_user, recipient_id=user_id) |
            Q(sender_id=user_id, recipient=current_user)
        ).order_by('-timestamp')  # najnovšie ako prvé

        # Aplikuj slice
        paginated = messages[offset:offset+limit]

        # Otoč späť do prirodzeného poradia (od najstaršej po najnovšiu)
        serializer = MessageSerializer(paginated[::-1], many=True, context={"request": request})
        return Response(serializer.data)


    elif request.method == 'POST':
        data = request.data.copy()
        data['sender'] = current_user.id
        serializer = MessageSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            message = serializer.save()
            # Posielanie notifikácií
            tokens = ExpoPushToken.objects.filter(user=message.recipient).values_list("token", flat=True)
            full_name = f"{current_user.first_name} {current_user.last_name}".strip()
            preview = message.text[:80] + ("..." if len(message.text) > 80 else "")
            for token in tokens:
                try:
                    response = send_push_notification(
                        token,
                        title=f"Nová správa od {full_name}",
                        message=preview
                    )
                    logger.info(f"📤 {message.recipient.username} → {token} → {response.status_code} - {response.text}")
                except Exception as e:
                    logger.warning(f"❌ Chyba pri push {message.recipient.username} → {token}: {str(e)}")
            # Vždy vráť validný JSON
            return Response(MessageSerializer(message, context={"request": request}).data, status=201)
        # Ak je invalid
        return Response(serializer.errors, status=400)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model

User = get_user_model()

from django.db.models import Q


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_users_list(request):
    user = request.user
    club = user.club
    roles = UserCategoryRole.objects.filter(user=user).values_list("role", flat=True)
    is_coach_or_admin = any(r.lower() in ['coach', 'admin'] for r in roles)

    users = User.objects.filter(club=club).exclude(id=user.id)

    filtered_users = []
    for u in users:
        u_roles = UserCategoryRole.objects.filter(user=u).values_list("role", flat=True)
        u_is_coach_or_admin = any(r.lower() in ['coach', 'admin'] for r in u_roles)

        # Ak si tréner alebo admin, zobraz všetkých
        # Inak zobraz len trénerov a adminov
        if is_coach_or_admin or u_is_coach_or_admin:
            messages_between = Message.objects.filter(
                Q(sender=user, recipient=u) | Q(sender=u, recipient=user)
            )

            last_msg = messages_between.order_by("-timestamp").first()
            last_timestamp = last_msg.timestamp.isoformat() if last_msg else None
            has_unread = messages_between.filter(sender=u, recipient=user, read=False).exists()

            filtered_users.append({
                "id": u.id,
                "username": u.username,
                "full_name": f"{u.first_name} {u.last_name}".strip(),
                "last_message_timestamp": last_timestamp,
                "has_unread": has_unread,
                "number": u.number,
            })

    sorted_users = sorted(
        filtered_users,
        key=lambda x: x["last_message_timestamp"] or "",
        reverse=True
    )

    return Response(sorted_users)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_reaction(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    emoji = request.data.get('emoji')
    user = request.user

    if not emoji:
        return Response({"error": "Emoji is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Skontroluj, či už existuje reakcia
    existing_reaction = MessageReaction.objects.filter(message=message, user=user).first()

    if existing_reaction:
        if existing_reaction.emoji == emoji:
            # rovnaká emoji → vymaž (toggle off)
            existing_reaction.delete()
            return Response({"deleted": True})
        else:
            # iná emoji → aktualizuj
            existing_reaction.emoji = emoji
            existing_reaction.save()
            return Response(MessageReactionSerializer(existing_reaction).data)
    else:
        # nová reakcia
        reaction = MessageReaction.objects.create(message=message, user=user, emoji=emoji)
        return Response(MessageReactionSerializer(reaction).data, status=status.HTTP_201_CREATED)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import User, UserCategoryRole


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_in_club(request):
    club = request.user.club
    if not club:
        return Response([], status=400)

    users = User.objects.filter(club=club).order_by('-date_joined')
    data = []
    for u in users:
        roles = UserCategoryRole.objects.filter(user=u).values('role', 'category__id', 'category__name')
        data.append({
            "id": u.id,
            "username": u.username,
            "name": u.get_full_name(),
            "email": u.email,
            "date_joined": u.date_joined,
            "roles": list(roles)
        })
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_role(request):
    try:
        user_id = int(request.data.get("user_id"))
        category_id = int(request.data.get("category_id"))
        role = str(request.data.get("role")).strip()
    except (TypeError, ValueError):
        return Response({"error": "Neplatné dáta – user_id a category_id musia byť čísla."}, status=400)

    if not user_id or not category_id or not role:
        return Response({"error": "Missing fields"}, status=400)

    UserCategoryRole.objects.get_or_create(
        user_id=user_id,
        category_id=category_id,
        role=role
    )
    return Response({"success": True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_role(request):
    user_id = request.data.get("user_id")
    category_id = request.data.get("category_id")
    role = request.data.get("role")

    try:
        obj = UserCategoryRole.objects.get(user_id=user_id, category_id=category_id, role=role)
        obj.delete()
        return Response({"success": True})
    except UserCategoryRole.DoesNotExist:
        return Response({"error": "Not found"}, status=404)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Category

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categories_in_club(request):
    club = request.user.club
    if not club:
        return Response({"error": "Používateľ nemá priradený klub."}, status=400)

    categories = Category.objects.filter(club=club).order_by("name")
    data = [{"id": c.id, "name": c.name} for c in categories]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def coach_players_view(request):
    user = request.user
    coach_roles = UserCategoryRole.objects.filter(user=user, role='coach')
    category_ids = coach_roles.values_list('category_id', flat=True)

    users = User.objects.filter(
        roles__category_id__in=category_ids,
        roles__role='player'
    ).distinct().order_by('last_name')

    result = []
    for u in users:
        user_roles = UserCategoryRole.objects.filter(user=u, role='player', category_id__in=category_ids)
        result.append({
            'id': u.id,
            'name': u.get_full_name(),
            'birth_date': u.birth_date,
            'categories': list(user_roles.values('category__id', 'category__name')),
        })

    return Response(result)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_players_with_roles(request):
    user = request.user
    coach_roles = UserCategoryRole.objects.filter(user=user, role='coach')
    category_ids = coach_roles.values_list('category_id', flat=True)

    users = User.objects.exclude(id=user.id).order_by('-date_joined')

    result = []
    for u in users:
        player_roles = UserCategoryRole.objects.filter(user=u, role='player')
        result.append({
            'id': u.id,
            'name': u.get_full_name(),
            'birth_date': u.birth_date,
            'categories': list(player_roles.values('category__id', 'category__name')),
        })
    return Response(result)