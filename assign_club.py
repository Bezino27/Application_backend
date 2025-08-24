from dochadzka_app.models import Club, Category, Player, Training, AbsenceReason

def assign_club_to_all(club_id):
    club = Club.objects.get(id=club_id)

    # Category
    categories_without_club = Category.objects.filter(club__isnull=True)
    for category in categories_without_club:
        category.club = club
        category.save()
    print(f"Assigned club to {categories_without_club.count()} categories.")

    # Player
    players_without_club = Player.objects.filter(club__isnull=True)
    for player in players_without_club:
        player.club = club
        player.save()
    print(f"Assigned club to {players_without_club.count()} players.")

    # Training
    trainings_without_club = Training.objects.filter(club__isnull=True)
    for training in trainings_without_club:
        training.club = club
        training.save()
    print(f"Assigned club to {trainings_without_club.count()} trainings.")

    # AbsenceReason
    absence_reasons_without_club = AbsenceReason.objects.filter(player__club__isnull=False, training__club__isnull=False, player__club__id=club_id, training__club__id=club_id)
    for absence_reason in absence_reasons_without_club:
        if not hasattr(absence_reason, 'club') or getattr(absence_reason, 'club', None) is None:
            # Ak AbsenceReason má pole club, nastav ho, ak nie, ignoruj
            if hasattr(absence_reason, 'club'):
                absence_reason.club = club
                absence_reason.save()
    print(f"Processed absence reasons for club id {club_id}.")