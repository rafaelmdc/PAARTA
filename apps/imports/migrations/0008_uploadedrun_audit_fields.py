import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('imports', '0007_uploadedrun_checksum_uploadedrunshunk'),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadedrun',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='uploads_created',
                to=django.conf.settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='completed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='uploads_completed',
                to=django.conf.settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='import_requested_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='uploads_import_requested',
                to=django.conf.settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='client_ip',
            field=models.CharField(blank=True, max_length=45, null=True),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='user_agent',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='failed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
