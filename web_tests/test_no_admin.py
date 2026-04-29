from django.contrib.admin.models import LogEntry
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.imports.models import ImportBatch


@override_settings(NO_ADMIN=True)
class NoAdminModeTests(TestCase):
    def test_imports_home_allows_anonymous_user(self):
        response = self.client.get(reverse("imports:home"))

        self.assertEqual(response.status_code, 200)

    def test_import_history_allows_anonymous_user(self):
        response = self.client.get(reverse("imports:history"))

        self.assertEqual(response.status_code, 200)

    def test_admin_index_allows_anonymous_user(self):
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)

    def test_admin_add_write_does_not_require_persisted_user_for_log_entry(self):
        response = self.client.post(
            reverse("admin:imports_importbatch_add"),
            {
                "source_path": "/tmp/run-alpha/publish",
                "status": ImportBatch.Status.PENDING,
                "replace_existing": "0",
                "phase": "",
                "celery_task_id": "",
                "success_count": "0",
                "error_count": "0",
                "progress_payload": "{}",
                "row_counts": "{}",
                "error_message": "",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImportBatch.objects.count(), 1)
        self.assertEqual(LogEntry.objects.count(), 0)
