from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Existing tables — faked by --fake-initial on EC2
        migrations.CreateModel(
            name='GICCertificate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('certificate_number', models.CharField(max_length=50, unique=True)),
                ('investment_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('gold_equivalent_grams', models.DecimalField(decimal_places=4, max_digits=10)),
                ('benchmark_at_issue', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(default='ACTIVE', max_length=15)),
                ('stream1_corpus_returns', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('stream2_trading_fees', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('stream3_appreciation', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('blockchain_id', models.CharField(max_length=66, unique=True)),
                ('issuance_tx_hash', models.CharField(max_length=66)),
                ('issued_at', models.DateTimeField(auto_now_add=True)),
                ('maturity_date', models.DateField()),
                ('holder', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='gic_certificates', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'irg_gic_certificate'},
        ),
        migrations.CreateModel(
            name='GICRevenueDistribution',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('stream', models.CharField(max_length=15)),
                ('period', models.CharField(max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('distribution_tx_hash', models.CharField(max_length=66)),
                ('distributed_at', models.DateTimeField(auto_now_add=True)),
                ('certificate', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='distributions', to='irg_gic.giccertificate')),
            ],
            options={'db_table': 'irg_gic_distribution'},
        ),
        # New tables — will be created
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
