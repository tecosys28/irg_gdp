from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WalletActivation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('wallet_address', models.CharField(db_index=True, max_length=66, unique=True)),
                ('state', models.CharField(
                    choices=[
                        ('CREATED', 'Created — awaiting activation'),
                        ('ACTIVATED', 'Activated — ready for transactions'),
                        ('LOCKED', 'Locked — too many failed attempts'),
                        ('RECOVERING', 'Recovery in progress'),
                        ('OWNERSHIP_TRANSFER', 'Ownership transfer in progress (legal-person wallets)'),
                        ('SUSPENDED', 'Suspended'),
                        ('RECOVERED', 'Recovered — superseded'),
                    ],
                    db_index=True, default='CREATED', max_length=20)),
                ('holder_type', models.CharField(
                    choices=[
                        ('INDIVIDUAL', 'Natural person'),
                        ('LEGAL_PERSON', 'Company, LLP, trust, firm, HUF, cooperative, etc.'),
                    ],
                    default='INDIVIDUAL', max_length=14)),
                ('legal_entity_name', models.CharField(blank=True, max_length=200)),
                ('entity_type', models.CharField(blank=True, default='', max_length=24,
                    choices=[
                        ('', '—'),
                        ('PRIVATE_LTD', 'Private limited company'),
                        ('PUBLIC_LTD_LISTED', 'Public limited — listed'),
                        ('PUBLIC_LTD_UNLISTED', 'Public limited — unlisted'),
                        ('LLP', 'Limited liability partnership'),
                        ('PARTNERSHIP', 'Partnership firm'),
                        ('PROPRIETORSHIP', 'Proprietorship'),
                        ('PUBLIC_TRUST', 'Public trust'),
                        ('PRIVATE_TRUST', 'Private trust'),
                        ('COOPERATIVE', 'Cooperative society'),
                        ('HUF', 'Hindu Undivided Family'),
                        ('OTHER', 'Other legal entity'),
                    ])),
                ('password_hash', models.CharField(blank=True, max_length=256)),
                ('password_algo', models.CharField(blank=True, default='pbkdf2_sha256', max_length=32)),
                ('password_iterations', models.PositiveIntegerField(default=600000)),
                ('password_salt', models.CharField(blank=True, max_length=64)),
                ('seed_phrase_hash', models.CharField(blank=True, max_length=66)),
                ('seed_phrase_confirmed', models.BooleanField(default=False)),
                ('seed_phrase_confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('failed_password_attempts', models.PositiveSmallIntegerField(default=0)),
                ('locked_until', models.DateTimeField(blank=True, null=True)),
                ('last_activity_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('inactivity_prompt_sent_at', models.DateTimeField(blank=True, null=True)),
                ('inactivity_reminder_sent_at', models.DateTimeField(blank=True, null=True)),
                ('nominees_alerted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('last_state_change', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=models.deletion.CASCADE,
                    related_name='wallet_activation',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'wallet_activation'},
        ),
        migrations.CreateModel(
            name='NomineeRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('relationship', models.CharField(max_length=60)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('mobile', models.CharField(blank=True, max_length=20)),
                ('id_document_hash', models.CharField(blank=True, max_length=66)),
                ('share_percent', models.DecimalField(decimal_places=3, default=0, max_digits=6)),
                ('social_recovery_threshold', models.PositiveSmallIntegerField(default=2)),
                ('notified_at', models.DateTimeField(blank=True, null=True)),
                ('active', models.BooleanField(default=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('revoke_reason', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('wallet', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='nominees',
                    to='wallet_access.walletactivation')),
            ],
            options={
                'db_table': 'wallet_nominee',
                'indexes': [models.Index(fields=['wallet', 'active'], name='wallet_nominee_wal_act_idx')],
            },
        ),
        migrations.CreateModel(
            name='WalletDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('device_id_hash', models.CharField(db_index=True, max_length=66)),
                ('device_label', models.CharField(blank=True, max_length=100)),
                ('platform', models.CharField(blank=True, max_length=20)),
                ('state', models.CharField(
                    choices=[
                        ('PENDING', 'Pending cooling-off period'),
                        ('ACTIVE', 'Active — can sign transactions'),
                        ('RETIRED', 'Retired — superseded by rebind'),
                        ('REVOKED', 'Revoked by user or system'),
                    ],
                    default='PENDING', max_length=10)),
                ('cooling_off_until', models.DateTimeField(blank=True, null=True)),
                ('bind_tx_hash', models.CharField(blank=True, max_length=66)),
                ('revoke_tx_hash', models.CharField(blank=True, max_length=66)),
                ('bound_at', models.DateTimeField(auto_now_add=True)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('retired_at', models.DateTimeField(blank=True, null=True)),
                ('wallet', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='devices',
                    to='wallet_access.walletactivation')),
            ],
            options={
                'db_table': 'wallet_device',
                'indexes': [models.Index(fields=['wallet', 'state'], name='wallet_dev_wal_state_idx')],
            },
        ),
        migrations.CreateModel(
            name='InactivityEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('kind', models.CharField(max_length=20, choices=[
                    ('PROMPT_SENT', 'First prompt — "we have not seen you in a year"'),
                    ('REMINDER_SENT', 'Reminder sent 2 days after prompt with no response'),
                    ('NOMINEES_ALERTED', 'Nominees informed due to continued silence'),
                    ('CONFIRMED', 'User confirmed they are still active'),
                ])),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('detail', models.CharField(blank=True, max_length=200)),
                ('wallet', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='inactivity_events',
                    to='wallet_access.walletactivation')),
            ],
            options={
                'db_table': 'wallet_inactivity_event',
                'ordering': ['-occurred_at'],
                'indexes': [models.Index(fields=['wallet', 'occurred_at'], name='wallet_inact_idx')],
            },
        ),
        migrations.CreateModel(
            name='RecoveryCase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('path', models.CharField(db_index=True, max_length=10,
                    choices=[
                        ('SELF', 'Self-recovery via seed phrase'),
                        ('SOCIAL', 'Social recovery via nominees'),
                        ('TRUSTEE', 'Trustee-assisted, Ombudsman-ordered recovery'),
                    ])),
                ('status', models.CharField(db_index=True, default='FILED', max_length=20,
                    choices=[
                        ('FILED', 'Filed — initial submission'),
                        ('NOTIFIED', 'Original owner notified, cooling-off running'),
                        ('AWAITING_SIGNATURES', 'Awaiting nominee co-signatures (SOCIAL only)'),
                        ('AWAITING_OMBUDSMAN', 'Awaiting Ombudsman review (TRUSTEE only)'),
                        ('APPROVED', 'Approved — ready for execution'),
                        ('EXECUTED', 'Executed — assets moved to claimant wallet'),
                        ('REJECTED', 'Rejected'),
                        ('CANCELLED', 'Cancelled by original owner during cooling-off'),
                        ('EXPIRED', 'Expired without completion'),
                    ])),
                ('claimant_wallet_address', models.CharField(blank=True, max_length=66)),
                ('grounds', models.TextField(blank=True)),
                ('evidence_bundle_hash', models.CharField(blank=True, max_length=66)),
                ('cooling_off_ends_at', models.DateTimeField(blank=True, null=True)),
                ('public_notice_ends_at', models.DateTimeField(blank=True, null=True)),
                ('recovery_requested_tx_hash', models.CharField(blank=True, max_length=66)),
                ('ombudsman_order_hash', models.CharField(blank=True, max_length=66)),
                ('ombudsman_order_tx_hash', models.CharField(blank=True, max_length=66)),
                ('execution_tx_hash', models.CharField(blank=True, max_length=66)),
                ('reversibility_ends_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('claimant_user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='filed_recovery_cases',
                    to=settings.AUTH_USER_MODEL)),
                ('original_wallet', models.ForeignKey(
                    on_delete=models.deletion.PROTECT,
                    related_name='recovery_cases',
                    to='wallet_access.walletactivation')),
            ],
            options={
                'db_table': 'wallet_recovery_case',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['path', 'status'], name='wallet_rec_path_status_idx'),
                    models.Index(fields=['original_wallet', 'status'], name='wallet_rec_wal_status_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='NomineeSignature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('signature', models.CharField(max_length=200)),
                ('signed_at', models.DateTimeField(auto_now_add=True)),
                ('case', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='nominee_signatures',
                    to='wallet_access.recoverycase')),
                ('nominee', models.ForeignKey(
                    on_delete=models.deletion.PROTECT,
                    to='wallet_access.nomineeregistration')),
            ],
            options={
                'db_table': 'wallet_nominee_signature',
                'unique_together': {('case', 'nominee')},
            },
        ),
        migrations.CreateModel(
            name='OwnershipTransferCase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status', models.CharField(db_index=True, default='FILED', max_length=20,
                    choices=[
                        ('FILED', 'Filed'),
                        ('AWAITING_OMBUDSMAN', 'Awaiting Ombudsman review'),
                        ('APPROVED', 'Approved — seed rotation pending new operator'),
                        ('EXECUTED', 'Executed — new operator activated'),
                        ('REJECTED', 'Rejected'),
                        ('CANCELLED', 'Cancelled by current operator or entity'),
                        ('EXPIRED', 'Expired without completion'),
                    ])),
                ('reason', models.CharField(default='OTHER', max_length=24,
                    choices=[
                        ('ACQUISITION', 'Company acquired / shareholding changed'),
                        ('PARTNERSHIP_CHANGE', 'Partnership reconstituted'),
                        ('TRUSTEE_SUCCESSION', 'Trustee succession'),
                        ('PROP_SALE', 'Proprietorship sold as going concern'),
                        ('OPERATOR_DEPARTED', 'Authorised operator left the entity'),
                        ('OTHER', 'Other — see grounds'),
                    ])),
                ('grounds', models.TextField(blank=True)),
                ('evidence_bundle_hash', models.CharField(blank=True, max_length=66)),
                ('public_notice_ends_at', models.DateTimeField(blank=True, null=True)),
                ('transfer_requested_tx_hash', models.CharField(blank=True, max_length=66)),
                ('ombudsman_order_hash', models.CharField(blank=True, max_length=66)),
                ('ombudsman_order_tx_hash', models.CharField(blank=True, max_length=66)),
                ('execution_tx_hash', models.CharField(blank=True, max_length=66)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('outgoing_operator', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='outgoing_wallet_transfers',
                    to=settings.AUTH_USER_MODEL)),
                ('incoming_operator', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='incoming_wallet_transfers',
                    to=settings.AUTH_USER_MODEL)),
                ('wallet', models.ForeignKey(
                    on_delete=models.deletion.PROTECT,
                    related_name='ownership_transfers',
                    to='wallet_access.walletactivation')),
            ],
            options={
                'db_table': 'wallet_ownership_transfer_case',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['wallet', 'status'], name='wallet_own_wal_status_idx'),
                    models.Index(fields=['status', 'created_at'], name='wallet_own_status_idx'),
                ],
            },
        ),
    ]
