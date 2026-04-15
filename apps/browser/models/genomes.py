from django.db import models

from .base import TimestampedModel


class Genome(TimestampedModel):
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="genomes",
    )
    batch = models.ForeignKey(
        "AcquisitionBatch",
        on_delete=models.PROTECT,
        related_name="genomes",
        blank=True,
        null=True,
    )
    genome_id = models.CharField(max_length=255)
    source = models.CharField(max_length=64)
    accession = models.CharField(max_length=255, db_index=True)
    genome_name = models.CharField(max_length=255, db_index=True)
    assembly_type = models.CharField(max_length=128)
    taxon = models.ForeignKey(
        "Taxon",
        on_delete=models.PROTECT,
        related_name="genomes",
    )
    assembly_level = models.CharField(max_length=128, blank=True)
    species_name = models.CharField(max_length=255, blank=True)
    analyzed_protein_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["pipeline_run__run_id", "accession", "genome_id"]
        verbose_name = "imported genome observation"
        verbose_name_plural = "imported genome observations"
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline_run", "genome_id"],
                name="browser_genome_unique_run_genome_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["pipeline_run", "accession"],
                name="brw_genome_run_acc_idx",
            ),
            models.Index(
                fields=["pipeline_run", "genome_name"],
                name="brw_genome_run_name_idx",
            ),
            models.Index(
                fields=["pipeline_run", "taxon"],
                name="brw_genome_run_tax_idx",
            ),
        ]

    def __str__(self):
        return f"{self.accession} [{self.pipeline_run.run_id}]"


class Sequence(TimestampedModel):
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="sequences",
    )
    genome = models.ForeignKey(
        Genome,
        on_delete=models.CASCADE,
        related_name="sequences",
    )
    taxon = models.ForeignKey(
        "Taxon",
        on_delete=models.PROTECT,
        related_name="sequences",
    )
    sequence_id = models.CharField(max_length=255)
    sequence_name = models.CharField(max_length=255, db_index=True)
    sequence_length = models.PositiveIntegerField()
    nucleotide_sequence = models.TextField(blank=True)
    gene_symbol = models.CharField(max_length=255, blank=True, db_index=True)
    transcript_id = models.CharField(max_length=255, blank=True)
    isoform_id = models.CharField(max_length=255, blank=True)
    assembly_accession = models.CharField(max_length=255, blank=True)
    source_record_id = models.CharField(max_length=255, blank=True)
    protein_external_id = models.CharField(max_length=255, blank=True)
    translation_table = models.CharField(max_length=32, blank=True)
    gene_group = models.CharField(max_length=255, blank=True)
    linkage_status = models.CharField(max_length=64, blank=True)
    partial_status = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["pipeline_run__run_id", "sequence_name", "sequence_id"]
        verbose_name = "imported sequence observation"
        verbose_name_plural = "imported sequence observations"
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline_run", "sequence_id"],
                name="browser_sequence_unique_run_sequence_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["pipeline_run", "assembly_accession", "sequence_name", "id"],
                name="brw_seq_run_asm_name_id",
            ),
            models.Index(
                fields=["pipeline_run", "genome"],
                name="brw_seq_run_genome_idx",
            ),
            models.Index(
                fields=["pipeline_run", "taxon"],
                name="brw_seq_run_taxon_idx",
            ),
            models.Index(
                fields=["pipeline_run", "gene_symbol"],
                name="brw_seq_run_gene_idx",
            ),
        ]

    def __str__(self):
        return f"{self.sequence_name} [{self.pipeline_run.run_id}]"


class Protein(TimestampedModel):
    pipeline_run = models.ForeignKey(
        "PipelineRun",
        on_delete=models.CASCADE,
        related_name="proteins",
    )
    genome = models.ForeignKey(
        Genome,
        on_delete=models.CASCADE,
        related_name="proteins",
    )
    sequence = models.ForeignKey(
        Sequence,
        on_delete=models.CASCADE,
        related_name="proteins",
    )
    taxon = models.ForeignKey(
        "Taxon",
        on_delete=models.PROTECT,
        related_name="proteins",
    )
    protein_id = models.CharField(max_length=255)
    protein_name = models.CharField(max_length=255, db_index=True)
    protein_length = models.PositiveIntegerField()
    accession = models.CharField(max_length=255, blank=True, db_index=True)
    amino_acid_sequence = models.TextField(blank=True)
    gene_symbol = models.CharField(max_length=255, blank=True, db_index=True)
    translation_method = models.CharField(max_length=64, blank=True)
    translation_status = models.CharField(max_length=64, blank=True)
    assembly_accession = models.CharField(max_length=255, blank=True)
    gene_group = models.CharField(max_length=255, blank=True)
    protein_external_id = models.CharField(max_length=255, blank=True)
    repeat_call_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["pipeline_run__run_id", "protein_name", "protein_id"]
        verbose_name = "imported protein observation"
        verbose_name_plural = "imported protein observations"
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline_run", "protein_id"],
                name="browser_protein_unique_run_protein_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["pipeline_run", "accession", "protein_name", "id"],
                name="brw_prot_run_acc_name_id",
            ),
            models.Index(
                fields=["pipeline_run", "genome"],
                name="brw_protein_run_genome_idx",
            ),
            models.Index(
                fields=["pipeline_run", "accession"],
                name="brw_protein_run_acc_idx",
            ),
            models.Index(
                fields=["pipeline_run", "taxon"],
                name="brw_protein_run_taxon_idx",
            ),
            models.Index(
                fields=["pipeline_run", "gene_symbol"],
                name="brw_protein_run_gene_idx",
            ),
        ]

    def __str__(self):
        return f"{self.protein_name} [{self.pipeline_run.run_id}]"
