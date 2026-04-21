"""
IRG_GDP Master System - Django Settings
IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group

COMPLIANCE: No banned words used throughout the system.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DEBUG = os.environ.get('DJANGO_DEBUG', os.environ.get('DEBUG', 'False')) == 'True'

_secret_key = os.environ.get('DJANGO_SECRET_KEY', '')
if not _secret_key:
    if DEBUG:
        _secret_key = 'dev-insecure-key-do-not-use-in-production-irg-gdp'
    else:
        raise RuntimeError(
            'DJANGO_SECRET_KEY environment variable must be set. '
            'Generate one with: python -c "from django.core.management.utils '
            'import get_random_secret_key; print(get_random_secret_key())"'
        )
SECRET_KEY = _secret_key

_allowed = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
if _allowed == '*' and not DEBUG:
    raise RuntimeError(
        'DJANGO_ALLOWED_HOSTS=* is not permitted in production. '
        'Set it to a comma-separated list of actual hostnames.'
    )
ALLOWED_HOSTS = ['*'] if _allowed == '*' else [h.strip() for h in _allowed.split(',') if h.strip()]

CSRF_TRUSTED_ORIGINS = [
    'http://43.205.237.197',
    'https://43.205.237.197',
    'https://irggdp.web.app',
    'https://irggdp.firebaseapp.com',
    'https://irggdp.com',
    'https://www.irggdp.com',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    # IRG_GDP Apps
    'core',
    'irg_gdp',
    'irg_jr',
    'irg_jdb',
    'irg_gic',
    'oracle',
    'corpus',
    'governance',
    'disputes',
    'recall',
    'chain',
    'payment_bridge',
    'wallet_access',
]

MIDDLEWARE = [
    # Licence enforcement runs first so an unlicensed deployment cannot
    # serve any response.
    'chain.licence_middleware.LicenceEnforcementMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'wallet_access.middleware.WalletActivityMiddleware',
]

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wsgi.application'

# Database — uses Postgres when DB_HOST is set, SQLite otherwise (dev/demo)
_db_host = os.environ.get('DB_HOST', '')
if _db_host:
    _db_password = os.environ.get('DB_PASSWORD', '')
    if not _db_password:
        raise RuntimeError(
            'DB_PASSWORD environment variable must be set when DB_HOST is configured.'
        )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'irg_gdp_db'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': _db_password,
            'HOST': _db_host,
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom User Model
AUTH_USER_MODEL = 'core.User'

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework — Firebase ID token authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.firebase_auth.FirebaseAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CORS
CORS_ALLOWED_ORIGINS = [
    'https://irggdp.com',
    'https://www.irggdp.com',
    'https://irggdp.firebaseapp.com',
    'https://irggdp.web.app',
    'http://localhost:5000',
    'http://localhost:5173',
]
# Never open CORS to all origins — even in DEBUG mode the backend may be
# accessible from untrusted sources via port-forwarding or tunnelling.
CORS_ALLOW_ALL_ORIGINS = False

# Firebase Admin SDK — initialised once in core/apps.py
FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON', '')
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'irggdp')


# ═══════════════════════════════════════════════════════════════════════════════
# IRG_GDP SYSTEM CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

IRG_GDP_CONFIG = {
    # Minting Parameters
    'SALEABLE_PER_GRAM': 9,
    'RESERVE_PER_GRAM': 1,
    
    # Corpus Fund
    'CORPUS_CONTRIBUTION_PERCENT': 20,
    'PHYSICAL_GOLD_PERCENT': 5,
    'OTHER_INVESTMENTS_PERCENT': 95,
    
    # Bonus & Earmarking
    'MINTER_SHARE_PERCENT': 6,
    'EARMARKING_PERCENTAGE': 11,
    
    # Lock-in Periods (months)
    'LOCK_IN_NEW_MONTHS': 0,
    'LOCK_IN_OLD_MONTHS': 12,
    'LOCK_IN_REMADE_MONTHS': 6,
    
    # Designer Royalties
    'ROYALTY_EMERGING_PERCENT': 2,
    'ROYALTY_ESTABLISHED_PERCENT': 3,
    'ROYALTY_MASTER_PERCENT': 5,
    
    # SCF Facilitation
    'SCF_FACILITATION_PERCENT': 7,
    
    # Gold Purity Factors
    'PURITY_24K': 1.0,
    'PURITY_22K': 0.9167,
    'PURITY_18K': 0.75,
    'PURITY_14K': 0.5833,
}

# Super CF Bank Account
SUPER_CF_ACCOUNT = {
    'ACCOUNT_NAME': 'Intech Research Group',
    'ACCOUNT_NUMBER': '99620200000108',
    'ACCOUNT_TYPE': 'Current Account',
    'BANK_NAME': 'Bank of Baroda',
    'BRANCH': 'Santacruz East',
    'CITY': 'Mumbai',
    'POSTAL_CODE': '400 055',
    'COUNTRY': 'INDIA',
    'SWIFT_CODE': 'BARB0DBSCRU',
    'IFSC_CODE': 'BARB0DBSCRU',
}

# Blockchain Configuration
BLOCKCHAIN_CONFIG = {
    'CHAIN_ID': 888101,
    'CHAIN_NAME': 'IRG Chain',
    'CONSENSUS': 'PBFT+Raft',
    'RPC_URL': os.environ.get('BLOCKCHAIN_RPC', 'http://localhost:8545'),

    # ── Submission middleware (auto-links every transaction to IRG Chain 888101) ──
    # URL of the Node.js middleware service that lives in /middleware/.
    # Leave blank in local dev to use simulate-only mode.
    'MIDDLEWARE_URL': os.environ.get('IRG_CHAIN_MIDDLEWARE_URL', ''),

    # Shared HMAC secret — must match the middleware's MIDDLEWARE_SHARED_SECRET.
    # Generate with: openssl rand -hex 32
    'MIDDLEWARE_SHARED_SECRET': os.environ.get('IRG_CHAIN_MIDDLEWARE_SECRET', ''),

    # Bearer token the middleware uses when POSTing audit callbacks back to
    # Django's /api/v1/chain/audit/ endpoint.
    'AUDIT_SINK_TOKEN': os.environ.get('IRG_CHAIN_AUDIT_TOKEN', ''),

    # Safety valves.
    'SUBMIT_TIMEOUT_SECONDS': float(os.environ.get('IRG_CHAIN_SUBMIT_TIMEOUT', '15')),
    'SUBMIT_MAX_RETRIES': int(os.environ.get('IRG_CHAIN_SUBMIT_RETRIES', '3')),

    # If True, fall back to deterministic simulated hashes when the middleware
    # is unreachable. Must be set explicitly — never inherits from DEBUG so a
    # misconfigured production environment doesn't silently write fake hashes.
    'ALLOW_SIMULATE': os.environ.get('IRG_CHAIN_ALLOW_SIMULATE', 'False') == 'True',
}

# ─────────────────────────────────────────────────────────────────────────────
# CONTRACT ADDRESSES ON IRG CHAIN 888101
# Populated after each deployment. Blank entries trigger simulate-mode audit
# rows instead of real on-chain writes (useful in dev/CI).
# ─────────────────────────────────────────────────────────────────────────────
CONTRACT_ADDRESSES = {
    # Identity
    'IdentityRegistry':       os.environ.get('ADDR_IDENTITY_REGISTRY', ''),
    'IPRLicense':             os.environ.get('ADDR_IPR_LICENSE', ''),
    'WalletRecoveryEvents':   os.environ.get('ADDR_WALLET_RECOVERY_EVENTS', ''),
    'LegalEntityRegistry':    os.environ.get('ADDR_LEGAL_ENTITY_REGISTRY', ''),
    # TGDP
    'TGDPMinting':            os.environ.get('ADDR_TGDP_MINTING', ''),
    'TGDPToken':              os.environ.get('ADDR_TGDP_TOKEN', ''),
    # FTR
    'FTRToken':               os.environ.get('ADDR_FTR_TOKEN', ''),
    'FTRRedemption':          os.environ.get('ADDR_FTR_REDEMPTION', ''),
    'FTRRecall':              os.environ.get('ADDR_FTR_RECALL', ''),
    'FTRClassRegistry':       os.environ.get('ADDR_FTR_CLASS_REGISTRY', ''),
    'FTRMintingApproval':     os.environ.get('ADDR_FTR_MINTING_APPROVAL', ''),
    'OmbudsmanRegistry':      os.environ.get('ADDR_OMBUDSMAN_REGISTRY', ''),
    'EscrowVault':            os.environ.get('ADDR_ESCROW_VAULT', ''),
    # Corpus
    'SuperCorpusFund':        os.environ.get('ADDR_SUPER_CORPUS', ''),
    'CorpusFundFactory':      os.environ.get('ADDR_CORPUS_FUND_FACTORY', ''),
    'TrusteeBanker':          os.environ.get('ADDR_TRUSTEE_BANKER', ''),
    'CFRiskMonitor':          os.environ.get('ADDR_CF_RISK_MONITOR', ''),
    # Governance
    'Governance':             os.environ.get('ADDR_GOVERNANCE', ''),
    'GovernanceParameters':   os.environ.get('ADDR_GOVERNANCE_PARAMS', ''),
    'IRGMultisig':            os.environ.get('ADDR_IRG_MULTISIG', ''),
    'IRGTimelock':            os.environ.get('ADDR_IRG_TIMELOCK', ''),
    # Enforcement / dispute
    'DisputeRegistry':        os.environ.get('ADDR_DISPUTE_REGISTRY', ''),
    'LawFirmRegistry':        os.environ.get('ADDR_LAW_FIRM_REGISTRY', ''),
    'SpecialRecoveryCF':      os.environ.get('ADDR_SPECIAL_RECOVERY_CF', ''),
    # Oracle
    'LBMAOracle':             os.environ.get('ADDR_LBMA_ORACLE', ''),
    'BenchmarkOracle':        os.environ.get('ADDR_BENCHMARK_ORACLE', ''),
    'VRFCoordinator':         os.environ.get('ADDR_VRF_COORDINATOR', ''),
    'OracleNodePool':         os.environ.get('ADDR_ORACLE_NODE_POOL', ''),
    # Recall
    'RecallRegistry':         os.environ.get('ADDR_RECALL_REGISTRY', ''),
    # GIC
    'GICLedger':              os.environ.get('ADDR_GIC_LEDGER', ''),
    'GICRedemption':          os.environ.get('ADDR_GIC_REDEMPTION', ''),
    'LicenseeRegistry':       os.environ.get('ADDR_LICENSEE_REGISTRY', ''),
    # TDiR
    'TDiRToken':              os.environ.get('ADDR_TDIR_TOKEN', ''),
    'TDiRRedemption':         os.environ.get('ADDR_TDIR_REDEMPTION', ''),
    # Node
    'NodeAdmission':          os.environ.get('ADDR_NODE_ADMISSION', ''),
    # Utility
    'SystemPause':            os.environ.get('ADDR_SYSTEM_PAUSE', ''),
    # Registries
    'JewelerRegistry':        os.environ.get('ADDR_JEWELER_REGISTRY', ''),
    'CertifierRegistry':      os.environ.get('ADDR_CERTIFIER_REGISTRY', ''),
    # Legacy / placeholder keys kept for backward compat with old call sites
    'P2PGuaranteedSettlement': os.environ.get('ADDR_P2P_SETTLEMENT', ''),
    'JRRegistry':             os.environ.get('ADDR_JR_REGISTRY', ''),
    'JDBRegistry':            os.environ.get('ADDR_JDB_REGISTRY', ''),
    'DeviceP2PRegistry':      os.environ.get('ADDR_DEVICE_P2P', ''),
}

# Path to the irg_chain ABI directory (populated by node scripts/export-abis.js)
# Example: IRG_CHAIN_ABI_DIR=/opt/irg_chain/abis
# Leave blank to auto-discover a sibling irg_chain/abis directory.
IRG_CHAIN_ABI_DIR = os.environ.get('IRG_CHAIN_ABI_DIR', '')

# ─────────────────────────────────────────────────────────────────────────────
# HTTPS / SECURITY HEADERS (production only)
# ─────────────────────────────────────────────────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = False   # SSL terminated by Firebase/CDN; EC2 has no cert on 443
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 0               # no HSTS — no SSL cert on EC2
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_SECURE = False         # HTTP-only EC2; cookies must work over plain HTTP
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SECURE = False            # same — no SSL on EC2
    CSRF_COOKIE_HTTPONLY = False
