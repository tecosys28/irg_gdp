from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('irg_gic', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HouseholdRegistration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('commission_rate', models.DecimalField(decimal_places=2, default=25, max_digits=5)),
                ('status', models.CharField(choices=[('ACTIVE','Active'),('INACTIVE','Inactive')], default='ACTIVE', max_length=20)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('licensee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='registered_households', to='core.licenseeprofile')),
                ('household_user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='licensee_registrations', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'irg_gic_household_registration'},
        ),
        migrations.AlterUniqueTogether(
            name='householdregistration',
            unique_together={('licensee', 'household_user')},
        ),
        migrations.CreateModel(
            name='GICRedemption',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('redemption_value', models.DecimalField(decimal_places=2, max_digits=15)),
                ('status', models.CharField(choices=[('REQUESTED','Requested'),('PROCESSING','Processing'),('COMPLETED','Completed'),('REJECTED','Rejected')], default='REQUESTED', max_length=20)),
                ('redemption_tx_hash', models.CharField(blank=True, max_length=66)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('certificate', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='redemptions', to='irg_gic.giccertificate')),
                ('redeemed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'irg_gic_redemption'},
        ),
    ]
