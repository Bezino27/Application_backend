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
                    "Nový Tréning",
                    f"{training.description} - {training.date.strftime('%d.%m.%Y')} v {training.location}",
                    user_id=0,
                    user_name="tréning"
                )
                logger.info(f"Push pre {player.username} → {token}")
            except Exception as e:
                logger.warning(f"Chyba pri push pre {player.username} → {token}: {str(e)}")


@shared_task
def notify_training_deleted(training_id, training_description, category_id):
    from .models import User, Role, ExpoPushToken, Category

    try:
        category = Category.objects.get(id=category_id)
        players = User.objects.filter(
            roles__category=category,
            roles__role=Role.PLAYER
        ).distinct()

        for player in players:
            tokens = ExpoPushToken.objects.filter(user=player).values_list("token", flat=True)
            for token in tokens:
                try:
                    send_push_notification(
                        token,
                        "Zrušený tréning",
                        f"Tréning '{training_description}' bol zrušený.",
                        user_id=0,
                        user_name="tréning"
                    )
                except Exception as e:
                    logger.warning(f"Chyba pri push pre {player.username} → {token}: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Chyba pri notifikovaní o zmazaní tréningu: {str(e)}")

@shared_task
def send_match_notifications(match_id):
    from .models import Match
    match = Match.objects.get(id=match_id)

    players = User.objects.filter(
        roles__category=match.category,
        roles__role=Role.PLAYER
    ).distinct()

    for player in players:
        send_push_notification(player, f"Nový zápas: {match.opponent}", f"{match.location} ")


@shared_task
def send_training_updated_notification(training_id):
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
                    "Zmena tréningu!",
                    f"{training.description} - {training.date.strftime('%d.%m.%Y')} v {training.location}",
                    user_id=0,
                    user_name="tréning"
                )
                logger.info(f"Notifikácia o zmene tréningu pre {player.username} → {token}")
            except Exception as e:
                logger.warning(f"Chyba pri notifikácii pre {player.username} → {token}: {str(e)}")


# dochadzka_app/tasks.py
from celery import shared_task
from .models import Match, MatchNomination, ExpoPushToken, User
from .helpers import send_push_notification
from django.utils.timezone import localtime

def get_tokens(users):
    return ExpoPushToken.objects.filter(user__in=users).values_list("token", flat=True)

@shared_task
def notify_match_created(match_id):
    try:
        match = Match.objects.get(id=match_id)
        users = User.objects.filter(
            roles__category=match.category,
            roles__role='player',
            club=match.club
        ).distinct()
        tokens = get_tokens(users)

        date_str = localtime(match.date).strftime("%d.%m.%Y %H:%M")
        for token in tokens:
            send_push_notification(
                token,
                title="📅 Nový zápas",
                message=f"Proti {match.opponent} – {date_str} – {match.location}"
            )
    except Exception as e:
        print(f"❌ notify_match_created: {e}")

@shared_task
def notify_match_updated(match_id):
    try:
        match = Match.objects.get(id=match_id)
        nominations = MatchNomination.objects.filter(match=match)
        tokens = get_tokens([n.user for n in nominations])

        for token in tokens:
            send_push_notification(
                token,
                title="📝 Zápas aktualizovaný",
                message=f"Zápas proti {match.opponent} bol upravený."
            )
    except Exception as e:
        print(f"❌ notify_match_updated: {e}")

@shared_task
def notify_match_deleted(match_id, opponent):
    try:
        nominations = MatchNomination.objects.filter(match_id=match_id)
        tokens = get_tokens([n.user for n in nominations])

        for token in tokens:
            send_push_notification(
                token,
                title="❌ Zápas zrušený",
                message=f"Zápas proti {opponent} bol zrušený."
            )
    except Exception as e:
        print(f"❌ notify_match_deleted: {e}")

@shared_task
def notify_nomination_changed(match_id, user_ids):
    try:
        match = Match.objects.get(id=match_id)
        users = User.objects.filter(id__in=user_ids)
        tokens = get_tokens(users)

        for token in tokens:
            send_push_notification(
                token,
                title="📢 Nominácia",
                message=f"Bol si nominovaný na zápas proti {match.opponent}."
            )
    except Exception as e:
        print(f"❌ notify_nomination_changed: {e}")