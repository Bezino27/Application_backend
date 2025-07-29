from rest_framework import serializers
from .models import User, Club, Category, UserCategoryRole, Training
from django.utils.timezone import localtime

class ClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['id', 'name', 'description']



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


class UserMeSerializer(serializers.ModelSerializer):
    club = ClubSerializer()
    roles = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'club', 'roles', 'categories','email_2',
                  'birth_date', 'number','height', 'weight', 'side']

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

class UserMeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'username',
            'email', 'email_2',
            'birth_date', 'number',
            'height', 'weight', 'side'
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
        fields = ['id', 'description', 'date','location', 'category', 'category_name', 'attendance_summary', 'user_status']

    from django.contrib.auth import get_user_model
    User = get_user_model()

    def get_attendance_summary(self, obj):
        present = 0
        absent = 0

        for att in obj.attendances.all():
            if att.status == 'present':
                present += 1
            elif att.status == 'absent':
                absent += 1

        # zistíme počet hráčov v kategórii (prefetchovaný queryset by nebol efektívny)
        player_count = User.objects.filter(
            roles__category=obj.category,
            roles__role='player'
        ).distinct().count()

        unknown = max(player_count - (present + absent), 0)

        return {
            'present': present,
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
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    recipient_name = serializers.CharField(source='recipient.username', read_only=True)
    reactions = MessageReactionSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'recipient', 'text', 'timestamp', 'read', 'sender_name', 'recipient_name', 'reactions']



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


