from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("imports", "0008_uploadedrun_audit_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="uploadedrun",
            name="actor_label",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
