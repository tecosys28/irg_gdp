# IRG Chain 888101 — Submission Middleware (GDP copy)

Small Node.js service that sits between the Django backend and the Besu
RPC. Its job is to:

1. Accept `raw` (already-signed) transactions from user devices via the
   Django backend and forward them to Besu using `eth_sendRawTransaction`.
2. Sign and submit `system` transactions that the Django backend itself
   originates (corpus deposits, oracle updates, governance execution,
   recall events, dispute resolutions). The signer key is loaded at
   startup from env / AWS Secrets Manager — it is never accepted in a
   request body.
3. Retry-safe via `clientTxId` idempotency keys.
4. Push every successful submission back to Django's audit sink for DB
   storage.

## Why this lives inside the GDP repo (and also inside the FTR repo)

You asked for each app to be self-contained. Both repos ship an
identical middleware so either can bring up the service on its own.
In production you only need **one** running middleware instance per
environment — point both the Django backend and the FTR Node backend
at the same URL. The mirrored copy in the FTR repo is a backup.

## Quick start (local dev)

```bash
cd middleware
cp .env.example .env
# edit .env — set MIDDLEWARE_SHARED_SECRET and (optional) SYSTEM_SIGNER_KEY
npm install
npm start
```

## Deploy to EKS

```bash
kubectl apply -f k8s-deployment.yaml
# The ConfigMap `irg-middleware-src` is populated separately via:
kubectl -n irg-chain create configmap irg-middleware-src \
    --from-file=server.js --from-file=package.json --from-file=package-lock.json
```

## Security notes

- `MIDDLEWARE_SHARED_SECRET` must match `IRG_CHAIN_MIDDLEWARE_SECRET` in
  the Django and FTR backends. HMAC-signs every request.
- `SYSTEM_SIGNER_KEY` is the only key this service ever holds. It pays
  gas for backend-originated tx only. It must be scoped narrowly on-chain
  (grant it only the operator roles it actually needs).
- The middleware refuses any submission whose embedded `chainId` does
  not equal 888101, so a misconfigured client cannot accidentally
  broadcast to the wrong chain.

## API

`POST /submit-tx` — see `server.js` header for request shapes.
`GET /tx/:hash` — receipt lookup.
`GET /health` — liveness + chainId sanity check.
