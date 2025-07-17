from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class Club(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    # Ďalšie polia ako adresa, logo, kontakty, ...

    def __str__(self):
        return self.name


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
    def __str__(self):
        return self.username


class Category(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.club.name})"


class Role(models.TextChoices):
    PLAYER = 'player', 'Hráč'
    COACH = 'coach', 'Tréner'
    PARENT = 'parent', 'Rodič'
    ADMIN = 'admin', 'Admin'




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

