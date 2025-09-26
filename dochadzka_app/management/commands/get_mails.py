from django.core.management.base import BaseCommand
from dochadzka_app.models import User


class Command(BaseCommand):
    help = "Exportuje všetky e-maily hráčov z kategórie s id 9 do mails.txt"

    def handle(self, *args, **options):
        users = User.objects.filter(
            roles__category_id=9,
            roles__role="player"
        ).exclude(email="").values_list("email", flat=True)

        file_path = "mails.txt"
        with open(file_path, "w") as f:
            for email in users:
                f.write(email + "\n")

        self.stdout.write(self.style.SUCCESS(
            f"✅ Export hotový. Počet e-mailov: {users.count()}. Súbor: {file_path}"
        ))
