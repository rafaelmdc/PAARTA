from django.apps import AppConfig
from django.conf import settings


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        from django.contrib import admin

        if getattr(admin.ModelAdmin, "_homorepeat_no_admin_log_patch", False):
            return

        original_log_addition = admin.ModelAdmin.log_addition
        original_log_change = admin.ModelAdmin.log_change
        original_log_deletion = admin.ModelAdmin.log_deletion

        def log_addition(self, request, obj, message):
            if getattr(settings, "NO_ADMIN", False):
                return None
            return original_log_addition(self, request, obj, message)

        def log_change(self, request, obj, message):
            if getattr(settings, "NO_ADMIN", False):
                return None
            return original_log_change(self, request, obj, message)

        def log_deletion(self, request, obj, object_repr):
            if getattr(settings, "NO_ADMIN", False):
                return None
            return original_log_deletion(self, request, obj, object_repr)

        admin.ModelAdmin.log_addition = log_addition
        admin.ModelAdmin.log_change = log_change
        admin.ModelAdmin.log_deletion = log_deletion
        admin.ModelAdmin._homorepeat_no_admin_log_patch = True
