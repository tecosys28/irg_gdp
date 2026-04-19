/**
 * IRG Chain 888101 — Transaction Submission Middleware
 *
 * Design principles (important — deviates deliberately from the original
 * linking note which showed `privateKey` being sent in the request body):
 *
 *   1. The middleware NEVER accepts a raw private key over HTTP.
 *      Two submission modes are supported:
 *
 *      a) "raw"      — caller already signed the transaction on-device;
 *                      middleware only forwards the signed hex blob via
 *                      eth_sendRawTransaction. This is the P2P mobile path.
 *
 *      b) "system"   — backend-originated system transactions (corpus
 *                      settlements, oracle updates, recalls, governance
 *                      executions). The signer key is loaded ONCE at
 *                      startup from env / secrets manager, never accepted
 *                      from the caller, and never logged.
 *
 *   2. All submissions are idempotent on `clientTxId` so retry storms
 *      do not produce duplicate on-chain writes.
 *
 *   3. Every submission is forwarded back to the Django backend's
 *      `/api/v1/chain/audit/` sink so the DB has a permanent record
 *      even if the middleware process is restarted.
 *
 *   4. Simple HMAC shared-secret auth between the Django backend and
 *      this middleware, because they run inside the same private VPC
 *      and do not need full mTLS for this internal hop.
 *
 * IPR Owner: Rohit Tidke | (c) 2026 Intech Research Group
 */

'use strict';

require('dotenv').config();

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const crypto = require('crypto');
const rateLimit = require('express-rate-limit');
const pino = require('pino');
const { JsonRpcProvider, Wallet, Transaction } = require('ethers');

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

// ─────────────────────────────────────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────────────────────────────────────

const CHAIN_ID = parseInt(process.env.IRG_CHAIN_ID || '888101', 10);
const RPC_URL = process.env.BESU_RPC || 'http://irg-rpc-service:8545';
const PORT = parseInt(process.env.PORT || '3100', 10);
const SHARED_SECRET = process.env.MIDDLEWARE_SHARED_SECRET || '';
const SYSTEM_SIGNER_KEY = process.env.SYSTEM_SIGNER_KEY || ''; // loaded from KMS
const AUDIT_SINK_URL = process.env.AUDIT_SINK_URL || '';      // Django callback
const AUDIT_SINK_TOKEN = process.env.AUDIT_SINK_TOKEN || '';

if (!SHARED_SECRET) {
  logger.warn('MIDDLEWARE_SHARED_SECRET is empty — refusing to authenticate requests. ' +
              'Set this before production use.');
}

// ─────────────────────────────────────────────────────────────────────────────
// PROVIDER + SYSTEM SIGNER
// ─────────────────────────────────────────────────────────────────────────────

const provider = new JsonRpcProvider(RPC_URL, CHAIN_ID, {
  staticNetwork: true,
});

let systemSigner = null;
if (SYSTEM_SIGNER_KEY) {
  try {
    systemSigner = new Wallet(SYSTEM_SIGNER_KEY, provider);
    logger.info({ address: systemSigner.address }, 'System signer loaded');
  } catch (err) {
    logger.error({ err: err.message }, 'Failed to initialise system signer');
  }
} else {
  logger.warn('No SYSTEM_SIGNER_KEY set — only "raw" mode will work.');
}

// ─────────────────────────────────────────────────────────────────────────────
// IDEMPOTENCY CACHE (in-memory; replace with Redis in cluster deployments)
// ─────────────────────────────────────────────────────────────────────────────

const idempotency = new Map();
const IDEMPOTENCY_TTL_MS = 15 * 60 * 1000;

function rememberIdempotent(key, result) {
  idempotency.set(key, { result, expires: Date.now() + IDEMPOTENCY_TTL_MS });
}
function recallIdempotent(key) {
  const hit = idempotency.get(key);
  if (!hit) return null;
  if (hit.expires < Date.now()) {
    idempotency.delete(key);
    return null;
  }
  return hit.result;
}
setInterval(() => {
  const now = Date.now();
  for (const [k, v] of idempotency.entries()) {
    if (v.expires < now) idempotency.delete(k);
  }
}, 60 * 1000).unref();

// ─────────────────────────────────────────────────────────────────────────────
// AUTH — HMAC of body + timestamp with shared secret
// ─────────────────────────────────────────────────────────────────────────────

function verifyHmac(req, res, next) {
  if (!SHARED_SECRET) {
    return res.status(503).json({ success: false, error: 'middleware_not_configured' });
  }
  const signature = req.header('X-IRG-Signature') || '';
  const timestamp = req.header('X-IRG-Timestamp') || '';
  if (!signature || !timestamp) {
    return res.status(401).json({ success: false, error: 'missing_auth_headers' });
  }
  const age = Math.abs(Date.now() - parseInt(timestamp, 10));
  if (!Number.isFinite(age) || age > 5 * 60 * 1000) {
    return res.status(401).json({ success: false, error: 'stale_or_invalid_timestamp' });
  }
  const raw = `${timestamp}.${JSON.stringify(req.body || {})}`;
  const expected = crypto.createHmac('sha256', SHARED_SECRET).update(raw).digest('hex');
  // constant-time compare
  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    return res.status(401).json({ success: false, error: 'bad_signature' });
  }
  next();
}

// ─────────────────────────────────────────────────────────────────────────────
// AUDIT FORWARDER — pushes tx result back to Django for durable storage
// ─────────────────────────────────────────────────────────────────────────────

async function forwardAudit(record) {
  if (!AUDIT_SINK_URL) return;
  try {
    await fetch(AUDIT_SINK_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${AUDIT_SINK_TOKEN}`,
      },
      body: JSON.stringify(record),
    });
  } catch (err) {
    logger.warn({ err: err.message, clientTxId: record.clientTxId },
                'Audit sink unreachable — Django will reconcile from chain on next sweep');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SUBMISSION ROUTES
// ─────────────────────────────────────────────────────────────────────────────

const app = express();
app.use(helmet());
app.use(cors({ origin: (process.env.CORS_ORIGINS || '').split(',').filter(Boolean) }));
app.use(express.json({ limit: '256kb' }));

app.use(rateLimit({
  windowMs: 60 * 1000,
  max: 600,
  standardHeaders: true,
  legacyHeaders: false,
}));

app.get('/health', async (_req, res) => {
  try {
    const network = await provider.getNetwork();
    res.json({
      status: 'ok',
      chainId: Number(network.chainId),
      expectedChainId: CHAIN_ID,
      systemSigner: systemSigner ? systemSigner.address : null,
      rpc: RPC_URL,
    });
  } catch (err) {
    res.status(503).json({ status: 'degraded', error: err.message });
  }
});

/**
 * POST /submit-tx
 *
 * Body (mode = "raw"):
 *   { mode: "raw", clientTxId: "...", signedTx: "0x..." }
 *
 * Body (mode = "system"):
 *   { mode: "system", clientTxId: "...", to: "0x...", data: "0x...", value?: "0", module, action, meta? }
 */
app.post('/submit-tx', verifyHmac, async (req, res) => {
  const { mode, clientTxId } = req.body || {};
  if (!clientTxId) {
    return res.status(400).json({ success: false, error: 'clientTxId_required' });
  }

  const cached = recallIdempotent(clientTxId);
  if (cached) {
    return res.json({ ...cached, idempotent: true });
  }

  try {
    let txHash;
    if (mode === 'raw') {
      if (!req.body.signedTx || !req.body.signedTx.startsWith('0x')) {
        return res.status(400).json({ success: false, error: 'signedTx_required' });
      }
      // Verify signed tx is actually for chain 888101 before forwarding
      const parsed = Transaction.from(req.body.signedTx);
      if (parsed.chainId !== BigInt(CHAIN_ID)) {
        return res.status(400).json({
          success: false,
          error: 'wrong_chain_id',
          expected: CHAIN_ID,
          got: Number(parsed.chainId),
        });
      }
      const sent = await provider.broadcastTransaction(req.body.signedTx);
      txHash = sent.hash;
    } else if (mode === 'system') {
      if (!systemSigner) {
        return res.status(503).json({ success: false, error: 'system_signer_unavailable' });
      }
      const { to, data, value } = req.body;
      if (!to) return res.status(400).json({ success: false, error: 'to_required' });
      const tx = await systemSigner.sendTransaction({
        to,
        data: data || '0x',
        value: value ? BigInt(value) : 0n,
        chainId: CHAIN_ID,
      });
      txHash = tx.hash;
    } else {
      return res.status(400).json({ success: false, error: 'unknown_mode' });
    }

    const result = { success: true, txHash, chainId: CHAIN_ID };
    rememberIdempotent(clientTxId, result);

    // Fire-and-forget audit push to Django
    forwardAudit({
      clientTxId,
      txHash,
      chainId: CHAIN_ID,
      mode,
      module: req.body.module || null,
      action: req.body.action || null,
      meta: req.body.meta || null,
      submittedAt: new Date().toISOString(),
    });

    logger.info({ clientTxId, txHash, module: req.body.module }, 'tx_submitted');
    return res.json(result);
  } catch (err) {
    logger.error({ clientTxId, err: err.message }, 'tx_submit_failed');
    return res.status(502).json({ success: false, error: err.message });
  }
});

/**
 * GET /tx/:hash — convenience lookup so the backend can reconcile status
 */
app.get('/tx/:hash', verifyHmac, async (req, res) => {
  try {
    const receipt = await provider.getTransactionReceipt(req.params.hash);
    if (!receipt) return res.json({ found: false });
    res.json({
      found: true,
      blockNumber: receipt.blockNumber,
      status: receipt.status,
      gasUsed: receipt.gasUsed.toString(),
    });
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  logger.info({ port: PORT, chainId: CHAIN_ID, rpc: RPC_URL },
              'IRG GDP chain middleware listening');
});
