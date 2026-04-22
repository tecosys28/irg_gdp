from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('corpus', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CorpusBankAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_name',   models.CharField(max_length=200)),
                ('account_number', models.CharField(max_length=50)),
                ('account_type',   models.CharField(max_length=50)),
                ('bank_name',      models.CharField(max_length=200)),
                ('branch',         models.CharField(max_length=200)),
                ('city',           models.CharField(max_length=100)),
                ('postal_code',    models.CharField(max_length=20)),
                ('country',        models.CharField(default='INDIA', max_length=100)),
                ('swift_code',     models.CharField(blank=True, max_length=20)),
                ('ifsc_code',      models.CharField(max_length=20)),
                ('is_active',      models.BooleanField(default=True)),
                ('updated_at',     models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'corpus_bank_account'},
        ),
    ]
