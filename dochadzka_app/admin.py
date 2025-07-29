from pyexpat.errors import messages

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    Club,
    User,
    Category,
    UserCategoryRole,
    Training,
    TrainingAttendance,
    Match,
    MatchParticipation,
    Announcement, ExpoPushToken, Message, MessageReaction,
)


class UserCategoryRoleInline(admin.TabularInline):
    model = UserCategoryRole
    extra = 1  # počet prázdnych riadkov na pridanie
    autocomplete_fields = ['category']
    verbose_name = "Kategória a rola"
    verbose_name_plural = "Kategórie a roly"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (('Doplňujúce údaje'), {'fields': ('club','email_2',
                  'birth_date', 'number','height', 'weight', 'side')}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (('Doplňujúce údaje'), {'fields': ('club','email_2',
                  'birth_date', 'number','height', 'weight', 'side', 'expo_push_token')}),
    )

    list_display = ('id', 'username', 'first_name', 'last_name', 'email', 'club', 'email_2',
                  'birth_date', 'number','height', 'weight', 'side', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'club')

    inlines = [UserCategoryRoleInline]

@admin.register(ExpoPushToken)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('user','token', 'created_at')

@admin.register(Message)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('sender','recipient', 'text', 'timestamp', 'read')

@admin.register(MessageReaction)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'created_at', 'emoji')


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'club')
    list_filter = ('club',)
    search_fields = ('name',)


@admin.register(UserCategoryRole)
class UserCategoryRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'category')
    list_filter = ('role', 'category__club')
    search_fields = ('user__username', 'category__name')


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ('category', 'date', 'description')
    list_filter = ('category__club', 'category')
    search_fields = ('category__name', 'description')


@admin.register(TrainingAttendance)
class TrainingAttendanceAdmin(admin.ModelAdmin):
    list_display = ('training', 'user' )
    search_fields = ('user__username', 'training__category__name')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('category', 'date', 'opponent', 'location')
    list_filter = ('category__club', 'category')
    search_fields = ('category__name', 'opponent', 'location')


@admin.register(MatchParticipation)
class MatchParticipationAdmin(admin.ModelAdmin):
    list_display = ('match', 'user', 'confirmed')
    list_filter = ('confirmed', 'match__category__club')
    search_fields = ('user__username', 'match__category__name')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'club', 'category', 'date_created')
    list_filter = ('club', 'category')
    search_fields = ('title', 'content')
    date_hierarchy = 'date_created'