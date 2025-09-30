from django.apps import AppConfig
from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dochadzka_app'
    def ready(self):
        import dochadzka_app.signals  # načíta signály

