from django.urls import path

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (me_view, login_view, RegisterView, save_expo_push_token, coach_players_attendance_view,
                    get_categories, player_trainings_view, delete_training_view, training_attendance_view,
                    set_training_attendance, test_push, create_training_view, user_categories_view,
                    training_detail_view, coach_trainings_view)

app_name = 'dochadzka_app'

urlpatterns = [
    path('me/', me_view, name='me'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='register'),
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

]