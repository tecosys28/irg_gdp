from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('irg_jdb', '0001_initial'),
    ]

    operations = [
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
