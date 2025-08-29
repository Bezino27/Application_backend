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

        date_str = localtime(match.date).strftime("%d.%m.%Y")
        for token in tokens:
            send_push_notification(
                token,
                title="Nový zápas",
                message=f"Proti {match.opponent} – {date_str} – {match.location}",
                data = {"type": "match", "match_id": match.id}

            )
    except Exception as e:
        print(f"❌ notify_match_created: {e}")

@shared_task
def notify_match_updated(match_id):
    try:
        match = Match.objects.get(id=match_id)

        # 🔁 Všetci hráči s rolou 'player' v danej kategórii a klube
        users = User.objects.filter(
            roles__category=match.category,
            roles__role='player',
            club=match.club
        ).distinct()

        tokens = get_tokens(users)

        for token in tokens:
            send_push_notification(
                token,
                title="Zmena v zápase!",
                message=f"Boli zmenené údaje zápasu proti {match.opponent}, skontroluj ich!",
                data = {"type": "match", "match_id": match.id}
            )

    except Exception as e:
        print(f"❌ notify_match_updated: {e}")

@shared_task
def notify_match_deleted(opponent, category_id, club_id):
    try:
        users = User.objects.filter(
            roles__category_id=category_id,
            roles__role='player',
            club_id=club_id
        ).distinct()

        tokens = get_tokens(users)

        for token in tokens:
            send_push_notification(
                token,
                title="Zápas zrušený",
                message=f"Zápas proti {opponent} bol zrušený."
            )
    except Exception as e:
        print(f"❌ notify_match_deleted: {e}")
@shared_task
def notify_nomination_changed(match_id, user_ids):
    try:
        match = Match.objects.get(id=match_id)
        nominations = MatchNomination.objects.filter(match=match, user__id__in=user_ids).select_related('user')

        for nomination in nominations:
            token_list = get_tokens([nomination.user])
            role = "v základe" if not nomination.is_substitute else "ako náhradník"
            message = f"Bol si nominovaný na zápas proti {match.opponent} {role}."

            for token in token_list:
                send_push_notification(
                    token,
                    title="Nominácia",
                    message=message,
                    data = {"type": "match", "match_id": match.id}
                )
    except Exception as e:
        print(f"❌ notify_nomination_changed: {e}")

@shared_task
def notify_nomination_removed(match_id, user_ids):
    try:
        match = Match.objects.get(id=match_id)
        users = User.objects.filter(id__in=user_ids)
        tokens = get_tokens(users)

        for token in tokens:
            send_push_notification(
                token,
                title="Zmena v nominácii",
                message=f"Bol si odstránený z nominácie na zápas proti {match.opponent}.",
                data = {"type": "match", "match_id": match.id}
            )
    except Exception as e:
        print(f"❌ notify_nomination_removed: {e}")

@shared_task
def remind_unknown_players(training_id, user_ids):
    try:
        training = Training.objects.get(id=training_id)
        users = User.objects.filter(id__in=user_ids)

        for user in users:
            tokens = ExpoPushToken.objects.filter(user=user).values_list("token", flat=True)
            for token in tokens:
                send_push_notification(
                    token,
                    title="Nezabudni hlasovať!",
                    message=f"Stále si nepotvrdil účasť na udalosti {training.description} ({training.date.strftime('%d.%m.%Y')})!",
                    data={"type": "training", "training_id": training.id}
                )
                logger.info(f"Pripomenutie posl. hráčovi {user.username} → {token}")

    except Exception as e:
        logger.error(f"❌ Chyba pri pripomenutí neodpovedaným: {e}")


@shared_task
def notify_match_reminder(match_id, user_ids):
    try:
        match = Match.objects.get(id=match_id)
        users = User.objects.filter(id__in=user_ids)

        for user in users:
            tokens = ExpoPushToken.objects.filter(user=user).values_list("token", flat=True)
            for token in tokens:
                send_push_notification(
                    token=token,
                    title="Potvrď účasť na zápase",
                    message=f"Zápas proti {match.opponent} – {match.date.strftime('%d.%m.%Y')}. Nezabudni odpovedať.",
                    data={
                        "type": "match",
                        "match_id": match.id
                    }
                )
                logger.info(f"📨 Reminder na zápas poslaný hráčovi {user.username} → {token}")
    except Match.DoesNotExist:
        logger.warning(f"❌ notify_match_reminder: Match {match_id} not found")
    except Exception as e:
        logger.error(f"❌ Chyba pri pripomenutí na zápas: {e}")


@shared_task
def notify_created_member_payment(user_id, amount, due_date):
    try:
        user = User.objects.get(id=user_id)
        tokens = ExpoPushToken.objects.filter(user=user).values_list("token", flat=True)

        for token in tokens:
            send_push_notification(
                token=token,
                title="Nová platba",
                message=f"Bola ti vytvorená nová platba vo výške {amount} € so splatnosťou do {due_date}.",
                data={"type": "payment"}
            )
            logger.info(f"Notifikácia o novej platbe → {user.username} ({token})")
    except Exception as e:
        logger.error(f"Chyba pri notifikácii novej platby: {e}")


@shared_task
def notify_payment_status(user_id, is_paid, amount=None, vs=None):
    try:
        user = User.objects.get(id=user_id)
        tokens = ExpoPushToken.objects.filter(user=user).values_list("token", flat=True)

        if is_paid:
            title = "Platba prijatá"
            message = f"Platba vo výške {amount} € s VS {vs} bola úspešne prijatá. Ďakujeme!"
        else:
            title = "Platba chýba"
            message = "Tvoja platba zatiaľ nebola zaznamenaná. Skontroluj prosím svoje prevody."

        for token in tokens:
            send_push_notification(
                token=token,
                title=title,
                message=message,
                data={"type": "payment"}
            )
            logger.info(f"Notifikácia platby ({'OK' if is_paid else 'CHÝBA'}) → {user.username} ({token})")

    except Exception as e:
        logger.error(f"Chyba pri posielaní stavu platby: {e}")