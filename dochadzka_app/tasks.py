# tasks.py
from celery import shared_task
from .models import Training
from .models import User, Role
from .helpers import send_push_notification  # uprav podľa tvojej štruktúry
from .models import ExpoPushToken  # uprav podľa tvojej štruktúry
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_training_notifications(training_id):
    try:
        training = Training.objects.get(id=training_id)
    except Training.DoesNotExist:
        logger.warning(f"Tréning s ID {training_id} neexistuje")
        return

    players = User.objects.filter(
        roles__category=training.category,
        roles__role=Role.PLAYER
    ).distinct()

    for player in players:
        tokens = ExpoPushToken.objects.filter(user=player).values_list("token", flat=True)
        for token in tokens:
            try:
                send_push_notification(
                    token,
                    "Nový tréning",
                    f"{training.description} - {training.date.strftime('%d.%m.%Y %H:%M')} v {training.location}",
                    user_id=0,
                    user_name="tréning"
                )
                logger.info(f"Push pre {player.username} → {token}")
            except Exception as e:
                logger.warning(f"Chyba pri push pre {player.username} → {token}: {str(e)}")