from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = "Otestuje odosielanie emailov cez nastavený SMTP server"

    def handle(self, *args, **options):
        try:
            self.stdout.write("➡️ Posielam testovací email...")

            result = send_mail(
                subject="Test Ludimus",
                message="Toto je testovací email zo servera.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=["tomikbez@gmail.com"],  # 👈 sem daj svoju adresu
                fail_silently=False,
            )

            if result == 1:
                self.stdout.write(self.style.SUCCESS("✅ Email bol úspešne odoslaný"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Email sa neodoslal (send_mail vrátil: {result})"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Chyba pri odosielaní emailu: {e}"))
