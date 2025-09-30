from django_rest_passwordreset.signals import reset_password_token_created
from django.core.mail import send_mail
from django.conf import settings


def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    """
    Keď sa vygeneruje token, pošleme mail s linkom na frontend.
    """
    reset_url = f"https://ludimus.sk/reset-password?token={reset_password_token.key}"

    message = f"""
    Ahoj {reset_password_token.user.username},

    Dostali sme požiadavku na reset hesla k tvojmu účtu v Ludimus.

    Ak si to bol ty, klikni na tento odkaz a nastav si nové heslo:
    {reset_url}

    Ak si to nebol ty, ignoruj tento email.
    """

    send_mail(
        subject="🔑 Reset hesla - Ludimus",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reset_password_token.user.email],
    )
