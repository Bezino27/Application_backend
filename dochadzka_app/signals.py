from django_rest_passwordreset.signals import reset_password_token_created
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

print("📩 signals.py importnutý")

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):

    reset_url = f"https://ludimus.sk/reset-password?token={reset_password_token.key}"

    message = f"""
    Ahoj {reset_password_token.user.username},

    Klikni na tento odkaz a nastav si nové heslo:
    {reset_url}
    """

    send_mail(
        subject="🔑 Reset hesla - Ludimus",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reset_password_token.user.email],
        fail_silently=False,
    )
