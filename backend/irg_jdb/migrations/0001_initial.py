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
        # Existing tables — will be faked by --fake-initial on EC2
        migrations.CreateModel(
            name='Design',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('category', models.CharField(max_length=20)),
                ('design_file', models.FileField(upload_to='designs/')),
                ('thumbnail', models.ImageField(upload_to='design_thumbnails/')),
                ('estimated_gold_weight', models.DecimalField(decimal_places=4, max_digits=10)),
                ('estimated_making_charges', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(default='DRAFT', max_length=15)),
                ('views_count', models.PositiveIntegerField(default=0)),
                ('orders_count', models.PositiveIntegerField(default=0)),
                ('copyright_hash', models.CharField(blank=True, max_length=66, null=True)),
                ('copyright_tx_hash', models.CharField(blank=True, max_length=66, null=True)),
                ('copyright_registered_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('approved_at', models.DateTimeField(null=True, blank=True)),
                ('designer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='designs', to='core.designerprofile')),
            ],
            options={'db_table': 'irg_jdb_design'},
        ),
        migrations.CreateModel(
            name='DesignOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('customization_notes', models.TextField(blank=True)),
                ('agreed_price', models.DecimalField(decimal_places=2, max_digits=15)),
                ('status', models.CharField(default='PLACED', max_length=15)),
                ('order_tx_hash', models.CharField(blank=True, max_length=66, null=True)),
                ('placed_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('design', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='irg_jdb.design')),
                ('jeweler', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='design_orders', to='core.jewelerprofile')),
                ('customer', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'irg_jdb_order'},
        ),
        migrations.CreateModel(
            name='RoyaltyPayment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('royalty_rate', models.DecimalField(decimal_places=2, max_digits=5)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('payment_tx_hash', models.CharField(max_length=66)),
                ('paid_at', models.DateTimeField(auto_now_add=True)),
                ('designer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='royalty_payments', to='core.designerprofile')),
                ('design_order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='royalty_payments', to='irg_jdb.designorder')),
            ],
            options={'db_table': 'irg_jdb_royalty'},
        ),
        migrations.CreateModel(
            name='Copyright',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('copyright_number', models.CharField(max_length=50, unique=True)),
                ('design_hash', models.CharField(max_length=66)),
                ('registration_tx_hash', models.CharField(max_length=66)),
                ('valid_from', models.DateField()),
                ('valid_until', models.DateField()),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('design', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='copyright_record', to='irg_jdb.design')),
                ('designer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.designerprofile')),
            ],
            options={'db_table': 'irg_jdb_copyright'},
        ),
        # New table — will be created
        migrations.CreateModel(
            name='DesignLicense',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('license_fee', models.DecimalField(decimal_places=2, max_digits=12)),
                ('royalty_per_unit_sold', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('status', models.CharField(choices=[('ACTIVE','Active'),('EXPIRED','Expired'),('REVOKED','Revoked')], default='ACTIVE', max_length=20)),
                ('valid_until', models.DateField(null=True, blank=True)),
                ('license_tx_hash', models.CharField(blank=True, max_length=66)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('design', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='licenses', to='irg_jdb.design')),
                ('licensed_to', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='design_licenses', to='core.jewelerprofile')),
            ],
            options={'db_table': 'irg_jdb_design_license'},
        ),
    ]
