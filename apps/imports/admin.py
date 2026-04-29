from django.contrib import admin

from .models import ImportBatch, UploadedRun


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "source_path",
        "pipeline_run",
        "status",
        "phase",
        "success_count",
        "started_at",
        "heartbeat_at",
        "finished_at",
    )
    search_fields = ("source_path", "pipeline_run__run_id", "status", "phase")
    list_filter = ("status", "phase", "replace_existing")


@admin.register(UploadedRun)
class UploadedRunAdmin(admin.ModelAdmin):
    list_display = (
        "original_filename",
        "run_id",
        "status",
        "size_bytes",
        "received_bytes",
        "total_chunks",
        "import_batch",
        "created_at",
        "updated_at",
    )
    search_fields = ("original_filename", "run_id", "upload_id", "publish_root", "error_message")
    list_filter = ("status", "created_at", "updated_at")
    readonly_fields = ("upload_id", "created_at", "updated_at")
