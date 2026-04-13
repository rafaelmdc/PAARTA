from django.db import models

from .base import TimestampedModel
from .repeat_calls import RunParameter


class DownloadManifestEntry(TimestampedModel):
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="download_manifest_entries",
    )
    batch = models.ForeignKey(
        "AcquisitionBatch",
        on_delete=models.PROTECT,
        related_name="download_manifest_entries",
    )
    assembly_accession = models.CharField(max_length=255, db_index=True)
    download_status = models.CharField(max_length=64, blank=True, db_index=True)
    package_mode = models.CharField(max_length=64, blank=True)
    download_path = models.CharField(max_length=500, blank=True)
    rehydrated_path = models.CharField(max_length=500, blank=True)
    checksum = models.CharField(max_length=255, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(blank=True, null=True)
    download_started_at = models.DateTimeField(blank=True, null=True)
    download_finished_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["pipeline_run__run_id", "batch__batch_id", "assembly_accession"]
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline_run", "batch", "assembly_accession"],
                name="browser_dlmfest_unique_run_batch_accession",
            ),
        ]
        indexes = [
            models.Index(
                fields=["pipeline_run", "batch"],
                name="brw_dlmfest_run_batch_idx",
            ),
            models.Index(
                fields=["pipeline_run", "download_status"],
                name="brw_dlmfest_run_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.assembly_accession} [{self.batch.batch_id}]"


class NormalizationWarning(TimestampedModel):
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="normalization_warnings",
    )
    batch = models.ForeignKey(
        "AcquisitionBatch",
        on_delete=models.PROTECT,
        related_name="normalization_warnings",
    )
    warning_code = models.CharField(max_length=255, db_index=True)
    warning_scope = models.CharField(max_length=64, blank=True, db_index=True)
    warning_message = models.TextField(blank=True)
    genome_id = models.CharField(max_length=255, blank=True, db_index=True)
    sequence_id = models.CharField(max_length=255, blank=True, db_index=True)
    protein_id = models.CharField(max_length=255, blank=True, db_index=True)
    assembly_accession = models.CharField(max_length=255, blank=True, db_index=True)
    source_file = models.CharField(max_length=500, blank=True)
    source_record_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["pipeline_run__run_id", "batch__batch_id", "warning_code", "assembly_accession"]
        indexes = [
            models.Index(
                fields=["pipeline_run", "batch"],
                name="brw_normwarn_run_batch_idx",
            ),
            models.Index(
                fields=["pipeline_run", "assembly_accession"],
                name="brw_normwarn_run_acc_idx",
            ),
            models.Index(
                fields=["pipeline_run", "warning_code", "warning_scope"],
                name="brw_normwarn_run_code_idx",
            ),
        ]

    def __str__(self):
        return f"{self.warning_code} [{self.batch.batch_id}]"


class AccessionStatus(TimestampedModel):
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="accession_status_rows",
    )
    batch = models.ForeignKey(
        "AcquisitionBatch",
        on_delete=models.PROTECT,
        related_name="accession_status_rows",
        blank=True,
        null=True,
    )
    assembly_accession = models.CharField(max_length=255, db_index=True)
    download_status = models.CharField(max_length=64, blank=True)
    normalize_status = models.CharField(max_length=64, blank=True)
    translate_status = models.CharField(max_length=64, blank=True)
    detect_status = models.CharField(max_length=64, blank=True)
    finalize_status = models.CharField(max_length=64, blank=True)
    terminal_status = models.CharField(max_length=64, blank=True, db_index=True)
    failure_stage = models.CharField(max_length=255, blank=True)
    failure_reason = models.TextField(blank=True)
    n_genomes = models.PositiveIntegerField(default=0)
    n_proteins = models.PositiveIntegerField(default=0)
    n_repeat_calls = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["pipeline_run__run_id", "assembly_accession"]
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline_run", "assembly_accession"],
                name="browser_accstatus_unique_run_accession",
            ),
        ]
        indexes = [
            models.Index(
                fields=["pipeline_run", "terminal_status"],
                name="brw_accstatus_run_terminal_idx",
            ),
        ]

    def __str__(self):
        return f"{self.assembly_accession} [{self.pipeline_run.run_id}]"


class AccessionCallCount(TimestampedModel):
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="accession_call_count_rows",
    )
    batch = models.ForeignKey(
        "AcquisitionBatch",
        on_delete=models.PROTECT,
        related_name="accession_call_count_rows",
        blank=True,
        null=True,
    )
    assembly_accession = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=20, choices=RunParameter.Method.choices, db_index=True)
    repeat_residue = models.CharField(max_length=16, blank=True, db_index=True)
    detect_status = models.CharField(max_length=64, blank=True)
    finalize_status = models.CharField(max_length=64, blank=True)
    n_repeat_calls = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["pipeline_run__run_id", "assembly_accession", "method", "repeat_residue"]
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline_run", "assembly_accession", "method", "repeat_residue"],
                name="browser_acccallcount_unique_run_accession_method_residue",
            ),
        ]
        indexes = [
            models.Index(
                fields=["pipeline_run", "method", "repeat_residue"],
                name="brw_acccall_run_method_res_idx",
            ),
        ]

    def __str__(self):
        return f"{self.assembly_accession} [{self.method}:{self.repeat_residue}]"
