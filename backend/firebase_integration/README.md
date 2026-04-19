# firebase_integration — IRG_GDP Django App

Bridges Django to the dedicated **irg-gdp-prod** Firebase project.

## What this app does

1. **Initialises** `firebase_admin` on Django startup (see `admin_init.py`).
2. **Mirrors** select Django models into Firestore via `post_save` signals
   (see `firestore_sync.py`) so the `mics_digest` collection read by the
   Advisory Board's MICS stays current.
3. **Authenticates** Firebase ID tokens on incoming API requests via
   `FirebaseAuthMiddleware` (see `auth_middleware.py`).

## Environment variables

| Var | Purpose |
|---|---|
| `FIREBASE_PROJECT_ID` | `irg-gdp-prod` (or staging equivalent) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service-account JSON |
| `FIREBASE_CREDENTIALS_JSON` | Alternative: raw JSON in an env var (Cloud Run friendly) |

If neither credentials var is set, `firebase_admin` falls back to
Application Default Credentials — which Just Works on Cloud Run.

## Installation in settings.py

```python
INSTALLED_APPS += ['firebase_integration']

MIDDLEWARE += ['firebase_integration.auth_middleware.FirebaseAuthMiddleware']
```

## Install dependency

```bash
pip install firebase-admin>=6.5.0
```

## Sovereignty reminder

This app writes to **irg-gdp-prod's** Firestore only. It never writes to
irg-gov-prod, irg-ftr-prod, irg-chain-prod, or irg-dac-prod. Cross-project
communication happens only via the public `getMICSDigest` Cloud Function.
