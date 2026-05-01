import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('imports', '0006_uploadedrun'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadedrun',
            name='file_sha256',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='assembled_sha256',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='checksum_status',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='uploadedrun',
            name='checksum_error',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='UploadedRunChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chunk_index', models.PositiveIntegerField()),
                ('size_bytes', models.PositiveIntegerField()),
                ('sha256', models.CharField(max_length=64)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_run', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chunk_records',
                    to='imports.uploadedrun',
                )),
            ],
            options={
                'unique_together': {('uploaded_run', 'chunk_index')},
            },
        ),
    ]
