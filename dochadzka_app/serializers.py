from rest_framework import serializers
from .models import User, Club, Category, UserCategoryRole, Training, OrderPayment, JerseyOrder, Order_Ludimus
from django.utils.timezone import localtime

class ClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = '__all__'



class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'  # alebo ['id', 'name'] ak chceš obmedziť


class UserCategoryRoleSerializer(serializers.ModelSerializer):
    category = CategorySerializer(allow_null=True)
    role = serializers.CharField()  # ✅ zachová raw hodnotu ako "player", "coach", ...
    role_display = serializers.CharField(source='get_role_display')  # ak chceš aj čitateľný názov
    class Meta:
        model = UserCategoryRole
        fields = ['category', 'role','role_display']


from datetime import timedelta
from django.utils.timezone import now

class UserMeSerializer(serializers.ModelSerializer):
    club = ClubSerializer()
    roles = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    is_new = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'club',
                  'roles', 'categories', 'email_2', 'birth_date', 'number',
                  'height', 'weight', 'side', 'is_new', 'position', 'iban']

    def get_roles(self, obj):
        roles = UserCategoryRole.objects.filter(user=obj)
        return UserCategoryRoleSerializer(roles, many=True).data

    def get_categories(self, obj):
        return list(
            UserCategoryRole.objects
            .filter(user=obj)
            .values_list('category__name', flat=True)
            .distinct()
        )

    def get_is_new(self, obj):
        return obj.date_joined >= now() - timedelta(days=2)
class UserMeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'username',
            'email', 'email_2',
            'birth_date', 'number',
            'height', 'weight', 'side','position', 'iban'
        ]


# serializers.py
from rest_framework import serializers
from .models import Training, TrainingAttendance

class TrainingAttendanceSummarySerializer(serializers.Serializer):
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    unknown = serializers.IntegerField()

class TrainingSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    attendance_summary = serializers.SerializerMethodField()
    user_status = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    def get_date(self, obj):
        return obj.date.isoformat()

    class Meta:
        model = Training
        fields = ['id', 'description', 'date', 'location', 'category',
                  'category_name', 'attendance_summary', 'user_status']

    from django.contrib.auth import get_user_model
    User = get_user_model()

    def get_attendance_summary(self, obj):
        from collections import Counter

        present = 0
        absent = 0
        goalies = 0

        for att in obj.attendances.all():
            if att.status == 'present':
                present += 1

                position_name = (
                    att.user.position.name
                    if att.user and att.user.position
                    else None
                )
                if position_name and position_name.lower() == 'brankár':
                    goalies += 1

            elif att.status == 'absent':
                absent += 1

        player_count = self.User.objects.filter(
            roles__category=obj.category,
            roles__role='player'
        ).distinct().count()

        unknown = max(player_count - (present + absent), 0)

        return {
            'present': present - goalies,
            'goalies': goalies,
            'absent': absent,
            'unknown': unknown,
        }

    def get_user_status(self, obj):
        user = self.context.get('request').user
        attendance = obj.attendances.filter(user=user).first()
        return attendance.status if attendance else "unknown"

class TrainingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Training
        fields = ['category', 'date', 'description', 'location']



class CategorySerializer2(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']



from rest_framework import serializers
from .models import Message, MessageReaction
from django.contrib.auth import get_user_model
User = get_user_model()

class MessageReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageReaction
        fields = ['id', 'user', 'emoji', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()
    reaction = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'sender',
            'recipient',
            'text',
            'timestamp',
            'sender_name',
            'recipient_name',
            'reaction',
        ]

    def get_sender_name(self, obj):
        return f"{obj.sender.first_name} {obj.sender.last_name}".strip()

    def get_recipient_name(self, obj):
        return f"{obj.recipient.first_name} {obj.recipient.last_name}".strip()

    def get_reaction(self, obj):
        user = self.context['request'].user
        reaction = obj.reactions.filter(user=user).first()
        return reaction.emoji if reaction else None

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


from rest_framework import serializers
from .models import Position

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'name']


# serializers.py
from rest_framework import serializers
from .models import Match, MatchParticipation

from rest_framework import serializers
from .models import Match, MatchParticipation


from .models import MatchNomination  # ak ešte nemáš import

class MatchSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source='category.name', read_only=True)
    club_name = serializers.CharField(source='club.name', read_only=True)
    user_status = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    plus_minus = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            'id', 'date', 'club_name', 'location', 'opponent',
            'description', 'category', 'category_name', 'user_status',
            'rating', 'plus_minus',  # ⬅️ pridaj sem
        ]

    def get_user_status(self, obj):
        user = self.context['request'].user
        participation = obj.participations.filter(user=user).first()
        if participation:
            return 'confirmed' if participation.confirmed else 'declined'
        return 'unknown'

    def get_rating(self, obj):
        user = self.context['request'].user
        nomination = MatchNomination.objects.filter(match=obj, user=user).first()
        return nomination.rating if nomination else None

    def get_plus_minus(self, obj):
        user = self.context['request'].user
        nomination = MatchNomination.objects.filter(match=obj, user=user).first()
        return nomination.plus_minus if nomination else None
from rest_framework import serializers
from datetime import timedelta
from django.utils import timezone
from .models import MatchParticipation

class MatchParticipationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchParticipation
        fields = ['match', 'confirmed']

    def validate(self, data):
        match = data.get('match')
        if match.date - timezone.now() < timedelta(days=2):
            raise serializers.ValidationError("Účasť sa dá meniť najneskôr 2 dni pred zápasom.")
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        participation, _ = MatchParticipation.objects.update_or_create(
            user=user,
            match=validated_data['match'],
            defaults={'confirmed': validated_data['confirmed'], 'club': user.club}
        )
        return participation


class MatchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = ['description', 'location', 'opponent', 'date', 'category']


from rest_framework import serializers
from .models import ClubDocument

class ClubDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubDocument
        fields = ['id', 'title', 'file', 'club', 'uploaded_at']


from rest_framework import serializers
from .models import Match, MatchParticipation
from django.contrib.auth import get_user_model

User = get_user_model()

class MatchParticipantSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source="user.id")
    name = serializers.SerializerMethodField()
    number = serializers.CharField(source="user.number", allow_blank=True)
    birth_date = serializers.SerializerMethodField()
    confirmed = serializers.BooleanField()

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_birth_date(self, obj):
        birth = obj.user.birth_date
        return birth.strftime("%d.%m.%Y") if birth else None

class MatchDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    players_present = serializers.SerializerMethodField()
    players_absent = serializers.SerializerMethodField()
    players_unknown = serializers.SerializerMethodField()
    nominations_created = serializers.SerializerMethodField()
    nominations = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id", "category", "category_name", "date", "location", "opponent", "description",
            "players_present", "players_absent", "players_unknown",
            "nominations_created", "nominations"
        ]

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_players_present(self, match):
        qs = match.participations.filter(confirmed=True).select_related("user")
        return MatchParticipantSerializer(qs, many=True).data

    def get_players_absent(self, match):
        qs = match.participations.filter(confirmed=False).select_related("user")
        return MatchParticipantSerializer(qs, many=True).data

    def get_players_unknown(self, match):
        category = match.category
        User = get_user_model()
        users_in_category = User.objects.filter(
            roles__category=category,
            roles__role="player",
            club=match.club
        ).distinct()

        confirmed_ids = match.participations.values_list("user_id", flat=True)
        unknown_users = users_in_category.exclude(id__in=confirmed_ids)

        return [
            {
                "user_id": user.id,
                "name": user.get_full_name() or user.username,
                "number": user.number,
                "birth_date": user.birth_date.strftime("%d.%m.%Y") if user.birth_date else None,
                "confirmed": None,
            }
            for user in unknown_users
        ]

    def get_nominations_created(self, obj):
        return self.context.get("nominations_exist", False)

    def get_nominations(self, obj):
        if self.context.get("nominations_exist"):
            nominations = MatchNomination.objects.filter(match=obj)
            return MatchNominationSerializer(nominations, many=True).data
        return []
from rest_framework import serializers
from .models import MatchNomination

class MatchNominationSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id")
    name = serializers.SerializerMethodField()
    number = serializers.SerializerMethodField()
    birth_date = serializers.SerializerMethodField()

    class Meta:
        model = MatchNomination
        fields = [
            "user_id", "is_substitute", "rating", "goals", "plus_minus",
            "name", "number", "birth_date", "confirmed",  # <- nové pole
        ]

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_number(self, obj):
        return obj.user.number

    def get_birth_date(self, obj):
        return obj.user.birth_date.strftime("%d.%m.%Y") if obj.user.birth_date else None


# serializers.py
class MatchNominationUpdateSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    birth_date = serializers.DateField(source='user.userprofile.birth_date', read_only=True)

    class Meta:
        model = MatchNomination
        fields = ['user', 'user_name', 'birth_date', 'is_substitute', 'rating', 'plus_minus']

from rest_framework import serializers
from .models import Training

class TrainingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Training
        fields = ['id', 'description', 'location', 'date']  # alebo aj 'category', ak chceš meniť


from rest_framework import serializers
from .models import ClubPaymentSettings, MemberPayment

class ClubPaymentSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubPaymentSettings
        fields = '__all__'

class MemberPaymentSerializer(serializers.ModelSerializer):
    iban = serializers.SerializerMethodField()

    class Meta:
        model = MemberPayment
        fields = '__all__'

    def get_iban(self, obj):
        return obj.user.club.iban if obj.user and obj.user.club else None

from rest_framework import serializers
from decimal import Decimal
from .models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id", "product_type", "product_name", "product_code",
            "side", "height", "size", "quantity", "unit_price", "note",
            "line_total","is_canceled"
        ]

    def get_line_total(self, obj):
        return (obj.unit_price or Decimal("0")) * obj.quantity

class OrderSerializer2(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "user", "club", "status", "is_paid", "note", "created_at",
            "total_amount", "items",
        ]
        read_only_fields = ["status", "created_at"]




class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    total_amount = serializers.SerializerMethodField()     # ← NOVÉ

    class Meta:
        model = Order
        fields = [
            "id", "user", "club", "status", "is_paid", "note", "created_at",
            "total_amount", "items",
        ]
        read_only_fields = ["status", "created_at"]

    def get_total_amount(self, obj):
        return sum((it.unit_price or 0) * it.quantity for it in obj.items.all())

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = Order.objects.create(**validated_data)
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
        return order




from rest_framework import serializers
from decimal import Decimal
from .models import Order, OrderItem

class ClubOrderItemReadSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id", "product_type", "product_name", "product_code",
            "side", "height", "size", "quantity", "unit_price", "note",
            "line_total",
        ]

    def get_line_total(self, obj):
        unit = obj.unit_price or Decimal("0")
        return unit * (obj.quantity or 0)



# UPDATE (pre PATCH)
class ClubOrderItemUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    quantity = serializers.IntegerField(min_value=1, required=False)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

# serializers.py
from rest_framework import serializers
from .models import Order

from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from .models import Order, OrderPayment

class OrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["status", "is_paid", "note", "total_amount"]

    def update(self, instance, validated_data):
        amount_changed = "total_amount" in validated_data
        paid_changed = "is_paid" in validated_data

        # Najprv ulož objednávku
        instance = super().update(instance, validated_data)

        payment = getattr(instance, "payment", None)

        # Ak sa zmenila suma a platba existuje, udrž ju v synchre (aj keď ešte nie je zaplatená)
        if amount_changed and payment:
            payment.amount = instance.total_amount
            payment.save(update_fields=["amount"])

        # Ak sa zmenil is_paid, zosynchronizuj OrderPayment
        if paid_changed:
            if payment:
                payment.is_paid = instance.is_paid
                payment.paid_at = timezone.now() if instance.is_paid else None
                # pre istotu zosúladíme aj ďalšie polia
                if getattr(instance.user, "iban", None):
                    payment.iban = instance.user.iban
                payment.amount = instance.total_amount
                payment.variable_symbol = str(instance.id)
                payment.save()
            else:
                # platba ešte neexistuje – vytvor ju len ak je objednávka označená ako zaplatená
                if instance.is_paid:
                    iban = getattr(instance.user, "iban", None)
                    if not iban:
                        # Bez IBANu nebudeme vytvárať "zaplatenú" platbu
                        raise serializers.ValidationError({
                            "is_paid": "Používateľ nemá nastavený IBAN v profile – najprv ho ulož v profile."
                        })
                    OrderPayment.objects.create(
                        order=instance,
                        user=instance.user,
                        iban=iban,
                        variable_symbol=str(instance.id),
                        amount=instance.total_amount or Decimal("0.00"),
                        is_paid=True,
                        paid_at=timezone.now(),
                    )

        return instance


class ClubOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = "__all__"

class ClubOrderReadSerializer(serializers.ModelSerializer):
    items = ClubOrderItemSerializer(many=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()
    class Meta:
        model = Order
        fields = "__all__"


# serializers.py
class OrderPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderPayment
        fields = ["id", "order","jersey_order",
                "user", "iban", "variable_symbol", "amount", "is_paid", "created_at", "paid_at"]



class JerseyOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = JerseyOrder
        fields = "__all__"


from rest_framework import serializers
from .models import Order

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order_Ludimus
        fields = ["id", "club_name", "first_name", "last_name", "email", "phone", "plan", "created_at"]
        read_only_fields = ["id", "created_at"]
