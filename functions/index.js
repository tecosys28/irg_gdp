/**
 * irg_gdp Cloud Functions (firebase-functions v5 / Node 22)
 *
 * Scope:
 *   • getMICSDigest      — PUBLIC HTTPS endpoint returning aggregate metrics
 *   • getMICSDrill       — PUBLIC HTTPS endpoint for drill-down details
 *   • onUnitMint         — Firestore trigger maintaining aggregate counters
 *   • onDisputeChange    — Firestore trigger updating dispute rollups
 *   • refreshMICSDigest  — Hourly scheduled recompute
 *   • licenceStatus      — Callable: licence health check
 *
 * IPR Owner: Mr. Rohit Tidke · © 2026 Intech Research Group
 */

const { onRequest, onCall } = require('firebase-functions/v2/https');
const { onDocumentCreated, onDocumentWritten } = require('firebase-functions/v2/firestore');
const { onSchedule } = require('firebase-functions/v2/scheduler');
const { setGlobalOptions } = require('firebase-functions/v2');
const admin = require('firebase-admin');
const cors  = require('cors');

const { currentLicenceInfo } = require('./licence-guard');
// Licence guard disabled for owner-operated production deployment (irggdp project).

setGlobalOptions({ region: 'asia-south1' });

admin.initializeApp();
const db = admin.firestore();

// Public callable for ops team to check licence health.
exports.licenceStatus = onCall(async () => currentLicenceInfo());

// CORS: explicit allowlist
const ALLOWED_ORIGINS = [
  'https://irggdp.com',
  'https://www.irggdp.com',
  'https://irggdp.firebaseapp.com',
  'https://irggdp.web.app',
  'https://gov.irgecosystem.com',
  'https://irg-gov-prod.web.app',
  'http://localhost:5173',
  'http://localhost:5000',
];

const corsHandler = cors({
  origin: (origin, cb) => {
    if (!origin) return cb(null, true);
    if (ALLOWED_ORIGINS.includes(origin)) return cb(null, true);
    return cb(new Error(`Origin ${origin} not allowed`));
  },
  methods: ['GET'],
  credentials: false,
});

// Naive per-IP rate limiter (resets on cold start)
const _rlBuckets = new Map();
function rateLimited(ip, max = 30, windowMs = 60_000) {
  const now = Date.now();
  const bucket = _rlBuckets.get(ip) || [];
  const recent = bucket.filter(t => now - t < windowMs);
  recent.push(now);
  _rlBuckets.set(ip, recent);
  return recent.length > max;
}

// ── getMICSDigest ─────────────────────────────────────────────────────────────
exports.getMICSDigest = onRequest({ cors: false }, (req, res) => {
  corsHandler(req, res, async () => {
    try {
      const ip = req.headers['x-forwarded-for'] || req.ip;
      if (rateLimited(ip)) return res.status(429).json({ error: 'rate_limited' });
      const { period } = req.query;
      if (!period) return res.status(400).json({ error: 'period_required' });
      const snap = await db.collection('mics_digest').doc(period).get();
      if (!snap.exists) return res.status(404).json({ error: 'no_data_for_period', period });
      const clean = Object.fromEntries(Object.entries(snap.data()).filter(([k]) => !k.startsWith('_')));
      return res.status(200).json(clean);
    } catch (e) {
      console.error('getMICSDigest failed:', e);
      return res.status(500).json({ error: 'internal_error' });
    }
  });
});

// ── getMICSDrill ──────────────────────────────────────────────────────────────
exports.getMICSDrill = onRequest({ cors: false }, (req, res) => {
  corsHandler(req, res, async () => {
    try {
      const ip = req.headers['x-forwarded-for'] || req.ip;
      if (rateLimited(ip)) return res.status(429).json({ error: 'rate_limited' });
      const { key } = req.query;
      if (!key) return res.status(400).json({ error: 'key_required' });
      const [, slice] = key.split('-');
      if (!slice) return res.status(400).json({ error: 'invalid_key' });
      const snap = await db.collection('mics_drill').doc(slice).get();
      if (!snap.exists) return res.status(404).json({ error: 'no_drill_data', slice });
      return res.status(200).json(snap.data());
    } catch (e) {
      console.error('getMICSDrill failed:', e);
      return res.status(500).json({ error: 'internal_error' });
    }
  });
});

// ── onUnitMint ────────────────────────────────────────────────────────────────
exports.onUnitMint = onDocumentCreated('minting_records/{recordId}', async (event) => {
  const data = event.data.data();
  const grams = data.gramsPure || 0;
  const digestRef = db.collection('mics_digest').doc('mtd');
  await db.runTransaction(async tx => {
    const cur = await tx.get(digestRef);
    const existing = cur.exists ? cur.data() : {};
    const kpis = existing.kpis || {};
    const txCounts = kpis.transactions || { mint: 0, earmark: 0, swap: 0, trade: 0, redeem: 0 };
    tx.set(digestRef, {
      ...existing,
      kpis: {
        ...kpis,
        transactions: { ...txCounts, mint: (txCounts.mint || 0) + 1 },
        pureGoldGrams: (kpis.pureGoldGrams || 0) + grams,
      },
      _updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
  });
});

// ── onDisputeChange ───────────────────────────────────────────────────────────
exports.onDisputeChange = onDocumentWritten('disputes/{caseId}', async () => {
  const openSnap   = await db.collection('disputes').where('status', 'in', ['Filed', 'Under Review', 'Hearing']).get();
  const closedSnap = await db.collection('disputes').where('status', '==', 'Closed').get();
  await db.collection('mics_digest').doc('mtd').set({
    complaintsRollup: { open: openSnap.size, closed: closedSnap.size },
    _updatedAt: admin.firestore.FieldValue.serverTimestamp(),
  }, { merge: true });
});

// ── refreshMICSDigest (hourly) ────────────────────────────────────────────────
exports.refreshMICSDigest = onSchedule(
  { schedule: 'every 60 minutes', timeZone: 'Asia/Kolkata' },
  async () => {
    await db.collection('mics_digest').doc('mtd').set({
      _refreshedAt: admin.firestore.FieldValue.serverTimestamp(),
      _source: 'scheduled_refresh',
    }, { merge: true });
  }
);
