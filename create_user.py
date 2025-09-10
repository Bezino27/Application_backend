from django.contrib.auth.models import User
from dochadzka_app.models import Player

for player in Player.objects.filter(user__isnull=True):
    username = f"{player.first_name.lower()}_{player.last_name.lower()}"

    # Ak už používateľ s týmto username existuje, pridáme číslo, aby bolo unikátne
    original_username = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{original_username}{counter}"
        counter += 1

    user = User.objects.create_user(
        username=username,
        password="atukosice",
        first_name=player.first_name,
        last_name=player.last_name,
        email=player.email_1
    )

    player.user = user
    player.save()

print("Hotovo – používatelia vytvorení a priradení hráčom bez používateľa.")