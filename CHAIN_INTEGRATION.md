# IRG_GDP ↔ IRG Chain 888101 Integration (v2.7)

This document describes the changes made to the IRG_GDP_Complete_System
repo to automatically push every transaction onto IRG Chain 888101, and
how the GDP and FTR apps share a single blockchain backend without being
merged.

---

## What changed in this repo

```
IRG_GDP_Complete_System/
├── middleware/                         [NEW]
│   ├── server.js                       ← Node.js Besu relay (HMAC auth)
│   ├── package.json
│   ├── .env.example
│   ├── k8s-deployment.yaml             ← Kubernetes manifest
│   └── README.md
├── backend/
│   ├── chain/                          [NEW Django app]
│   │   ├── models.py                   ← TxAuditLog model
│   │   ├── client.py                   ← system_submit / raw_submit gateway
│   │   ├── views.py                    ← /audit/ sink endpoint
│   │   ├── urls.py
│   │   └── migrations/0001_initial.py
│   ├── services/
│   │   └── blockchain.py               [REWRITTEN — every method now routes
│   │                                     through chain.client; signatures
│   │                                     unchanged so no call-site edits]
│   ├── core/
│   │   └── signals.py                  [EXTENDED — auto-register new user
│   │                                     wallets on 888101 after DB commit]
│   ├── settings.py                     [PATCHED — chain app registered,
│   │                                     BLOCKCHAIN_CONFIG expanded,
│   │                                     CONTRACT_ADDRESSES added]
│   └── urls.py                         [PATCHED — /api/v1/chain/ route]
```

Nothing else in the GDP codebase was touched. The 22 existing `blockchain.X(...)`
call sites across 10 modules all continue to work — they each now cause
a durable row in the `chain_tx_audit_log` table **and** a real submission
to IRG Chain 888101 via the middleware.

---

## Deployment sequence

### 1. Bring up IRG Chain 888101 (if not already running)

Use the Besu Helm + Terraform package from the linking note (v2.5). The
chain must be reachable at an internal RPC address and (optionally) a
public TLS-terminated endpoint.

### 2. Deploy the middleware

Only one instance needs to be live per environment. The `middleware/`
folder in this repo is identical to the one in the FTR repo — deploy
either copy.

```bash
cd middleware
cp .env.example .env
# edit .env — set MIDDLEWARE_SHARED_SECRET and SYSTEM_SIGNER_KEY
npm install
npm start
# or via Kubernetes:
kubectl apply -f k8s-deployment.yaml
```

Required environment variables (see `.env.example` for full list):

| Var | Purpose |
| --- | --- |
| `BESU_RPC` | Internal RPC URL of the Besu cluster |
| `IRG_CHAIN_ID` | `888101` |
| `MIDDLEWARE_SHARED_SECRET` | HMAC secret (generate: `openssl rand -hex 32`) |
| `SYSTEM_SIGNER_KEY` | Hex private key from AWS Secrets Manager / KMS |
| `AUDIT_SINK_URL` | Django endpoint: `http://<host>:8000/api/v1/chain/audit/` |
| `AUDIT_SINK_TOKEN` | Bearer token for the sink |

### 3. Configure the Django backend

Add to the Django environment:

```bash
# Must match the middleware's MIDDLEWARE_SHARED_SECRET
IRG_CHAIN_MIDDLEWARE_URL=http://irg-middleware:3100
IRG_CHAIN_MIDDLEWARE_SECRET=<same as middleware>
IRG_CHAIN_AUDIT_TOKEN=<same as middleware>
IRG_CHAIN_ALLOW_SIMULATE=False   # in production

# Contract addresses (populate after each deployment)
ADDR_TGDP_MINTING=0x...
ADDR_FTR_REDEMPTION=0x...
ADDR_SUPER_CORPUS=0x...
ADDR_IDENTITY_REGISTRY=0x...
# ... (see settings.py → CONTRACT_ADDRESSES)
```

Run migrations:

```bash
cd backend
python manage.py migrate chain
```

### 4. Verify

```bash
# Middleware health
curl http://irg-middleware:3100/health
# Expected: {"status":"ok","chainId":888101,...}

# Django → middleware round-trip (triggers a system tx)
python manage.py shell -c "
from services.blockchain import BlockchainService
print(BlockchainService().update_lbma_rate('AU','6250.00','2026-04-17'))
"
# Expected: a 0x... tx hash

# Audit log row
python manage.py shell -c "
from chain.models import TxAuditLog
print(TxAuditLog.objects.latest('created_at').__dict__)
"
# Expected: status='SUBMITTED', module='oracle', action='update_lbma_rate', tx_hash=0x...
```

---

## Security notes

1. **Private keys never travel over HTTP.** Two submission modes only:
   - `raw` — user device already signed the tx; middleware just forwards
   - `system` — middleware signs using a key loaded from env / KMS once at startup
   The original linking note (v2.3) showed `privateKey` in request bodies —
   this design deliberately does not do that.
2. **HMAC auth between Django and the middleware** using
   `MIDDLEWARE_SHARED_SECRET`. Requests older than 5 minutes are rejected.
3. **Chain-ID enforcement in the middleware** — any `raw` tx whose embedded
   chainId is not 888101 is rejected before broadcast, so a misconfigured
   client cannot accidentally write to the wrong network.
4. **Idempotency on `clientTxId`** — retry storms don't produce duplicate
   on-chain writes.

---

## Relationship to the FTR repo

The `irg-ftr-platform-v5` repo contains:
- An identical copy of `middleware/` (for self-containment).
- A TypeScript equivalent of `chain.client` at
  `backend/src/services/chain-submit.service.ts`.
- The same `ChainTxAudit` schema (Prisma model + migration).
- A matching `/api/v1/chain/audit` sink route.
- Updates to the swap and registration modules so every FTR transaction
  also flows through the gateway and is audit-logged.

In production both apps point at **one** middleware instance, which
points at **one** Besu cluster. Apps stay parallel — no merging required.

---

**IPR Owner: Rohit Tidke | © 2026 Intech Research Group**
