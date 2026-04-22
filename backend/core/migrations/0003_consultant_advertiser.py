from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_user_groups_alter_user_is_active_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsultantProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('expertise', models.CharField(max_length=200)),
                ('years_experience', models.PositiveIntegerField(default=0)),
                ('advisory_fee_per_hour', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('bio', models.TextField(blank=True)),
                ('total_clients', models.PositiveIntegerField(default=0)),
                ('rating', models.DecimalField(decimal_places=2, default=0, max_digits=3)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='consultant_profile', to='core.user')),
            ],
            options={'db_table': 'core_consultant_profile'},
        ),
        migrations.CreateModel(
            name='AdvertiserProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('company_name', models.CharField(max_length=200)),
                ('website', models.URLField(blank=True)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='advertiser_profile', to='core.user')),
            ],
            options={'db_table': 'core_advertiser_profile'},
        ),
        migrations.CreateModel(
            name='Advertisement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('target_url', models.URLField(blank=True)),
                ('budget', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('status', models.CharField(choices=[('DRAFT','Draft'),('PENDING','Pending Review'),('ACTIVE','Active'),('PAUSED','Paused'),('REJECTED','Rejected')], default='DRAFT', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('advertiser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ads', to='core.advertiserprofile')),
            ],
            options={'db_table': 'core_advertisement'},
        ),
    ]
