# odstránil som import z allauth.conftest
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import (ClubSerializer, CategorySerializer,
                          UserMeUpdateSerializer, CategorySerializer2, UserCategoryRoleSerializer,
                          MatchParticipationCreateSerializer)

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
        'position': user.position.name if user.position else None,
        'preferred_role': user.preferred_role,
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
from dochadzka_app.tasks import send_training_notifications
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

            send_training_notifications.delay(training.id)
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
    ).distinct().select_related('position').order_by('number')


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
            "position": player.position.name if player.position else None
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


from dochadzka_app.tasks import notify_training_deleted

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_training_view(request, training_id):
    training = get_object_or_404(Training, id=training_id)

    # Over, či používateľ je tréner v tejto kategórii
    is_coach = request.user.roles.filter(category=training.category, role=Role.COACH).exists()
    if not is_coach:
        return Response({"error": "Nemáš oprávnenie na zmazanie tohto tréningu."}, status=403)

    logger.info(f"🗑️ Mazanie tréningu {training.id} – {training.description}")

    # Spusti Celery task na notifikáciu hráčov
    notify_training_deleted.delay(training.id, training.description, training.category.id)

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
                        message=preview,
                        user_id=current_user.id,  # ← ten kto posiela správu
                        user_name=full_name  # ← celé meno
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
from .models import User


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
            "birth_date": u.birth_date,
            "roles": list(roles),
            'position': u.position.name if u.position else None,
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

    obj, created = UserCategoryRole.objects.get_or_create(
        user_id=user_id,
        category_id=category_id,
        role=role
    )

    if created:
        User = get_user_model()
        user = User.objects.get(id=user_id)
        category = Category.objects.get(id=category_id)

        tokens = ExpoPushToken.objects.filter(user=user).values_list("token", flat=True)
        for token in tokens:
            try:
                send_push_notification(
                    token,
                    title="Nová rola priradená",
                    message=f"Bola ti priradená rola '{role}' v kategórii '{category.name}'."
                )
            except Exception as e:
                print(f"❌ Chyba pri notifikácii {user.username}: {e}")

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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def player_trainings_history_view(request):
    user = request.user
    club = user.club

    # Tréningy z aktuálnych kategórií, kde má rolu player
    current_categories = Category.objects.filter(user_roles__user=user, user_roles__role='player')
    trainings_from_roles = Training.objects.filter(
        club=club,
        category__in=current_categories
    )

    # Tréningy, kde má user zaznamenanú dochádzku (aj ak už nemá rolu)
    trainings_from_attendance = Training.objects.filter(
        club=club,
        attendances__user=user
    )

    # Spojíme obe množiny
    all_trainings = (trainings_from_roles | trainings_from_attendance).select_related(
        'category'
    ).prefetch_related(
        'attendances'
    ).order_by('date').distinct()

    serializer = TrainingSerializer(all_trainings, many=True, context={'request': request})
    return Response(serializer.data)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Position
from .serializers import PositionSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def positions_list(request):
    positions = Position.objects.all()
    serializer = PositionSerializer(positions, many=True)
    return Response(serializer.data)


from .serializers import MatchParticipationCreateSerializer

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Match, MatchParticipation


from itertools import chain
from operator import attrgetter
"""
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def player_matches_view(request):
    user = request.user
    try:
        # všetky kategórie, kde má user rolu hráča
        categories = user.roles.filter(role='player').values_list('category_id', flat=True)

        # zápasy z aktuálnych kategórií
        matches = Match.objects.filter(category_id__in=categories)

        # zápasy, kde má user zaznamenanú účasť
        participations = MatchParticipation.objects.filter(user=user).select_related('match')
        participated_matches = Match.objects.filter(
            id__in=participations.values_list('match_id', flat=True)
        )

        # spojíme a odstránime duplicity
        combined = list(chain(matches, participated_matches))
        unique_matches_dict = {match.id: match for match in combined}
        unique_matches = list(unique_matches_dict.values())

        # zoradenie podľa dátumu (novšie prvé)
        sorted_matches = sorted(unique_matches, key=attrgetter('date'), reverse=True)

        serializer = MatchSerializer(sorted_matches, many=True, context={'request': request})
        return Response(serializer.data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)


"""
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def player_matches_view(request):
    user = request.user
    try:
        categories = user.roles.filter(role='player').values_list('category_id', flat=True)

        matches = Match.objects.filter(category_id__in=categories)
        participations = MatchParticipation.objects.filter(user=user).select_related('match')
        participated_matches = Match.objects.filter(id__in=participations.values_list('match_id', flat=True))

        combined = list(chain(matches, participated_matches))

        # Odstránenie duplicít podľa ID
        unique_matches_dict = {match.id: match for match in combined}
        unique_matches = list(unique_matches_dict.values())

        # Zoradenie podľa dátumu zostupne
        sorted_matches = sorted(unique_matches, key=attrgetter('date'), reverse=True)

        serializer = MatchSerializer(sorted_matches, many=True, context={'request': request})

        # ⬅️ pridáme info o locknutí
        club = user.club  # ak má user priamo FK na club
        vote_lock_days = getattr(club, "vote_lock_days", 0)

        return Response({
            "matches": serializer.data,
            "vote_lock_days": vote_lock_days
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def coach_matches_view(request):
    user = request.user
    try:
        categories = user.roles.filter(role='coach').values_list('category_id', flat=True)

        matches = Match.objects.filter(category_id__in=categories)
        participations = MatchParticipation.objects.filter(user=user).select_related('match')
        participated_matches = Match.objects.filter(id__in=participations.values_list('match_id', flat=True))

        combined = list(chain(matches, participated_matches))

        # Odstránenie duplicít podľa ID
        unique_matches_dict = {match.id: match for match in combined}
        unique_matches = list(unique_matches_dict.values())

        # Zoradenie podľa dátumu zostupne
        sorted_matches = sorted(unique_matches, key=attrgetter('date'), reverse=True)

        serializer = MatchSerializer(sorted_matches, many=True, context={'request': request})
        return Response(serializer.data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_match_participation(request):
    serializer = MatchParticipationCreateSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response({'status': 'saved'})
    return Response(serializer.errors, status=400)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .serializers import MatchSerializer,MatchDetailSerializer
from .tasks import notify_match_created, notify_match_deleted,notify_nomination_changed,notify_match_updated
from django.db import transaction


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_match_view(request):
    user = request.user
    club = user.club
    category_ids = request.data.get("category_ids", [])

    if not category_ids:
        return Response({"error": "Pole 'category_ids' je povinné."}, status=400)

    created_matches = []

    try:
        with transaction.atomic():
            for category_id in category_ids:
                match_data = {
                    "date": request.data.get("date"),
                    "location": request.data.get("location"),
                    "opponent": request.data.get("opponent"),
                    "description": request.data.get("description"),
                    "category": category_id,
                }

                serializer = MatchSerializer(data=match_data, context={"request": request})
                serializer.is_valid(raise_exception=True)

                match = serializer.save(club=club)  # ✅ ulož
                created_matches.append(MatchSerializer(match, context={"request": request}).data)  # ✅ bezpečne získaš data

                notify_match_created.delay(match.id)

        return Response(created_matches, status=201)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)

from django.contrib.auth import get_user_model

User = get_user_model()
from django.contrib.auth import get_user_model

User = get_user_model()


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import UserCategoryRole, Category, Role
from django.contrib.auth import get_user_model

User = get_user_model()

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def jersey_numbers_view(request):
    user_club = request.user.club
    categories = Category.objects.filter(club=user_club)

    result = []

    for category in categories:
        player_user_ids = UserCategoryRole.objects.filter(
            category=category,
            role=Role.PLAYER
        ).values_list("user_id", flat=True)

        used_numbers = (
            User.objects
            .filter(id__in=player_user_ids)
            .exclude(number__isnull=True)
            .exclude(number="")
            .values_list("number", flat=True)
        )

        valid_numbers = []
        for n in used_numbers:
            try:
                num = int(n)
                if 1 <= num <= 99:
                    valid_numbers.append(num)
            except ValueError:
                continue

        result.append({
            "category": category.name,
            "used_numbers": sorted(valid_numbers)
        })

    # Ak sa zada query param all=true, vrátime všetky čísla z klubu
    if request.query_params.get("all") == "true":
        used_numbers = (
            User.objects
            .filter(club=user_club)
            .exclude(number__isnull=True)
            .exclude(number="")
            .values_list("number", flat=True)
        )

        valid_numbers = []
        for n in used_numbers:
            try:
                num = int(n)
                if 1 <= num <= 99:
                    valid_numbers.append(num)
            except ValueError:
                continue

        return Response({"all": sorted(valid_numbers)})

    return Response(result)

# views_documents.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import ClubDocument

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def club_documents_view(request):
    documents = ClubDocument.objects.filter(club=request.user.club).order_by('-uploaded_at')
    return Response([
        {
            "id": doc.id,
            "title": doc.title,
            "file": request.build_absolute_uri(doc.file.url),
            "uploaded_at": doc.uploaded_at.strftime("%d.%m.%Y"),
        }
        for doc in documents
    ])


from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import api_view, parser_classes
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from .models import ClubDocument

User = get_user_model()


from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

@api_view(['POST'])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])   # ← použijeme DRF permission
def upload_document(request):
    user = request.user   # ← Django už vyrieši token podľa hlavičky

    file = request.FILES.get('file')
    title = request.POST.get('title')

    if file and title:
        ClubDocument.objects.create(
            club=user.club,
            title=title,
            file=file
        )
        return Response({"detail": "Upload successful"})

    return Response({"detail": "Missing file or title"}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def match_detail_view(request, match_id):
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return Response({"error": "Match not found"}, status=404)

    nominations_exist = MatchNomination.objects.filter(match=match).exists()
    serializer = MatchDetailSerializer(match, context={"nominations_exist": nominations_exist})
    return Response(serializer.data)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from .serializers import MatchParticipantSerializer
from datetime import datetime


# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Match, MatchNomination
from .serializers import MatchNominationSerializer, MatchNominationUpdateSerializer
from django.contrib.auth import get_user_model

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Match, MatchNomination
from .serializers import MatchNominationSerializer
from .tasks import notify_nomination_changed, notify_nomination_removed
from django.db import transaction

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def match_nominations_view(request, match_id):
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return Response({"error": "Zápas neexistuje"}, status=404)

    User = get_user_model()

    if request.method == "GET":
        nominations = MatchNomination.objects.filter(match=match)

        all_players = User.objects.filter(
            roles__category=match.category,
            roles__role='player',
            club=match.club
        ).distinct()

        nominated_user_ids = nominations.values_list("user_id", flat=True)
        nominated_serialized = MatchNominationSerializer(nominations, many=True).data

        non_nominated_players = all_players.exclude(id__in=nominated_user_ids)
        non_nominated_data = [
            {
                "user_id": p.id,
                "name": p.get_full_name() or p.username,
                "number": p.number,
                "birth_date": p.birth_date.strftime("%d.%m.%Y") if p.birth_date else None,
            }
            for p in non_nominated_players
        ]

        return Response({
            "match_id": match.id,
            "location": match.location,
            "date": match.date,
            "nominations": nominated_serialized + non_nominated_data
        })

    elif request.method == "POST":
        data = request.data.get("nominations", [])
        if not isinstance(data, list):
            return Response({"error": "Očakáva sa zoznam nominácií."}, status=400)

        # Staré nominácie pred zmazaním
        old_user_ids = list(MatchNomination.objects.filter(match=match).values_list("user_id", flat=True))

        MatchNomination.objects.filter(match=match).delete()

        new_nominations = []
        starter_ids = []
        sub_ids = []

        for item in data:
            user_id = item["user"]
            is_sub = item.get("is_substitute", False)
            new_nominations.append(MatchNomination(
                match=match,
                user_id=user_id,
                is_substitute=is_sub,
                rating=item.get("rating"),
                goals=item.get("goals", 0),
                plus_minus=item.get("plus_minus", 0),
            ))

            if is_sub:
                sub_ids.append(user_id)
            else:
                starter_ids.append(user_id)

        with transaction.atomic():
            MatchNomination.objects.bulk_create(new_nominations)

        new_user_ids = [item["user"] for item in data]
        removed_ids = list(set(old_user_ids) - set(new_user_ids))

        notify_nomination_changed.delay(match.id, starter_ids + sub_ids)
        if removed_ids:
            notify_nomination_removed.delay(match.id, removed_ids)

        return Response({"success": "Nominácia bola uložená"})
from django.utils import timezone
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def player_nominated_matches_view(request):
    user = request.user

    nominations = MatchNomination.objects.filter(
        user=user,
        match__date__gt=timezone.now(),
        match__club=user.club  # ← ak máš multi-klub systém
    ).select_related("match").distinct()

    results = []
    for nomination in nominations:
        match = nomination.match
        results.append({
            "id": match.id,
            "date": match.date,
            "location": match.location,
            "opponent": match.opponent,
            "category": match.category.id,
            "category_name": match.category.name,
            "description": match.description,
            "is_substitute": nomination.is_substitute,
            "confirmed": nomination.confirmed,
        })

    return Response(results)

# views.py

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])  # ⬅⬅⬅ DÔLEŽITÉ
def match_participation_view(request):
    print("RAW DATA:", request.body)
    print("PARSED DATA:", request.data)

    user = request.user
    match_id = request.data.get("match_id")
    confirmed = request.data.get("confirmed")

    if match_id is None or confirmed is None:
        return Response({"error": "Chýbajú údaje"}, status=400)

    if isinstance(confirmed, str):
        confirmed = confirmed.lower() == 'true'

    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return Response({"error": "Zápas neexistuje"}, status=404)

    nomination, _ = MatchNomination.objects.get_or_create(match=match, user=user)
    nomination.confirmed = confirmed
    nomination.save()

    return Response({"success": "Účasť bola uložená"})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def match_stats_view(request, match_id):
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return Response({"error": "Zápas neexistuje"}, status=404)

    if request.method == "GET":
        nominations = MatchNomination.objects.filter(match=match).select_related('user__userprofile')
        serializer = MatchNominationUpdateSerializer(nominations, many=True)
        return Response(serializer.data)

    if request.method == "POST":
        nominations_data = request.data.get("nominations", [])

        for entry in nominations_data:
            user_id = entry.get("user")
            if not user_id:
                continue  # bezpečnostná kontrola

            try:
                nomination = MatchNomination.objects.get(match=match, user_id=user_id)
                nomination.rating = entry.get("rating")
                nomination.plus_minus = entry.get("plus_minus")
                nomination.goals = entry.get("goals", 0)  # ak používaš
                nomination.save()
            except MatchNomination.DoesNotExist:
                continue  # neukladaj nič novému hráčovi

        return Response({"success": "Štatistiky boli uložené"})


# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db.models.deletion import ProtectedError

from .models import Match

def user_is_admin_or_match_coach(user, category_id: int) -> bool:
    return user.roles.filter(
        Q(role='admin') | Q(role='coach', category_id=category_id)
    ).exists()

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def match_delete_view(request, match_id: int):
    match = get_object_or_404(Match, id=match_id)

    if not user_is_admin_or_match_coach(request.user, match.category_id):
        return Response({"detail": "Nemáš oprávnenie zmazať tento zápas."}, status=403)

    try:
        # pošli všetko, čo budeš potrebovať, lebo zápas sa zmaže
        notify_match_deleted.delay(match.opponent, match.category_id, match.club_id)
        match.delete()
    except ProtectedError:
        return Response(
            {"detail": "Zápas má naviazané dáta (napr. štatistiky/účasti) a nie je možné ho zmazať."},
            status=409
        )

    return Response(status=204)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Training
from .serializers import TrainingUpdateSerializer
from dochadzka_app.tasks import send_training_updated_notification


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def training_update_view(request, training_id):
    try:
        training = Training.objects.get(id=training_id)
    except Training.DoesNotExist:
        return Response({'error': 'Tréning neexistuje'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = TrainingUpdateSerializer(training)
        return Response(serializer.data)

    if request.method == 'PUT':
        serializer = TrainingUpdateSerializer(training, data=request.data)
        if serializer.is_valid():
            serializer.save()

            # ✅ Spusti Celery task na poslanie notifikácie
            send_training_updated_notification.delay(training.id)

            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from .models import User, Category, UserCategoryRole

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def assign_players_to_category(request):
    category_id = request.data.get("category_id")
    player_ids = request.data.get("player_ids", [])

    if not category_id:
        return Response({"error": "category_id je povinný"}, status=400)

    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return Response({"error": "Kategória neexistuje"}, status=404)

    # Získaj všetky existujúce role pre túto kategóriu
    existing_roles = UserCategoryRole.objects.filter(
        category=category,
        role="player"
    )

    existing_user_ids = set(existing_roles.values_list("user_id", flat=True))
    new_user_ids = set(player_ids)

    # Pridaj nových hráčov
    to_add = new_user_ids - existing_user_ids
    for user_id in to_add:
        UserCategoryRole.objects.create(
            user_id=user_id,
            category=category,
            role="player"
        )

    # Odstráň hráčov, ktorí už nemajú byť v kategórii
    to_remove = existing_user_ids - new_user_ids
    UserCategoryRole.objects.filter(
        category=category,
        role="player",
        user_id__in=to_remove
    ).delete()

    return Response({"success": True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_preferred_role(request):
    role = request.data.get("preferred_role")
    if role not in ['player', 'coach', 'admin']:
        return Response({"error": "Invalid role"}, status=400)

    request.user.preferred_role = role
    request.user.save()
    return Response({"success": True})


@api_view(['GET'])
@permission_classes([AllowAny])
def club_detail(request, club_id):
    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        return Response({"error": "Club not found"}, status=404)

    data = {
        "id": club.id,
        "name": club.name,
        "description": club.description,
        "address": club.address,
        "phone": club.phone,
        "email": club.email,
        "contact_person": club.contact_person,
        "iban": club.iban,
    }
    return Response(data)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from .models import User
from .models import TrainingAttendance, Training

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def coach_attendance_summary(request):
    user = request.user
    coach_roles = user.roles.filter(role='coach')

    category_ids = coach_roles.values_list('category__id', flat=True).distinct()
    players = User.objects.filter(roles__category__id__in=category_ids, roles__role='player').distinct()

    result = []
    for player in players:
        player_data = {
            "player_id": player.id,
            "name": f"{player.first_name} {player.last_name}",
            "birth_date": player.birth_date,
            "position": player.position.name if player.position else None,
            "number": player.number,
            "categories": [],
        }

        total_percent = 0.0

        # ✅ Iteruj iba cez kategórie, kde má hráč rolu hráča
        player_category_ids = player.roles.filter(
            role='player',
            category__id__in=category_ids
        ).values_list('category__id', flat=True).distinct()

        for cat_id in player_category_ids:
            trainings = Training.objects.filter(category_id=cat_id)
            total = trainings.count()
            present = TrainingAttendance.objects.filter(
                user=player,
                training__category_id=cat_id,
                status='present'
            ).count()

            if total == 0:
                continue

            percent = round((present / total) * 100, 1)

            player_data['categories'].append({
                'category_id': cat_id,
                'category_name': trainings.first().category.name if trainings.exists() else '',
                'attendance_percentage': percent
            })

            total_percent += percent

        player_data['overall_attendance'] = round(total_percent, 1)
        result.append(player_data)

    return Response(result)


from datetime import date, datetime

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def player_attendance_detail(request, player_id):
    user = request.user
    coach_roles = user.roles.filter(role='coach')
    coach_category_ids = set(coach_roles.values_list('category__id', flat=True))

    try:
        player = User.objects.get(id=player_id)
    except User.DoesNotExist:
        return Response({'error': 'Player not found'}, status=404)

    # kategórie hráča
    player_categories = player.roles.filter(role='player')
    player_category_ids = set(player_categories.values_list('category__id', flat=True))

    # overenie oprávnenia
    if not coach_category_ids.intersection(player_category_ids):
        return Response({'error': 'Unauthorized'}, status=403)

    # 🔥 query params pre filter
    month = request.GET.get('month')   # napr. "0-11"
    season = request.GET.get('season') # napr. "2024/2025"

    season_start, season_end = None, None
    if season:
        try:
            start_year = int(season.split('/')[0])
            season_start = date(start_year, 6, 1)           # 1. jún
            season_end = date(start_year + 1, 5, 31)        # 31. máj
        except Exception:
            pass

    response_data = {
        "player_id": player.id,
        "name": f"{player.first_name} {player.last_name}",
        "number": player.number,
        "birth_date": player.birth_date,
        "email": player.email,
        "email_2": player.email_2,
        "height": player.height,
        "weight": player.weight,
        "side": player.side,
        "position": player.position.name if player.position else None,
        "categories": [],
        "trainings": []
    }

    # pre každú kategóriu hráča, kde tréner má prístup
    for role in player_categories:
        category = role.category
        if category.id not in coach_category_ids:
            continue

        trainings = Training.objects.filter(category=category)

        # aplikuj filter sezóna
        if season_start and season_end:
            trainings = trainings.filter(date__range=(season_start, season_end))

        # aplikuj filter mesiac
        if month is not None and month.isdigit():
            trainings = trainings.filter(date__month=int(month) + 1)  # Django 1-12

        trainings = trainings.order_by('-date')

        total = trainings.count()
        present = TrainingAttendance.objects.filter(user=player, training__in=trainings, status='present').count()
        absent = TrainingAttendance.objects.filter(user=player, training__in=trainings, status='absent').count()
        unknown = total - present - absent

        if total == 0:
            continue

        percent = round((present / total) * 100, 1)

        response_data['categories'].append({
            'category_id': category.id,
            'category_name': category.name,
            'present': present,
            'absent': absent,
            'unknown': unknown,
            'total': total,
            'percentage': percent
        })

        # detail tréningov
        for tr in trainings:
            try:
                attendance = TrainingAttendance.objects.get(user=player, training=tr)
                status = attendance.status
            except TrainingAttendance.DoesNotExist:
                status = "unknown"

            response_data['trainings'].append({
                "id": tr.id,
                "date": tr.date.strftime("%Y-%m-%d"),
                "time": tr.date.strftime("%H:%M"),
                "location": tr.location,
                "category": category.name,
                "status": status,
                "players_present": TrainingAttendance.objects.filter(training=tr, status="present").count(),
                "players_total": TrainingAttendance.objects.filter(training=tr).count(),
            })

    return Response(response_data)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import ClubPaymentSettings, MemberPayment
from .serializers import ClubPaymentSettingsSerializer, MemberPaymentSerializer

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def club_payment_settings_list(request):
    if request.method == 'GET':
        settings = ClubPaymentSettings.objects.all()
        serializer = ClubPaymentSettingsSerializer(settings, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = ClubPaymentSettingsSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import ClubPaymentSettings
from .serializers import ClubPaymentSettingsSerializer


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])  # ← zmenené z IsAdminUser
def club_payment_settings_detail(request, pk):
    setting = get_object_or_404(ClubPaymentSettings, pk=pk)

    if request.method == 'GET':
        serializer = ClubPaymentSettingsSerializer(setting)
        return Response(serializer.data)

    # PUT/DELETE len pre admina
    if not request.user.is_staff:
        return Response({"detail": "Len admin môže upravovať nastavenia."}, status=403)

    if request.method == 'PUT':
        serializer = ClubPaymentSettingsSerializer(setting, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        setting.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def member_payments(request):
    user = request.user
    show_all = request.query_params.get('all') == 'true'

    # Iba ak má rolu admin a chce všetko
    is_admin = user.roles.filter(role="admin").exists()  # uprav podľa svojho modelu

    if show_all and is_admin:
        payments = MemberPayment.objects.all()
    else:
        payments = MemberPayment.objects.filter(user=user)

    serializer = MemberPaymentSerializer(payments, many=True)
    return Response(serializer.data)

from dochadzka_app.tasks import notify_created_member_payment, notify_payment_status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_member_payments(request):
    club = request.user.club
    try:
        settings = ClubPaymentSettings.objects.get(club=club)
    except ClubPaymentSettings.DoesNotExist:
        return Response({"error": "Klub nemá nastavené platobné údaje."}, status=400)

    amount = request.data.get("amount")
    due_date = request.data.get("due_date")
    category_id = request.data.get("category_id")
    user_id = request.data.get("user_id")
    description = request.data.get("description", "")  # <- pridaj túto riadku

    if not amount or not due_date:
        return Response({"error": "Zadaj amount a due_date."}, status=400)

    # výber používateľov
    if user_id:
        users = User.objects.filter(id=user_id, club=club)
    elif category_id:
        user_ids = UserCategoryRole.objects.filter(
            category_id=category_id,
            role='player'
        ).values_list('user_id', flat=True)
        users = User.objects.filter(id__in=user_ids, club=club)
    else:
        users = User.objects.filter(club=club)

    created = []
    for user in users:
        variable_symbol = f"{settings.variable_symbol_prefix}{user.id:04d}"
        payment = MemberPayment.objects.create(
            user=user,
            club=club,
            amount=amount,
            due_date=due_date,
            variable_symbol=variable_symbol,
            is_paid=False,
            description=description  # <- a túto
        )
        notify_created_member_payment.delay(user.id, amount, due_date)
        created.append(payment.id)

    return Response({"created_payments": created}, status=201)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_member_payment(request, pk):
    payment = get_object_or_404(MemberPayment, pk=pk)
    serializer = MemberPaymentSerializer(payment, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['GET', 'PUT'])
@permission_classes([IsAdminUser])
def admin_member_payments(request):
    if request.method == 'GET':
        payments = MemberPayment.objects.select_related('user').filter(club=request.user.club)
        data = [
            {
                "id": p.id,
                "amount": str(p.amount),
                "due_date": p.due_date,
                "is_paid": p.is_paid,
                "description": p.description,
                "variable_symbol": p.variable_symbol,
                "user": {
                    "id": p.user.id,
                    "name": f"{p.user.first_name} {p.user.last_name}".strip() or p.user.username,
                    "username": p.user.username,
                },
            }
            for p in payments
        ]
        return Response(data)

    elif request.method == 'PUT':
        # 🔥 Ak príde zoznam
        if isinstance(request.data, list):
            updated = []
            for item in request.data:
                payment_id = item.get("id")
                is_paid = item.get("is_paid")

                if payment_id is None or is_paid is None:
                    continue

                try:
                    payment = MemberPayment.objects.get(id=payment_id, club=request.user.club)
                    payment.is_paid = is_paid
                    payment.save()
                    notify_payment_status.delay(
                        user_id=payment.user.id,
                        is_paid=is_paid,
                        amount=str(payment.amount),
                        vs=payment.variable_symbol
                    )
                    updated.append(payment_id)
                except MemberPayment.DoesNotExist:
                    continue

            return Response({"success": True, "updated": updated})

        # 🔥 Ak príde iba jeden objekt
        else:
            payment_id = request.data.get("id")
            is_paid = request.data.get("is_paid")

            if payment_id is None or is_paid is None:
                return Response({"error": "Chýbajú údaje."}, status=400)

            try:
                payment = MemberPayment.objects.get(id=payment_id, club=request.user.club)
                payment.is_paid = is_paid
                payment.save()
                notify_payment_status.delay(
                    user_id=payment.user.id,
                    is_paid=is_paid,
                    amount=str(payment.amount),
                    vs=payment.variable_symbol
                )
                return Response({"success": True, "updated": [payment_id]})
            except MemberPayment.DoesNotExist:
                return Response({"error": "Platba neexistuje."}, status=404)


from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.parsers import MultiPartParser
import csv, io


import os
import json
import pdfplumber
from openai import OpenAI
from django.core.files.storage import default_storage
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import MemberPayment

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_pdf_statement_chatgpt(request):
    file = request.FILES.get("file")
    if not file:
        return Response({"error": "Súbor nebol priložený"}, status=400)

    # Uložíme PDF
    file_path = default_storage.save(f"bank_statements/{file.name}", file)
    full_path = default_storage.path(file_path)

    # Načítame text z PDF
    text = ""
    try:
        with pdfplumber.open(full_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        return Response({"error": f"Chyba pri čítaní PDF: {str(e)}"}, status=500)

    if not text.strip():
        return Response({"error": "Výpis z PDF je prázdny alebo nečitateľný."}, status=400)

    # Inicializujeme klienta OpenAI
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        return Response({"error": f"Chyba pri inicializácii OpenAI klienta: {str(e)}"}, status=500)

    # Pripravíme prompt
    prompt = f"""
Toto je výpis z banky. Nájdi všetky prichádzajúce transakcie, ktoré obsahujú:
- variabilný symbol (VS)
- sumu v eurách
- dátum

Vráť to ako **platný JSON zoznam** s kľúčmi: vs, amount, date. Nepridávaj žiaden komentár ani text mimo JSON.

[
  {{
    "vs": "123456",
    "amount": 25.50,
    "date": "2025-08-01"
  }},
  ...
]

Tu je výpis:
{text}
"""

    # Zavoláme AI
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Si expert na bankové transakcie."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=1000
        )

        extracted_data = response.choices[0].message.content.strip()

        # Odstráň markdown kódový blok ak je tam
        if extracted_data.startswith("```") and extracted_data.endswith("```"):
            extracted_data = "\n".join(extracted_data.split("\n")[1:-1]).strip()

        if not extracted_data:
            return Response({
                "error": "AI nevrátilo žiadny obsah.",
                "raw_response": str(response)
            }, status=500)

        try:
            data = json.loads(extracted_data)
        except json.JSONDecodeError as e:
            return Response({
                "error": f"Neplatný JSON z AI: {str(e)}",
                "raw_response": extracted_data
            }, status=500)

        # Spracujeme dáta
        matches = []
        for row in data:
            vs = str(row.get("vs", "")).strip()
            amount = float(str(row.get("amount", "0")).replace(",", "."))
            matched = MemberPayment.objects.filter(
                variable_symbol=vs,
                amount=amount,
                is_paid=False
            ).first()
            if matched:
                matched.is_paid = True
                matched.save()
                notify_payment_status.delay(user_id=matched.user.id, is_paid=True)
                matches.append({"id": matched.id, "vs": vs, "amount": amount})

        return Response({"message": f"Spracovaných: {len(matches)}", "matched": matches})

    except Exception as e:
        return Response({"error": f"Chyba pri spracovaní AI odpovede: {str(e)}"}, status=500)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from .models import Match
from .serializers import MatchSerializer
from .tasks import notify_match_updated


@api_view(['GET', 'PUT', 'PATCH'])  # podporuje načítanie aj úpravu
@permission_classes([IsAuthenticated])
def update_match_view(request, match_id):
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return Response({'error': 'Zápas neexistuje'}, status=404)

    if request.method == 'GET':
        serializer = MatchSerializer(match, context={"request": request})
        return Response(serializer.data)

    # PATCH / PUT – úprava zápasu
    is_authorized = request.user.roles.filter(
        Q(role='coach', category=match.category) | Q(role='admin')
    ).exists()

    if not is_authorized:
        return Response({"error": "Nemáš oprávnenie upraviť tento zápas."}, status=403)

    serializer = MatchSerializer(
        match,
        data=request.data,
        partial=True,
        context={"request": request}
    )

    if serializer.is_valid():
        serializer.save()
        notify_match_updated.delay(match.id)

        # serializuj znova po uložení (kvôli napr. .data a context)
        updated = MatchSerializer(match, context={"request": request})
        return Response(updated.data)

    return Response(serializer.errors, status=400)


from .tasks import remind_unknown_players,notify_match_reminder

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def remind_attendance_view(request):
    training_id = request.data.get("training_id")
    user_ids = request.data.get("user_ids", [])

    if not training_id or not isinstance(user_ids, list):
        return Response({"error": "Neplatné dáta"}, status=400)

    # Spusti Celery task
    remind_unknown_players.delay(training_id, user_ids)

    return Response({"status": "ok", "message": "Pripomienky sa odosielajú."})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remind_match_attendance_view(request):
    match_id = request.data.get("match_id")
    user_ids = request.data.get("user_ids", [])

    if not match_id or not isinstance(user_ids, list):
        return Response({"detail": "Neplatné dáta."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return Response({"detail": "Zápas neexistuje."}, status=status.HTTP_404_NOT_FOUND)

    if not user_is_admin_or_match_coach(request.user, match.category_id):
        return Response({"detail": "Nemáš oprávnenie."}, status=status.HTTP_403_FORBIDDEN)

    notify_match_reminder.delay(match_id, user_ids)
    return Response({"detail": "Notifikácie budú odoslané."})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_member_payments_summary(request):
    if not request.user.club:
        return Response({"error": "Používateľ nemá priradený klub."}, status=400)

    club = request.user.club
    users = User.objects.filter(club=club)

    data = []
    for user in users:
        payments = MemberPayment.objects.filter(user=user)
        all_paid = all(p.is_paid for p in payments)

        data.append({
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}".strip() or user.username,
            "birth_date": user.birth_date,
            "number": user.number,
            "all_payments_paid": all_paid,
        })

    return Response(data)



# views.py
from collections import defaultdict
from django.db.models import Exists, OuterRef
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import User, MemberPayment, UserCategoryRole  # prispôsobiť ceste importov

from collections import defaultdict
from django.db.models import Exists, OuterRef
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import User, MemberPayment, UserCategoryRole


# views.py
from collections import defaultdict
from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import User, MemberPayment, UserCategoryRole


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def new_members_without_payments(request):
    """
    GET /api/new-members-without-payments/?role=player&scope=club|any

    - scope=any (default): vráti členov, ktorí NIKDY nemali žiadnu platbu (v akomkoľvek klube)
    - scope=club: vráti členov, ktorí NIKDY nemali žiadnu platbu v aktuálnom klube

    Výstup má rovnaký tvar ako users_in_club.
    """
    club = getattr(request.user, 'club', None)
    if not club:
        return Response([], status=400)

    scope = request.query_params.get('scope', 'any')  # 'any' | 'club'

    qs = (
        User.objects
        .filter(club=club)
        .select_related('position')
        .order_by('-date_joined')
    )

    # spočítaj platby podľa zvoleného scope
    if scope == 'club':
        qs = qs.annotate(
            payments_count=Count(
                'memberpayment',
                filter=Q(memberpayment__club_id=club.id),
                distinct=True,
            )
        )
    else:  # 'any' (default)
        qs = qs.annotate(
            payments_count=Count('memberpayment', distinct=True)
        )

    # nechceme nikoho, kto už má aspoň jednu platbu
    qs = qs.filter(payments_count=0)

    # voliteľný filter podľa roly (napr. ?role=player)
    role = request.query_params.get('role')
    if role:
        qs = qs.filter(usercategoryrole__role=role).distinct()

    users = list(qs)

    # načítaj roly hromadne (bez N+1)
    role_rows = (
        UserCategoryRole.objects
        .filter(user__in=users)
        .select_related('category')
        .values('user_id', 'role', 'category__id', 'category__name')
    )
    roles_map = defaultdict(list)
    for r in role_rows:
        roles_map[r['user_id']].append({
            'role': r['role'],
            'category__id': r['category__id'],
            'category__name': r['category__name'],
        })

    data = []
    for u in users:
        data.append({
            "id": u.id,
            "username": u.username,
            "name": u.get_full_name(),
            "email": u.email,
            "date_joined": u.date_joined,
            "birth_date": getattr(u, 'birth_date', None),
            "roles": roles_map.get(u.id, []),
            "position": u.position.name if getattr(u, 'position', None) else None,
        })

    return Response(data)


from rest_framework import permissions, status, generics
from rest_framework.response import Response
from .models import Order
from .serializers import OrderSerializer, OrderSerializer2

class OrderCreateView(generics.CreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        # ak máš kontext klubu na userovi, môžeš predvyplniť; tu očakávame club z requestu
        serializer.save(user=user)

class MyOrdersListView(generics.ListAPIView):
    serializer_class = OrderSerializer2
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by("-created_at")

from .models import Order
from .serializers import ClubOrderReadSerializer

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status
from django.shortcuts import get_object_or_404

from rest_framework import status as http_status

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status as http_status
from rest_framework.response import Response

from .models import Order
from .serializers import ClubOrderReadSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])  # v produkcii nahraď vlastnou IsClubAdmin
def club_orders_view(request, club_id: int):
    """
    GET /api/club-orders/<club_id>/?status=Nová
    GET /api/club-orders/<club_id>/?status__in=Nová,Spracováva sa,Objednaná
    """
    # ✅ kontrola, či má user prístup do tohto klubu
    if not request.user.is_superuser:
        if getattr(request.user, "club_id", None) != club_id:
            return Response({"detail": "Forbidden"}, status=http_status.HTTP_403_FORBIDDEN)

    qs = (
        Order.objects.filter(club_id=club_id)
        .select_related("user", "club")
        .prefetch_related("items")
        .order_by("-created_at")
    )

    # 1) ak je zadaný konkrétny status
    status_param = request.query_params.get("status")
    if status_param:
        qs = qs.filter(status=status_param)

    # 2) ak je zadané viac statusov
    status_in_param = request.query_params.get("status__in")
    if status_in_param:
        statuses = [s.strip() for s in status_in_param.split(",") if s.strip()]
        if statuses:
            qs = qs.filter(status__in=statuses)

    ser = ClubOrderReadSerializer(qs, many=True)
    return Response(ser.data, status=http_status.HTTP_200_OK)


# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status
from django.shortcuts import get_object_or_404
from .models import Order,OrderItem
from .serializers import OrderUpdateSerializer
from .tasks import notify_order_paid, notify_order_status_changed

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def order_update_view(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id)
    serializer = OrderUpdateSerializer(order, data=request.data, partial=True)

    if serializer.is_valid():
        order = serializer.save()

        # 🔥 Synchronizácia Order ↔ OrderPayment
        if "is_paid" in request.data:
            if hasattr(order, "payment"):  # ak má už vytvorenú platbu
                order.payment.is_paid = order.is_paid
                if order.is_paid:
                    from django.utils.timezone import now
                    order.payment.paid_at = now()
                    notify_order_paid.delay(order.user.id, str(order.total_amount), str(order.id))
                else:
                    order.payment.paid_at = None
                order.payment.save()
            else:
                # ak ešte nemá platbu, ale označíš ako zaplatenú
                from .models import OrderPayment
                payment = OrderPayment.objects.create(
                    order=order,
                    user=order.user,
                    iban=order.user.iban,
                    variable_symbol=str(order.id),
                    amount=order.total_amount,
                    is_paid=True,
                    paid_at=now(),
                )
                notify_order_paid.delay(order.user.id, str(payment.amount), str(payment.variable_symbol))

        # 🔥 Notifikácia o zmene statusu
        if "status" in request.data:
            notify_order_status_changed.delay(order.user.id, order.status)

        return Response(serializer.data, status=200)
    return Response(serializer.errors, status=400)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status
from django.shortcuts import get_object_or_404
from .models import OrderItem, OrderPayment
from .serializers import OrderItemSerializer, OrderUpdateSerializer, OrderPaymentSerializer, JerseyOrderSerializer


# dochadzka_app/views.py
from .tasks import notify_order_item_canceled  # pridaj import

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_order_item_view(request, item_id: int):
    item = get_object_or_404(OrderItem, pk=item_id)

    if item.order.user != request.user and not request.user.is_superuser:
        return Response({"detail": "Forbidden"}, status=http_status.HTTP_403_FORBIDDEN)

    if item.is_canceled:
        return Response({"detail": "Položka už bola zrušená"}, status=http_status.HTTP_400_BAD_REQUEST)

    item.is_canceled = True
    item.save()

    # 🔔 Push notifikácia pre vlastníka objednávky
    try:
        # bezpečný názov položky
        item_name = item.product_name or item.product_code or item.product_type or "Položka"
        notify_order_item_canceled.delay(
            user_id=item.order.user_id,
            order_id=item.order_id,
            item_name=str(item_name),
            quantity=int(item.quantity or 1),
            order_total=str(item.order.total_amount),
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"notify_order_item_canceled spawn error: {e}")

    try:
        serialized_item = OrderItemSerializer(item)
        print("==> Serializer OK:", serialized_item.data)
    except Exception as e:
        import traceback
        print("==> Serializer ERROR:", str(e))
        traceback.print_exc()
        return Response({"detail": f"Serializer error: {str(e)}"}, status=500)

    return Response({
        "detail": "Položka bola zrušená",
        "item": serialized_item.data,
        "order_total": str(item.order.total_amount),
    }, status=http_status.HTTP_200_OK)




from django.db.models import Q

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def orders_payments(request):
    user = request.user
    show_all = request.query_params.get('all') == 'true'
    is_admin = user.roles.filter(role="admin").exists()

    if show_all and is_admin:
        payments = OrderPayment.objects.all()
    else:
        payments = OrderPayment.objects.filter(
            Q(order__user=user) | Q(jersey_order__user=user)   # 🔥 len jeho vlastné objednávky dresov
        )

    serializer = OrderPaymentSerializer(payments, many=True)
    return Response(serializer.data)
import io
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
import qrcode
from pay_by_square import generate  # funkcia z balíka
from .models import MemberPayment, OrderPayment

def payment_qr(request, payment_type, pk):
    if payment_type == "member":
        payment = get_object_or_404(MemberPayment, pk=pk)
        iban = payment.club.iban
        vs = payment.variable_symbol
        amount = float(payment.amount)
        message = payment.description or "Členský príspevok"
        date = payment.due_date

    elif payment_type == "order":
        payment = get_object_or_404(OrderPayment, pk=pk)
        iban = payment.iban
        vs = payment.variable_symbol
        amount = float(payment.amount)

        if payment.order:
            message = f"Objednávka #{payment.order.id}"
        elif payment.jersey_order:
            message = f"Dresová objednávka #{payment.jersey_order.id}"
        else:
            message = "Objednávka"

        date = None

    else:
        return HttpResponse("Neplatný typ platby", status=400)

    code_string = generate(
        amount=amount,
        iban=iban,
        variable_symbol=vs,
        note=message,
        date=date,
        currency="EUR",
    )

    qr_img = qrcode.make(code_string)
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)
    return HttpResponse(buffer, content_type="image/png")


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Order, OrderPayment
from .tasks import notify_payment_assigned


from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_payment(request, order_id):
    """
    Vygeneruje alebo zaktualizuje platbu pre objednávku.
    IBAN, ktorý sa uloží, bude IBAN používateľa, ktorý túto platbu generuje (request.user).
    """
    order = get_object_or_404(Order, id=order_id)
    recipient = order.user  # vlastník objednávky

    generator = request.user  # kto platbu generuje
    if not getattr(generator, "iban", None):
        return Response({"error": "Generátor platby (request.user) nemá nastavený IBAN v profile"}, status=400)

    # ak chceš zároveň overiť, že len admin / konkrétny role môžu vytvárať platby:
    # if not (generator.is_staff or generator.has_role("admin")):
    #     return Response({"error": "Nemáš oprávnenie generovať platby"}, status=403)

    with transaction.atomic():
        payment, created = OrderPayment.objects.get_or_create(
            order=order,
            defaults={
                # user tu ponechám recipientom (vlastník objednávky),
                "user": recipient,
                # IBAN uložíme generatorov IBAN (ten, kto platbu generuje)
                "iban": generator.iban,
                "variable_symbol": str(order.id),
                "amount": order.total_amount,
                # prípadne ulož info, kto generoval, ak máš také pole:
                # "generated_by": generator,
            },
        )

        # ak už existuje, vždy aktualizujeme IBAN na IBAN generátora
        if not created:
            payment.iban = generator.iban
            payment.amount = order.total_amount
            payment.variable_symbol = str(order.id)
            # ak máš field generated_by, aktualizuj ho tiež:
            # payment.generated_by = generator
            payment.save()

    # notifikácia príjemcovi (vlastníkovi objednávky)
    try:
        notify_payment_assigned.delay(
            user_id=recipient.id,
            amount=str(payment.amount),
            vs=payment.variable_symbol,
            # môžete pridať informáciu kto platbu vytvoril:
            # generated_by_username=generator.username
        )
        logger.info(
            f"Notifikácia: platba {payment.amount}€ (VS {payment.variable_symbol}) "
            f"pre {recipient.username} odoslaná (vytvoril: {generator.username})"
        )
    except Exception as e:
        logger.error(f"Chyba pri spúšťaní notifikácie: {e}")

    return Response({
        "vs": payment.variable_symbol,
        "iban": payment.iban,
        "amount": str(payment.amount),
        "is_paid": payment.is_paid,
        # pridaj info o tom, kto platbu vytvoril
        "generated_by": generator.username,
    })

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def orders_bulk_update(request):
    """
    Uloží viac objednávok naraz.
    Očakáva list objektov: [{id, status, total_amount, is_paid}, ...]
    """
    from django.utils.timezone import now
    data = request.data
    if not isinstance(data, list):
        return Response({"detail": "Očakáva sa zoznam objednávok"}, status=400)

    updated = []
    for entry in data:
        order = get_object_or_404(Order, pk=entry.get("id"))

        # uložíme pôvodné hodnoty pred update
        old_is_paid = getattr(order, "is_paid", False)
        old_status = getattr(order, "status", None)

        serializer = OrderUpdateSerializer(order, data=entry, partial=True)

        if serializer.is_valid():
            order = serializer.save()

            # 🔄 synchronizácia s OrderPayment
            if "is_paid" in entry:
                if hasattr(order, "payment"):
                    order.payment.is_paid = order.is_paid
                    order.payment.paid_at = now() if order.is_paid else None
                    order.payment.save()
                else:
                    from .models import OrderPayment
                    payment, _ = OrderPayment.objects.get_or_create(
                        order=order,
                        defaults={
                            "user": order.user,
                            "iban": order.club.iban if order.club else "",
                            "variable_symbol": str(order.id),
                            "amount": order.total_amount,
                            "is_paid": order.is_paid,
                            "paid_at": now() if order.is_paid else None,
                        },
                    )

                # 🔔 notifikácia IBA ak sa zmenilo na True
                if not old_is_paid and order.is_paid:
                    from .tasks import notify_order_paid
                    notify_order_paid.delay(order.user.id, str(order.total_amount), str(order.id))

            # 🔔 notifikácia IBA ak sa status zmenil
            if "status" in entry and old_status != order.status:
                from .tasks import notify_order_status_changed
                notify_order_status_changed.delay(order.user.id, order.status)

            updated.append(serializer.data)
        else:
            return Response(serializer.errors, status=400)

    return Response(updated, status=200)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Order, JerseyOrder

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def order_delete_view(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id)

    # 🔒 Kontrola – môže zmazať iba vlastník alebo admin
    if request.user != order.user and not request.user.roles.filter(role="admin").exists():
        return Response({"detail": "Nemáš oprávnenie vymazať túto objednávku."}, status=403)

    target_user = order.user
    total_amount = str(order.total_amount)
    order.delete()

    # 🔔 Notifikácia po vymazaní
    try:
        from .tasks import notify_order_deleted
        notify_order_deleted.delay(target_user.id, str(order_id), total_amount)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Chyba pri spúšťaní notify_order_deleted: {e}")

    return Response({"detail": f"Objednávka {order_id} bola vymazaná."}, status=204)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_number(request, club_id, number: int):
    players = User.objects.filter(club_id=club_id, number=number)
    if players.exists():
        return Response({
            "taken": True,
            "players": [
                {"name": p.get_full_name(), "birth_year": p.birth_date.year if p.birth_date else ""}
                for p in players
            ]
        })
    return Response({"taken": False, "players": []})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_jersey_order(request):
    data = request.data.copy()
    data["user"] = request.user.id   # 🔥 priradíme prihláseného usera
    serializer = JerseyOrderSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def jersey_orders_list(request, club_id: int):
    qs = JerseyOrder.objects.filter(club_id=club_id).order_by("-created_at")
    serializer = JerseyOrderSerializer(qs, many=True)
    return Response(serializer.data)



# views.py
from .models import JerseyOrder
from .serializers import JerseyOrderSerializer

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def jersey_order_delete_view(request, order_id: int):
    order = get_object_or_404(JerseyOrder, pk=order_id)

    if not request.user.roles.filter(role="admin").exists():
        return Response({"detail": "Nemáš oprávnenie zmazať túto objednávku."}, status=403)

    order.delete()
    return Response({"detail": f"Objednávka dresu {order_id} bola vymazaná."}, status=204)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def jersey_orders_bulk_update(request):
    """
    Aktualizuje viac objednávok dresov naraz.
    Očakáva list objektov: [{id, amount, is_paid}, ...]
    """
    from django.utils.timezone import now
    data = request.data
    if not isinstance(data, list):
        return Response({"detail": "Očakáva sa zoznam objednávok"}, status=400)

    updated = []
    for entry in data:
        order = get_object_or_404(JerseyOrder, pk=entry.get("id"))

        old_is_paid = order.is_paid

        serializer = JerseyOrderSerializer(order, data=entry, partial=True)
        if serializer.is_valid():
            order = serializer.save()

            # 🔄 synchronizácia s OrderPayment
            if "is_paid" in entry:
                if hasattr(order, "payment"):
                    order.payment.is_paid = order.is_paid
                    order.payment.paid_at = now() if order.is_paid else None
                    order.payment.save()
                else:
                    from .models import OrderPayment
                    payment, _ = OrderPayment.objects.get_or_create(
                        jersey_order=order,
                        defaults={
                            "user": request.user,
                            "iban": request.user.iban if hasattr(request.user, "iban") else "",
                            "variable_symbol": f"J{order.id}",
                            "amount": order.amount,
                            "is_paid": order.is_paid,
                            "paid_at": now() if order.is_paid else None,
                        },
                    )

                # 🔔 notifikácia iba ak sa zmenilo na True
                if not old_is_paid and order.is_paid:
                    from .tasks import notify_order_paid
                    notify_order_paid.delay(order.id, str(order.amount), f"J{order.id}")

            updated.append(order)
        else:
            return Response(serializer.errors, status=400)

    return Response(JerseyOrderSerializer(updated, many=True).data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_jersey_payment(request, order_id):
    order = get_object_or_404(JerseyOrder, id=order_id)

    if not getattr(request.user, "iban", None):
        return Response({"error": "Nemáš nastavený IBAN v profile"}, status=400)

    from .models import OrderPayment
    payment, created = OrderPayment.objects.get_or_create(
        jersey_order=order,
        defaults={
            "user": request.user,
            "iban": request.user.iban,
            "variable_symbol": f"{order.id}",
            "amount": order.amount,
            "is_paid": order.is_paid,
        },
    )

    if not created:
        payment.iban = request.user.iban
        payment.amount = order.amount
        payment.save()

    return Response({
        "vs": payment.variable_symbol,
        "iban": payment.iban,
        "amount": str(payment.amount),
        "is_paid": payment.is_paid,
    })


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from .models import Order
from .serializers import OrderLudimusSerializer

@api_view(["POST"])
@permission_classes([AllowAny])
def create_order(request):
    serializer = OrderLudimusSerializer(data=request.data)
    if serializer.is_valid():
        order = serializer.save()

        # pošli mail adminovi
        subject = f"Nová objednávka balíka ({order.get_plan_display()})"
        message = (
            f"Názov klubu: {order.club_name}\n"
            f"Admin: {order.first_name} {order.last_name}\n"
            f"Email: {order.email}\n"
            f"Telefón: {order.phone}\n"
            f"Balík: {order.get_plan_display()}\n"
            f"Dátum: {order.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_user_from_club(request, user_id: int):
    """
    Vymaže používateľa z klubu (iba admin).
    """
    try:
        user_to_delete = get_object_or_404(User, pk=user_id)

        # kontrola – musí byť v rovnakom klube
        if not request.user.roles.filter(role="admin").exists():
            return Response({"detail": "Nemáš oprávnenie vymazať používateľov."}, status=status.HTTP_403_FORBIDDEN)

        if user_to_delete.club_id != request.user.club_id:
            return Response({"detail": "Používateľ nepatrí do tvojho klubu."}, status=status.HTTP_403_FORBIDDEN)

        user_to_delete.delete()
        return Response({"detail": f"Používateľ {user_to_delete.username} bol vymazaný."}, status=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        return Response({"detail": f"Chyba pri mazaní: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from dochadzka_app.models import Category, Training

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def categories_admin(request):
    """
    GET → vráti zoznam kategórií klubu
    POST → vytvorí novú kategóriu v klube
    """
    user = request.user
    club = user.club

    if request.method == "GET":
        categories = Category.objects.filter(club=club).values("id", "name", "description")
        return Response(categories)

    if request.method == "POST":
        name = request.data.get("name")
        description = request.data.get("description", "")
        if not name:
            return Response({"detail": "Meno kategórie je povinné."}, status=400)

        category = Category.objects.create(club=club, name=name, description=description)
        return Response({"id": category.id, "name": category.name, "description": category.description}, status=201)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_category(request, category_id: int):
    """
    Vymaže kategóriu a všetky tréningy v nej
    """
    user = request.user
    category = get_object_or_404(Category, pk=category_id, club=user.club)

    # pri zmazaní sa cascaduju aj tréningy
    category.delete()

    return Response({"detail": "Kategória a jej tréningy boli vymazané."}, status=204)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_vote_lock_days(request):
    user = request.user
    if not user.roles.filter(role="admin").exists():
        return Response({"detail": "Nemáš oprávnenie."}, status=403)

    days = request.data.get("vote_lock_days")
    try:
        days = int(days)
        if days < 0 or days > 30:
            return Response({"detail": "Neplatný rozsah (0–30 dní)"}, status=400)
    except:
        return Response({"detail": "Neplatná hodnota"}, status=400)

    club = user.club
    club.vote_lock_days = days
    club.save()
    return Response({"vote_lock_days": club.vote_lock_days})



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_training_lock_hours(request):
    user = request.user
    if not user.roles.filter(role="admin").exists():
        return Response({"error": "Unauthorized"}, status=403)

    try:
        hours = int(request.data.get("training_lock_hours"))
    except (TypeError, ValueError):
        return Response({"error": "Neplatná hodnota"}, status=400)

    club = user.club
    club.training_lock_hours = hours
    club.save()

    return Response({"training_lock_hours": club.training_lock_hours})



# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

from .models import Announcement, AnnouncementRead
from .serializers import AnnouncementSerializer, AnnouncementReadSerializer

from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .tasks import send_announcement_notification

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def announcements_list(request):
    """
    Vráti všetky oznamy pre klub používateľa + podľa jeho kategórie (ak má).
    Optimalizované: počty sa rátajú na úrovni DB.
    """
    user = request.user
    if not user.club:
        return Response({"detail": "Používateľ nemá klub"}, status=400)

    # základný queryset
    qs = (
        Announcement.objects.filter(club=user.club)
        .annotate(read_count=Count("reads", distinct=True))
        .select_related("club", "created_by")
        .prefetch_related("categories")  # 🔑 pridaj prefetch na M2M
        .order_by("-date_created")
    )

    if hasattr(user, "roles"):
        user_category_ids = list(user.roles.values_list("category_id", flat=True))
        if user_category_ids:
            qs = qs.filter(
                Q(categories__in=user_category_ids) | Q(categories=None)
            ).distinct()
    # počet userov v klube vyrátame raz
    total_count = user.club.users.count()

    serializer = AnnouncementSerializer(
        qs, many=True, context={"request": request, "total_count": total_count}
    )
    return Response(serializer.data)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_announcement(request):
    """
    Vytvorí nový oznam – admin alebo tréner.
    """
    user = request.user
    if not user.club_id:
        return Response({"detail": "Používateľ nemá priradený klub"}, status=400)

    
    serializer = AnnouncementSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        announcement = serializer.save(
            created_by=user,
            club=user.club   # 🔑 nastavíme explicitne klub
        )
         # 🔑 určíme používateľov ktorým to patrí
        if request.data.get("target") == "club":
            target_users = user.club.users.all()
        else:
            category_ids = request.data.get("categories", [])
            target_users = user.club.users.filter(roles__category_id__in=category_ids).distinct()

        user_ids = list(target_users.values_list("id", flat=True))

        send_announcement_notification.delay(announcement.id, user_ids)


        return Response(
            AnnouncementSerializer(announcement, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )
    else:
        print("❌ Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_announcement_read(request, pk):
    """
    Označí oznam ako prečítaný (uloží alebo updatuje read_at).
    """
    user = request.user
    try:
        announcement = Announcement.objects.get(pk=pk, club=user.club)
    except Announcement.DoesNotExist:
        return Response({"detail": "Oznam neexistuje"}, status=404)

    read, created = AnnouncementRead.objects.update_or_create(
        user=user, announcement=announcement,
        defaults={"read_at": timezone.now()}
    )
    return Response(AnnouncementReadSerializer(read).data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def announcement_readers(request, pk):
    """
    Zoznam používateľov klubu + info kto kedy prečítal.
    Optimalizované cez prefetch.
    """
    ann = get_object_or_404(
        Announcement.objects.prefetch_related("reads__user"),
        pk=pk, club=request.user.club
    )

    # všetci užívatelia v klube
    users = ann.club.users.all().select_related("club")

    # indexujeme reads podľa user.id aby to bolo O(1)
    read_map = {r.user_id: r.read_at for r in ann.reads.all()}

    data = [
        {
            "id": u.id,
            "full_name": f"{u.first_name} {u.last_name}".strip() or u.username,
            "read_at": read_map.get(u.id),
        }
        for u in users
    ]
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def announcements_admin_list(request):
    """
    Admin endpoint – všetky oznamy pre klub s počtom prečítaných a celkovým počtom cieľových používateľov.
    """
    user = request.user
    if not user.club:
        return Response({"detail": "Používateľ nemá klub"}, status=400)

    qs = (
        Announcement.objects.filter(club=user.club)
        .annotate(read_count=Count("reads", distinct=True))
        .select_related("club", "created_by")
        .prefetch_related("categories")
        .order_by("-date_created")
    )

    data = []
    for ann in qs:
        # 🔑 používateľov rátame podľa cieľa
        if ann.categories.exists():
            total_count = (
                request.user.club.users.filter(roles__category__in=ann.categories.all())
                .distinct()
                .count()
            )
        else:
            total_count = request.user.club.users.count()

        data.append(
            AnnouncementSerializer(
                ann, context={"request": request, "total_count": total_count}
            ).data
        )

    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def announcement_admin_readers(request, pk):
    """
    Admin endpoint – zoznam používateľov, ktorí mohli oznam vidieť,
    a info kto kedy prečítal.
    """
    ann = get_object_or_404(
        Announcement.objects.prefetch_related("reads__user", "categories"),
        pk=pk, club=request.user.club
    )

    # ak oznam patrí konkrétnym kategóriám → obmedzíme
    if ann.categories.exists():
        users = ann.club.users.filter(roles__category__in=ann.categories.all()).distinct()
    else:
        users = ann.club.users.all()

    read_map = {r.user_id: r.read_at for r in ann.reads.all()}

    data = [
        {
            "id": u.id,
            "full_name": f"{u.first_name} {u.last_name}".strip() or u.username,
            "read_at": read_map.get(u.id),
        }
        for u in users
    ]
    return Response(data)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django_rest_passwordreset.models import ResetPasswordToken

@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password_confirm_custom(request):
    token = request.data.get("token")
    password = request.data.get("password")

    if not token or not password:
        return Response({"detail": "Chýba token alebo heslo"}, status=400)

    try:
        reset_token = ResetPasswordToken.objects.get(key=token)
    except ResetPasswordToken.DoesNotExist:
        return Response({"detail": "Neplatný alebo expirovaný token"}, status=400)

    # Zmeň heslo používateľovi
    user = reset_token.user
    user.set_password(password)
    user.save()

    # Token odstránime, aby sa nedal znova použiť
    reset_token.delete()

    return Response({"detail": "✅ Heslo bolo úspešne zmenené"})


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    email = request.data.get("email")
    if not email:
        return Response({"detail": "Chýba email"}, status=400)

    users = User.objects.filter(email=email)
    if not users.exists():
        return Response({"detail": "Používateľ s týmto emailom neexistuje"}, status=404)

    # 🔧 tu opravujeme – ak existuje presne 1 používateľ, hneď pošli reset link
    if users.count() == 1:
        user = users.first()
        # Zmaž staré tokeny
        ResetPasswordToken.objects.filter(user=user).delete()
        # Vytvor nový token
        token = ResetPasswordToken.objects.create(user=user)
        # Vytvor odkaz
        reset_url = f"https://ludimus.sk/reset-password?token={token.key}"
        # Pošli e-mail
        user.email_user("🔑 Reset hesla Ludimus", f"Klikni na tento odkaz: {reset_url}")
        return Response({"detail": "Na email bol odoslaný odkaz na reset hesla"})

    else:
        # Viac účtov – treba vybrať konkrétneho používateľa
        accounts = [
            {"id": u.id, "username": u.username, "full_name": f"{u.first_name} {u.last_name}"}
            for u in users
        ]
        return Response({"multiple": True, "accounts": accounts})


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_generate_for_user(request):
    user_id = request.data.get("user_id")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": "Používateľ neexistuje"}, status=404)

    # Zmaž staré tokeny
    ResetPasswordToken.objects.filter(user=user).delete()
    # Vytvor nový token
    token = ResetPasswordToken.objects.create(user=user)
    # Pošli e-mail
    reset_url = f"https://ludimus.sk/reset-password?token={token.key}"
    user.email_user("🔑 Reset hesla Ludimus", f"Klikni na tento odkaz: {reset_url}")

    return Response({"detail": "Reset link bol odoslaný", "token": token.key})


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_coach_categories(request):
    """
    Vráti zoznam kategórií, kde má prihlásený používateľ rolu 'coach'.
    """
    user = request.user
    if not user.club:
        return Response({"detail": "Používateľ nemá priradený klub"}, status=400)

    # predpokladáš, že user.roles je M2M s modelom Role, ktorý má polia role a category
    categories = (
        user.roles.filter(role="coach")
        .select_related("category")
        .values("category__id", "category__name")
    )

    data = [
        {"id": c["category__id"], "name": c["category__name"]}
        for c in categories if c["category__id"] is not None
    ]

    return Response(data)


# views/announcements_admin.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Announcement

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def announcement_delete_view(request, pk: int):
    """
    Zmaže oznam podľa ID (iba admin klubu).
    """
    announcement = get_object_or_404(Announcement, pk=pk)

    # kontrola oprávnenia – napríklad len admin klubu môže zmazať
    if not request.user.roles.filter(role="admin").exists():
        return Response({"detail": "Nemáš oprávnenie zmazať tento oznam."}, status=403)

    announcement.delete()
    return Response({"detail": f"Oznam {pk} bol zmazaný."}, status=204)



from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Formation, FormationLine, FormationPlayer, Category
from .serializers import FormationSerializer, FormationLineSerializer, FormationPlayerSerializer


# ✅ 1. Všetky formácie pre kategóriu
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def formations_by_category(request, category_id):
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return Response({"detail": "Kategória neexistuje"}, status=404)

    if request.method == "GET":
        formations = Formation.objects.filter(category=category)
        serializer = FormationSerializer(formations, many=True)
        return Response(serializer.data)

    if request.method == "POST":
        serializer = FormationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(category=category)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


# ✅ 2. Detail formácie (GET, PUT, DELETE)
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def formation_detail(request, formation_id):
    try:
        formation = Formation.objects.get(id=formation_id)
    except Formation.DoesNotExist:
        return Response({"detail": "Formácia neexistuje"}, status=404)

    if request.method == "GET":
        serializer = FormationSerializer(formation)
        return Response(serializer.data)

    if request.method == "PUT":
        serializer = FormationSerializer(formation, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    if request.method == "DELETE":
        formation.delete()
        return Response({"detail": "Formácia zmazaná"}, status=204)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_line_to_formation(request, formation_id):
    try:
        formation = Formation.objects.get(id=formation_id)
    except Formation.DoesNotExist:
        return Response({"detail": "Formácia neexistuje"}, status=404)

    # automaticky určíme číslo päťky
    existing_count = formation.lines.count()
    new_number = existing_count + 1

    serializer = FormationLineSerializer(data={"number": new_number})
    if serializer.is_valid():
        serializer.save(formation=formation)
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

# ✅ 4. Pridanie alebo úprava hráča v päťke
@api_view(["POST", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def formation_player_manage(request, line_id):
    try:
        line = FormationLine.objects.get(id=line_id)
    except FormationLine.DoesNotExist:
        return Response({"detail": "Päťka neexistuje"}, status=404)

    if request.method == "POST":
        serializer = FormationPlayerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(line=line)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    if request.method == "PUT":
        try:
            player_id = request.data.get("id")
            player = FormationPlayer.objects.get(id=player_id, line=line)
        except FormationPlayer.DoesNotExist:
            return Response({"detail": "Hráč v tejto päťke neexistuje"}, status=404)

        serializer = FormationPlayerSerializer(player, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    if request.method == "DELETE":
        player_id = request.data.get("id")
        FormationPlayer.objects.filter(id=player_id, line=line).delete()
        return Response({"detail": "Hráč odstránený"}, status=204)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User



from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Category, UserCategoryRole

User = get_user_model()

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def players_in_category(request, category_id):
    """
    Vráti všetkých hráčov (role='player') v danej kategórii.
    """
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return Response({"detail": "Kategória neexistuje"}, status=status.HTTP_404_NOT_FOUND)

    # nájdi používateľov s rolou 'player' v danej kategórii
    roles = UserCategoryRole.objects.filter(category=category, role="player").select_related("user", "user__position")

    players = []
    for r in roles:
        u = r.user
        players.append({
            "id": u.id,
            "name": f"{u.first_name} {u.last_name}".strip() or u.username,
            "number": u.number,
            "position": u.position.name if u.position else None,
            "birth_date": u.birth_date,
        })

    return Response(players, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def formation_with_attendance(request, category_id, training_id):
    """
    Vráti formácie + info o hráčoch s farbou podľa dochádzky.
    """
    from .serializers import FormationSerializer
    from .models import TrainingAttendance, Formation

    try:
        formations = Formation.objects.filter(category_id=category_id)
    except Formation.DoesNotExist:
        return Response({"detail": "Kategória neexistuje"}, status=404)

    # načítaj všetky attendance pre daný tréning
    attendances = TrainingAttendance.objects.filter(training_id=training_id)
    attendance_map = {a.user_id: a.status for a in attendances}

    serializer = FormationSerializer(formations, many=True)
    data = serializer.data

    # doplň status hráčov
    for formation in data:
        for line in formation["lines"]:
            for player in line["players"]:
                user_id = player["player"]
                status = attendance_map.get(user_id, "unanswered")
                player["attendance_status"] = status

    return Response(data)
