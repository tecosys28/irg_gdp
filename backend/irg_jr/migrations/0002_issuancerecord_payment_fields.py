"""
Migration: Add payment proof fields and status to IssuanceRecord,
           make jr_unit nullable (JR unit created after payment).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('irg_jr', '0001_initial'),
    ]

    operations = [
        # Make jr_unit nullable so a record can exist before the unit is issued
        migrations.AlterField(
            model_name='issuancerecord',
            name='jr_unit',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='issuance_record',
                to='irg_jr.jrunit',
            ),
        ),
        # invoice_file optional (uploaded later or not required for bank-transfer flow)
        migrations.AlterField(
            model_name='issuancerecord',
            name='invoice_file',
            field=models.FileField(blank=True, null=True, upload_to='jr_invoices/'),
        ),
        # Payment status
        migrations.AddField(
            model_name='issuancerecord',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING_PAYMENT', 'Pending Payment'),
                    ('PAYMENT_VERIFIED', 'Payment Verified'),
                    ('COMPLETED', 'Completed'),
                    ('REJECTED', 'Rejected'),
                ],
                default='PENDING_PAYMENT',
                max_length=20,
            ),
        ),
        # UTR reference number submitted by jeweler
        migrations.AddField(
            model_name='issuancerecord',
            name='utr_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        # Scanned payment proof document
        migrations.AddField(
            model_name='issuancerecord',
            name='payment_proof',
            field=models.FileField(blank=True, null=True, upload_to='jr_payment_proofs/'),
        ),
        # Snapshot of jewellery form data — used to create JRUnit after verification
        migrations.AddField(
            model_name='issuancerecord',
            name='pending_data',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
