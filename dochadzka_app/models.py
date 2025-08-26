from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class Club(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    address = models.CharField(max_length=255, blank=True, null=True)
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    phone = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    iban = models.CharField(max_length=34, blank=True, null=True)

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    PLAYER = 'player', 'Hráč'
    COACH = 'coach', 'Tréner'
    PARENT = 'parent', 'Rodič'
    ADMIN = 'admin', 'Admin'

class User(AbstractUser):
    # Môžeš sem pridať ďalšie polia, ak chceš (napr. telefón, avatar...)
    club = models.ForeignKey(Club,on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    # Poznámka: tu je každý user priradený k jednému klubu
    # Dodatočné polia:
    birth_date = models.DateField(null=True, blank=True)
    number = models.CharField(max_length=10, blank=True)  # číslo na drese
    height = models.CharField(max_length=10, blank=True)  # výška napr. "180 cm"
    weight = models.CharField(max_length=10, blank=True)  # váha napr. "75 kg"
    side = models.CharField(max_length=10, blank=True)    # napr. "ľavá", "pravá"
    email_2 = models.EmailField(null=True, blank=True)    # druhý email
    position = models.ForeignKey('Position', on_delete=models.SET_NULL, null=True, blank=True)
    preferred_role = models.CharField(max_length=20, null=True, blank=True, choices=Role.choices)
    def __str__(self):
        return self.username

class ExpoPushToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expo_tokens")
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} – {self.token[:15]}..."

class Category(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.club.name})"






class Training(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='trainings')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='trainings')
    date = models.DateTimeField()
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Tréning {self.category.name} - {self.date.strftime('%Y-%m-%d %H:%M')}"





class Match(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='matches')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='matches')
    date = models.DateTimeField()
    opponent = models.CharField(max_length=100)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"Zápas {self.category.name} vs {self.opponent} - {self.date.strftime('%Y-%m-%d %H:%M')}"

class UserCategoryRole(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='roles')  # oprava
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='user_roles')
    role = models.CharField(max_length=10, choices=Role.choices)

    class Meta:
        unique_together = ('user', 'category', 'role')

    def __str__(self):
        return f"{self.user.username} - {self.role} - {self.category.name}"


class AttendanceStatus(models.TextChoices):
    PRESENT = 'present', 'Príde'
    ABSENT = 'absent', 'Nepríde'
    UNANSWERED = 'unanswered', 'Nezodpovedané'

class TrainingAttendance(models.Model):
    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='attendances')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='training_attendances')
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices, default=AttendanceStatus.UNANSWERED)

    class Meta:
        unique_together = ('training', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()} - {self.training}"

class MatchParticipation(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='participations')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='participations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='match_participations')  # oprava
    confirmed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('match', 'user')

    def __str__(self):
        return f"{self.user.username} - {'potvrdený' if self.confirmed else 'nepotvrdený'} - {self.match}"

class Announcement(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='announcements')
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        scope = self.category.name if self.category else self.club.name
        return f"Oznámenie pre {scope} - {self.title}"



from django.conf import settings  # ← dôležité
from django.db import models

class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_messages', on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"From {self.sender} to {self.recipient}: {self.text[:20]}"





class MessageReaction(models.Model):
    message = models.ForeignKey("Message", on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10)  # napr. "👍", "❤️"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')  # 1 reakcia na 1 správu od jedného usera


from django.db import models

class Position(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

# models.py
from django.db import models

class ClubDocument(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} – {self.club.name}"

class MatchNomination(models.Model):
    match = models.ForeignKey(Match, related_name="nominations", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_substitute = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)  # neskôr
    goals = models.PositiveSmallIntegerField(default=0)
    plus_minus = models.SmallIntegerField(default=0)
    confirmed = models.BooleanField(null=True, blank=True)  # None = nereagoval, True/False = odpovedal
    class Meta:
        unique_together = ('match', 'user')

from django.db import models
from django.contrib.auth import get_user_model

class PaymentCycle(models.TextChoices):
    MONTHLY = 'monthly', 'Mesačný'
    QUARTERLY = 'quarterly', 'Štvrťročný'
    HALF_YEAR = 'half_year', 'Polročný'
    SEASONAL = 'seasonal', 'Celosezónny'

class ClubPaymentSettings(models.Model):
    club = models.OneToOneField(Club, on_delete=models.CASCADE)
    iban = models.CharField(max_length=34)
    variable_symbol_prefix = models.CharField(max_length=10, blank=True)
    payment_cycle = models.CharField(max_length=20, choices=PaymentCycle.choices)
    due_day = models.PositiveSmallIntegerField(default=10)  # deň v mesiaci

class MemberPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    due_date = models.DateField()
    variable_symbol = models.CharField(max_length=20)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True, default="")  # ← nový stĺpec

    def __str__(self):
        return f"{self.user} – {self.amount} € – VS: {self.variable_symbol}"


