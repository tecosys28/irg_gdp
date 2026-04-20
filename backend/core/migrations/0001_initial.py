from django.conf import settings
from django.db import migrations, models
import django.contrib.auth.models
import django.contrib.auth.validators
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, verbose_name='superuser status')),
                ('username', models.CharField(
                    error_messages={'unique': 'A user with that username already exists.'},
                    help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
                    max_length=150,
                    unique=True,
                    validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                    verbose_name='username',
                )),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('firebase_uid', models.CharField(blank=True, db_index=True, max_length=128, null=True, unique=True)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('mobile', models.CharField(
                    blank=True, max_length=15,
                    validators=[django.core.validators.RegexValidator(r'^\+?[0-9]{10,14}$', 'Enter a valid mobile number')],
                )),
                ('kyc_tier', models.CharField(
                    choices=[('NONE', 'Not Verified'), ('BASIC', 'Basic KYC'), ('ENHANCED', 'Enhanced KYC'), ('FULL', 'Full KYC')],
                    default='NONE', max_length=10,
                )),
                ('aadhaar_verified', models.BooleanField(default=False)),
                ('pan_verified', models.BooleanField(default=False)),
                ('bank_verified', models.BooleanField(default=False)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('state', models.CharField(blank=True, max_length=100)),
                ('pincode', models.CharField(blank=True, max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('blockchain_address', models.CharField(blank=True, max_length=66, null=True)),
                ('groups', models.ManyToManyField(
                    blank=True,
                    help_text='The groups this user belongs to.',
                    related_name='user_set',
                    related_query_name='user',
                    to='auth.group',
                    verbose_name='groups',
                )),
                ('user_permissions', models.ManyToManyField(
                    blank=True,
                    help_text='Specific permissions for this user.',
                    related_name='user_set',
                    related_query_name='user',
                    to='auth.permission',
                    verbose_name='user permissions',
                )),
            ],
            options={
                'db_table': 'core_user',
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('role', models.CharField(
                    choices=[
                        ('JEWELER', 'Jeweler'), ('HOUSEHOLD', 'Household (Earmarking)'),
                        ('INVESTOR', 'IRG_GDP/FTR Buyer'), ('RETURNEE', 'Jewelry Returnee'),
                        ('DESIGNER', 'Jewelry Designer'), ('OMBUDSMAN', 'Ombudsman'),
                        ('CONSULTANT', 'Consultant'), ('MARKETMAKER', 'Market Maker'),
                        ('LICENSEE', 'Licensee'), ('MINTER', 'FTR Minter'),
                        ('TRUSTEE', 'Trustee Banker'), ('ADMIN', 'Administrator'),
                    ],
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[('PENDING', 'Pending Approval'), ('ACTIVE', 'Active'), ('SUSPENDED', 'Suspended'), ('REVOKED', 'Revoked')],
                    default='PENDING', max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='roles', to=settings.AUTH_USER_MODEL)),
                ('approved_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='approved_roles',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'core_user_role',
                'unique_together': {('user', 'role')},
            },
        ),
        migrations.CreateModel(
            name='KYCDocument',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('document_type', models.CharField(
                    choices=[
                        ('AADHAAR', 'Aadhaar Card'), ('PAN', 'PAN Card'), ('PASSPORT', 'Passport'),
                        ('VOTER_ID', 'Voter ID'), ('DRIVING_LICENSE', 'Driving License'),
                        ('BANK_STATEMENT', 'Bank Statement'), ('GST_CERT', 'GST Certificate'),
                        ('JEWELER_LICENSE', 'Jeweler License'), ('COMPANY_REG', 'Company Registration'),
                        ('ADDRESS_PROOF', 'Address Proof'),
                    ],
                    max_length=20,
                )),
                ('document_number', models.CharField(max_length=50)),
                ('document_file', models.FileField(blank=True, null=True, upload_to='kyc_documents/')),
                ('status', models.CharField(
                    choices=[('UPLOADED', 'Uploaded'), ('UNDER_REVIEW', 'Under Review'), ('VERIFIED', 'Verified'), ('REJECTED', 'Rejected')],
                    default='UPLOADED', max_length=20,
                )),
                ('rejection_reason', models.TextField(blank=True)),
                ('blockchain_hash', models.CharField(blank=True, max_length=66, null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_documents', to=settings.AUTH_USER_MODEL)),
                ('verified_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='verified_documents',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'core_kyc_document',
            },
        ),
        migrations.CreateModel(
            name='JewelerProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('business_name', models.CharField(max_length=200)),
                ('license_number', models.CharField(max_length=50, unique=True)),
                ('gst_number', models.CharField(max_length=20)),
                ('pan_number', models.CharField(max_length=10)),
                ('business_address', models.TextField()),
                ('years_in_business', models.PositiveIntegerField(default=0)),
                ('tier', models.CharField(
                    choices=[('BRONZE', 'Bronze'), ('SILVER', 'Silver'), ('GOLD', 'Gold'), ('PLATINUM', 'Platinum')],
                    default='BRONZE', max_length=10,
                )),
                ('corpus_balance', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('rating', models.DecimalField(decimal_places=2, default=0, max_digits=3)),
                ('blockchain_address', models.CharField(blank=True, max_length=66, null=True)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='jeweler_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'core_jeweler_profile'},
        ),
        migrations.CreateModel(
            name='DesignerProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('display_name', models.CharField(max_length=100)),
                ('portfolio_url', models.URLField(blank=True)),
                ('qualification', models.CharField(
                    choices=[('GIA', 'GIA Certified'), ('NIFT', 'NIFT Graduate'), ('SELF', 'Self-taught'), ('OTHER', 'Other Institute')],
                    max_length=10,
                )),
                ('experience_years', models.PositiveIntegerField(default=0)),
                ('specialization', models.CharField(
                    choices=[('GOLD', 'Gold Jewelry'), ('DIAMOND', 'Diamond Jewelry'), ('SILVER', 'Silver Jewelry'),
                             ('KUNDAN', 'Kundan/Polki'), ('CONTEMPORARY', 'Contemporary'), ('TRADITIONAL', 'Traditional'), ('ALL', 'All Categories')],
                    max_length=20,
                )),
                ('reference_jeweler_1', models.CharField(blank=True, max_length=200)),
                ('reference_jeweler_2', models.CharField(blank=True, max_length=200)),
                ('tier', models.CharField(
                    choices=[('EMERGING', 'Emerging'), ('ESTABLISHED', 'Established'), ('MASTER', 'Master')],
                    default='EMERGING', max_length=15,
                )),
                ('total_designs', models.PositiveIntegerField(default=0)),
                ('total_orders', models.PositiveIntegerField(default=0)),
                ('royalties_earned', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('copyright_count', models.PositiveIntegerField(default=0)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='designer_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'core_designer_profile'},
        ),
        migrations.CreateModel(
            name='LicenseeProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('entity_name', models.CharField(max_length=200)),
                ('registration_number', models.CharField(max_length=50, unique=True)),
                ('territory', models.CharField(max_length=200)),
                ('investment_capacity', models.DecimalField(decimal_places=2, max_digits=15)),
                ('industry_experience', models.TextField()),
                ('license_valid_from', models.DateField(blank=True, null=True)),
                ('license_valid_until', models.DateField(blank=True, null=True)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='licensee_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'core_licensee_profile'},
        ),
        migrations.CreateModel(
            name='OmbudsmanProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('qualification', models.CharField(max_length=200)),
                ('bar_council_registration', models.CharField(blank=True, max_length=50)),
                ('experience_years', models.PositiveIntegerField(default=0)),
                ('professional_references', models.TextField()),
                ('cases_resolved', models.PositiveIntegerField(default=0)),
                ('avg_resolution_days', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ombudsman_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'core_ombudsman_profile'},
        ),
        migrations.CreateModel(
            name='MarketMakerProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('entity_name', models.CharField(max_length=200)),
                ('registration_number', models.CharField(max_length=50)),
                ('available_capital', models.DecimalField(decimal_places=2, max_digits=15)),
                ('trading_experience_years', models.PositiveIntegerField(default=0)),
                ('total_volume', models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ('current_positions', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='marketmaker_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'core_marketmaker_profile'},
        ),
        migrations.CreateModel(
            name='TrusteeBankerProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('bank_name', models.CharField(max_length=200)),
                ('banking_license', models.CharField(max_length=50)),
                ('designation', models.CharField(max_length=100)),
                ('branch_details', models.CharField(max_length=200)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='trustee_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'core_trustee_profile'},
        ),
    ]
