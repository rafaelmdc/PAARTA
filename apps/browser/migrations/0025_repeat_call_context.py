from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("browser", "0024_payload_build"),
    ]

    operations = [
        migrations.CreateModel(
            name="RepeatCallContext",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("protein_id", models.CharField(max_length=255)),
                ("sequence_id", models.CharField(max_length=255)),
                ("aa_left_flank", models.TextField(blank=True)),
                ("aa_right_flank", models.TextField(blank=True)),
                ("nt_left_flank", models.TextField(blank=True)),
                ("nt_right_flank", models.TextField(blank=True)),
                ("aa_context_window_size", models.PositiveIntegerField()),
                ("nt_context_window_size", models.PositiveIntegerField()),
                (
                    "pipeline_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="repeat_call_contexts",
                        to="browser.pipelinerun",
                    ),
                ),
                (
                    "repeat_call",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="context",
                        to="browser.repeatcall",
                    ),
                ),
            ],
            options={
                "verbose_name": "imported repeat-call context",
                "verbose_name_plural": "imported repeat-call contexts",
                "ordering": ["repeat_call_id"],
            },
        ),
        migrations.AddIndex(
            model_name="repeatcallcontext",
            index=models.Index(
                fields=["pipeline_run", "protein_id"],
                name="brw_rcctx_run_prot_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="repeatcallcontext",
            index=models.Index(
                fields=["pipeline_run", "sequence_id"],
                name="brw_rcctx_run_seq_idx",
            ),
        ),
    ]
