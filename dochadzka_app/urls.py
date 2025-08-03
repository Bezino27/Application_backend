from django.urls import path

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (me_view, login_view, save_expo_push_token, register_user, chat_users_list,
                    coach_players_attendance_view,
                    get_categories, player_trainings_view, add_reaction, delete_training_view, training_attendance_view,
                    set_training_attendance, list_clubs, test_push, create_training_view, user_categories_view,
                    training_detail_view, coach_trainings_view, change_password_view, chat_messages_view,
                    users_in_club, assign_role, remove_role, categories_in_club, coach_players_view,
                    all_players_with_roles, player_trainings_all_view)

app_name = 'dochadzka_app'

urlpatterns = [
    path('me/', me_view, name='me'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('login/', login_view, name="login"),
    path('categories/<int:club_id>/', get_categories, name='get_categories'),
    path('player-trainings/', player_trainings_view, name='player_trainings'),
    path('set-training-attendance/', set_training_attendance, name='set_training_attendance'),
    path("trainings/", create_training_view, name="create-training"),
    path("user-categories/", user_categories_view),
    path('training-detail/<int:training_id>/', training_detail_view, name='training-detail'),
    path("save-token/", save_expo_push_token),
    path('test-push/', test_push),
    path("training/<int:training_id>/", delete_training_view),
    path("training-attendance/<int:training_id>/", training_attendance_view),
    path('coach-players-attendance/', coach_players_attendance_view),
    path('coach-trainings/', coach_trainings_view),
    path('change-password/', change_password_view),
    path('register/', register_user),
    path('clubs/', list_clubs),
    path('chat/<int:user_id>/', chat_messages_view, name='chat-messages'),
    path("chat-users/", chat_users_list),
    path("chat/<int:message_id>/react/", add_reaction, name="add-reaction"),
    path('users-in-club/', users_in_club),
    path('assign-role/', assign_role),
    path('remove-role/', remove_role),
    path('categories-in-club/', categories_in_club),
    path('categories-in-club/', coach_players_view),
    path('categories-in-club/', all_players_with_roles),
    path('categories-in-clubaaa/', all_players_with_roles),
    path("trainings/all/", player_trainings_all_view, name="player-trainings-all"),

]