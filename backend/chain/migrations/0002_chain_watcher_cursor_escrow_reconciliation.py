from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chain', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChainWatcherCursor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=80, unique=True)),
                ('last_block', models.BigIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'chain_watcher_cursor'},
        ),
        migrations.CreateModel(
            name='EscrowReconciliationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('run_date', models.DateField(db_index=True)),
                ('status', models.CharField(
                    choices=[
                        ('OK', 'Balanced — on-chain events match bank credits'),
                        ('DISCREPANCY', 'Mismatch detected — redemptions halted'),
                        ('PARTIAL', 'Bank statement not yet received — run again when available'),
                        ('ERROR', 'Reconciliation run failed due to RPC or DB error'),
                    ],
                    db_index=True,
                    max_length=14,
                )),
                ('escrow_locked_count', models.PositiveIntegerField(default=0)),
                ('escrow_released_count', models.PositiveIntegerField(default=0)),
                ('escrow_refunded_count', models.PositiveIntegerField(default=0)),
                ('total_locked_inr', models.BigIntegerField(default=0)),
                ('total_released_inr', models.BigIntegerField(default=0)),
                ('total_refunded_inr', models.BigIntegerField(default=0)),
                ('bank_credits_inr', models.BigIntegerField(default=0)),
                ('discrepancy_inr', models.BigIntegerField(default=0)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'chain_escrow_reconciliation_log',
                'ordering': ['-run_date'],
                'get_latest_by': 'run_date',
            },
        ),
    ]
