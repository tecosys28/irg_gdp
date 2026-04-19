from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TxAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_tx_id', models.CharField(db_index=True, max_length=80, unique=True)),
                ('module', models.CharField(db_index=True, max_length=40)),
                ('action', models.CharField(db_index=True, max_length=60)),
                ('mode', models.CharField(choices=[('raw', 'Raw — pre-signed by user device'), ('system', 'System — signed by backend operator key')], default='system', max_length=10)),
                ('chain_id', models.IntegerField(default=888101)),
                ('to_address', models.CharField(blank=True, max_length=66)),
                ('value_wei', models.CharField(blank=True, default='0', max_length=80)),
                ('data_hash', models.CharField(blank=True, max_length=66)),
                ('tx_hash', models.CharField(blank=True, db_index=True, max_length=66)),
                ('block_number', models.BigIntegerField(blank=True, null=True)),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('PENDING', 'Pending — queued in backend, not yet sent to middleware'), ('SUBMITTED', 'Submitted to middleware, awaiting chain receipt'), ('CONFIRMED', 'Included in a block on IRG Chain 888101'), ('FINAL', 'Finalised (N confirmations deep)'), ('FAILED', 'Middleware rejected or chain reverted'), ('SIMULATED', 'Dev/test path — no real on-chain write')], db_index=True, default='PENDING', max_length=12)),
                ('last_error', models.TextField(blank=True)),
                ('retries', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='chain_tx_audits', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'chain_tx_audit_log',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['module', 'action'], name='chain_tx_module_action_idx'),
                    models.Index(fields=['status', 'created_at'], name='chain_tx_status_created_idx'),
                ],
            },
        ),
    ]
