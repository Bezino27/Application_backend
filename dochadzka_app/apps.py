from django.apps import AppConfig

class DochadzkaAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dochadzka_app"

    def ready(self):
        import dochadzka_app.signals
        print("✅ Signály načítané")
