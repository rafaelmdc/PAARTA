import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("browser", "0021_canonicalcodoncompositionsummary"),
    ]

    operations = [
        migrations.CreateModel(
            name="CanonicalCodonCompositionLengthSummary",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("repeat_residue", models.CharField(max_length=16)),
                ("display_rank", models.CharField(max_length=64)),
                ("display_taxon_name", models.CharField(max_length=255)),
                ("length_bin_start", models.PositiveIntegerField()),
                ("observation_count", models.PositiveIntegerField()),
                ("species_count", models.PositiveIntegerField()),
                ("codon", models.CharField(max_length=16)),
                ("codon_share", models.FloatField()),
                (
                    "display_taxon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="canonical_codon_composition_length_summaries",
                        to="browser.taxon",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "repeat_residue",
                    "display_rank",
                    "-observation_count",
                    "display_taxon_name",
                    "display_taxon_id",
                    "length_bin_start",
                    "codon",
                ],
                "indexes": [
                    models.Index(
                        fields=[
                            "repeat_residue",
                            "display_rank",
                            "observation_count",
                            "display_taxon_name",
                            "display_taxon",
                        ],
                        name="brw_cccls_browse_idx",
                    ),
                    models.Index(
                        fields=[
                            "repeat_residue",
                            "display_rank",
                            "display_taxon",
                            "length_bin_start",
                        ],
                        name="brw_cccls_taxbin_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "repeat_residue",
                            "display_rank",
                            "display_taxon",
                            "length_bin_start",
                            "codon",
                        ),
                        name="brw_cccls_unique_scope",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("codon_share__gte", 0), ("codon_share__lte", 1)),
                        name="brw_cccls_share_0_1",
                    ),
                ],
            },
        ),
    ]
