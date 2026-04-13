from django.db import models

from .base import TimestampedModel
from .repeat_calls import RunParameter


class MergedProteinSummary(TimestampedModel):
    accession = models.CharField(max_length=255, db_index=True)
    protein_id = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=20, choices=RunParameter.Method.choices, db_index=True)
    protein_name = models.CharField(max_length=255, blank=True, db_index=True)
    protein_length = models.PositiveIntegerField(default=0)
    gene_symbol_label = models.TextField(blank=True)
    methods_label = models.TextField(blank=True)
    repeat_residues_label = models.TextField(blank=True)
    coordinate_label = models.TextField(blank=True)
    protein_length_label = models.TextField(blank=True)
    representative_protein = models.ForeignKey(
        "Protein",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    representative_repeat_call = models.ForeignKey(
        "RepeatCall",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    source_runs_count = models.PositiveIntegerField(default=0)
    source_taxa_count = models.PositiveIntegerField(default=0)
    source_proteins_count = models.PositiveIntegerField(default=0)
    source_repeat_calls_count = models.PositiveIntegerField(default=0)
    residue_groups_count = models.PositiveIntegerField(default=0)
    collapsed_repeat_calls_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["accession", "protein_name", "protein_id", "method"]
        constraints = [
            models.UniqueConstraint(
                fields=["accession", "protein_id", "method"],
                name="browser_mgprot_unique_acc_pid_method",
            ),
        ]
        indexes = [
            models.Index(
                fields=["accession", "protein_name", "id"],
                name="brw_mgprot_acc_name_id",
            ),
            models.Index(
                fields=["protein_name", "accession", "id"],
                name="brw_mgprot_name_acc_id",
            ),
            models.Index(
                fields=["method", "accession", "protein_name"],
                name="brw_mgprot_method_acc_idx",
            ),
        ]

    def __str__(self):
        return f"{self.accession}:{self.protein_id} [{self.method}]"


class MergedResidueSummary(TimestampedModel):
    accession = models.CharField(max_length=255, db_index=True)
    protein_id = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=20, choices=RunParameter.Method.choices, db_index=True)
    repeat_residue = models.CharField(max_length=16, db_index=True)
    protein_name = models.CharField(max_length=255, blank=True, db_index=True)
    protein_length = models.PositiveIntegerField(default=0)
    gene_symbol_label = models.TextField(blank=True)
    methods_label = models.TextField(blank=True)
    coordinate_label = models.TextField(blank=True)
    protein_length_label = models.TextField(blank=True)
    start = models.PositiveIntegerField(default=0)
    end = models.PositiveIntegerField(default=0)
    length = models.PositiveIntegerField(default=0)
    length_label = models.TextField(blank=True)
    normalized_purity = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    purity_label = models.TextField(blank=True)
    representative_protein = models.ForeignKey(
        "Protein",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    representative_repeat_call = models.ForeignKey(
        "RepeatCall",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    source_runs_count = models.PositiveIntegerField(default=0)
    source_taxa_count = models.PositiveIntegerField(default=0)
    source_proteins_count = models.PositiveIntegerField(default=0)
    source_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["accession", "protein_name", "protein_id", "method", "repeat_residue"]
        constraints = [
            models.UniqueConstraint(
                fields=["accession", "protein_id", "method", "repeat_residue"],
                name="browser_mgres_unique_acc_pid_method_res",
            ),
        ]
        indexes = [
            models.Index(
                fields=["accession", "protein_name", "id"],
                name="brw_mgres_acc_name_id",
            ),
            models.Index(
                fields=["protein_name", "accession", "id"],
                name="brw_mgres_name_acc_id",
            ),
            models.Index(
                fields=["method", "repeat_residue", "accession", "id"],
                name="brw_mgres_method_res_acc_idx",
            ),
        ]

    def __str__(self):
        return f"{self.accession}:{self.protein_id}:{self.repeat_residue} [{self.method}]"


class MergedProteinOccurrence(TimestampedModel):
    summary = models.ForeignKey(
        MergedProteinSummary,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="merged_protein_occurrences",
    )
    taxon = models.ForeignKey(
        "Taxon",
        on_delete=models.PROTECT,
        related_name="merged_protein_occurrences",
    )
    representative_protein = models.ForeignKey(
        "Protein",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    representative_repeat_call = models.ForeignKey(
        "RepeatCall",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    source_proteins_count = models.PositiveIntegerField(default=0)
    source_repeat_calls_count = models.PositiveIntegerField(default=0)
    residue_groups_count = models.PositiveIntegerField(default=0)
    collapsed_repeat_calls_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["pipeline_run__run_id", "summary__accession", "summary__protein_name", "summary__protein_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["summary", "pipeline_run", "taxon"],
                name="browser_mgprotocc_unique_sum_run_tax",
            ),
        ]
        indexes = [
            models.Index(
                fields=["pipeline_run", "taxon", "summary"],
                name="brw_mgprotocc_run_tax_sum_idx",
            ),
            models.Index(
                fields=["summary", "pipeline_run"],
                name="brw_mgprotocc_sum_run_idx",
            ),
            models.Index(
                fields=["taxon", "summary"],
                name="brw_mgprotocc_tax_sum_idx",
            ),
        ]

    def __str__(self):
        return f"{self.summary} @ {self.pipeline_run.run_id}"


class MergedResidueOccurrence(TimestampedModel):
    summary = models.ForeignKey(
        MergedResidueSummary,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="merged_residue_occurrences",
    )
    taxon = models.ForeignKey(
        "Taxon",
        on_delete=models.PROTECT,
        related_name="merged_residue_occurrences",
    )
    representative_protein = models.ForeignKey(
        "Protein",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    representative_repeat_call = models.ForeignKey(
        "RepeatCall",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    source_proteins_count = models.PositiveIntegerField(default=0)
    source_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = [
            "pipeline_run__run_id",
            "summary__accession",
            "summary__protein_name",
            "summary__protein_id",
            "summary__repeat_residue",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["summary", "pipeline_run", "taxon"],
                name="browser_mgresocc_unique_sum_run_tax",
            ),
        ]
        indexes = [
            models.Index(
                fields=["pipeline_run", "taxon", "summary"],
                name="brw_mgresocc_run_tax_sum_idx",
            ),
            models.Index(
                fields=["summary", "pipeline_run"],
                name="brw_mgresocc_sum_run_idx",
            ),
            models.Index(
                fields=["taxon", "summary"],
                name="brw_mgresocc_tax_sum_idx",
            ),
        ]

    def __str__(self):
        return f"{self.summary} @ {self.pipeline_run.run_id}"
