from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('irg_jr', '0002_issuancerecord_payment_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoldAssessment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('customer_email', models.EmailField()),
                ('item_description', models.TextField()),
                ('estimated_weight', models.DecimalField(decimal_places=4, max_digits=10)),
                ('purity', models.CharField(choices=[('24K','24K'),('22K','22K'),('18K','18K'),('14K','14K')], max_length=4)),
                ('test_method', models.CharField(choices=[('XRF','XRF Spectrometer'),('ACID','Acid Test'),('FIRE','Fire Assay'),('DENSITY','Density Test')], default='XRF', max_length=10)),
                ('estimated_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('benchmark_used', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('assessment_notes', models.TextField(blank=True)),
                ('certificate_number', models.CharField(max_length=50, unique=True)),
                ('status', models.CharField(choices=[('DRAFT','Draft'),('SUBMITTED','Submitted'),('CONFIRMED','Confirmed')], default='DRAFT', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('jeweler', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assessments', to='core.jewelerprofile')),
            ],
            options={'db_table': 'irg_jr_gold_assessment'},
        ),
    ]
