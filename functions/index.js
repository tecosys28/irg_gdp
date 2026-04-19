/**
 * irg_gdp Cloud Functions
 *
 * Scope:
 *   • getMICSDigest  — PUBLIC HTTPS endpoint returning aggregate metrics
 *                      for this ecosystem. Consumed by irg_gov's Advisory
 *                      Board MICS via its federation client.
 *   • getMICSDrill   — PUBLIC HTTPS endpoint returning drill-down details
 *                      when the AB member clicks through from an aggregate.
 *   • onUnitMint     — Firestore trigger that maintains aggregate counters.
 *   • onDisputeChange — Firestore trigger that updates dispute rollups.
 *
 * CORS policy: both public endpoints allow gov.irgecosystem.com (prod) and
 * staging equivalents. Rate-limited per IP to prevent scraping.
 *
 * IPR Owner: Mr. Rohit Tidke · © 2026 Intech Research Group
 */

const functions = require('firebase-functions');
const admin     = require('firebase-admin');
const cors      = require('cors');

// ─────────────────────────────────────────────────────────────────────────────
// Licence guard — verified at module load. If the deployment is unlicensed,
// this exits during load and Firebase refuses to register any function.
// ─────────────────────────────────────────────────────────────────────────────
const { verifyLicenceOrDie, currentLicenceInfo } = require('./licence-guard');
if (process.env.FUNCTIONS_EMULATOR !== 'true') {
  verifyLicenceOrDie('GDP');
}

admin.initializeApp();
const db = admin.firestore();

// Public callable for the licensee's ops team to check licence health.
exports.licenceStatus = functions.https.onCall(async () => currentLicenceInfo());

// CORS: explicit allowlist of origins that may call our digest endpoint
const ALLOWED_ORIGINS = [
  'https://irggdp.com',
  'https://www.irggdp.com',
  'https://irggdp.firebaseapp.com',
  'https://irggdp.web.app',
  'https://gov.irgecosystem.com',
  'https://irg-gov-prod.web.app',
  'https://irg-gov-prod.firebaseapp.com',
  'https://irg-gov-staging.web.app',
  'https://gov-staging.irgecosystem.com',
  'http://localhost:5173',
  'http://localhost:5000'
];

const corsHandler = cors({
  origin: (origin, cb) => {
    if (!origin) return cb(null, true);  // Server-to-server / curl
    if (ALLOWED_ORIGINS.includes(origin)) return cb(null, true);
    return cb(new Error(`Origin ${origin} not allowed`));
  },
  methods: ['GET'],
  credentials: false
});

const regional = functions.region('asia-south1');

// ── Naive in-memory per-IP rate limiter (resets on cold start) ─────────────
const _rlBuckets = new Map();
function rateLimited(ip, max = 30, windowMs = 60_000) {
  const now = Date.now();
  const bucket = _rlBuckets.get(ip) || [];
  const recent = bucket.filter(t => now - t < windowMs);
  recent.push(now);
  _rlBuckets.set(ip, recent);
  return recent.length > max;
}

// ═════════════════════════════════════════════════════════════════════════
// getMICSDigest — public aggregate for the Advisory Board MICS
// ═════════════════════════════════════════════════════════════════════════

exports.getMICSDigest = regional.https.onRequest((req, res) => {
  corsHandler(req, res, async () => {
    try {
      const ip = req.headers['x-forwarded-for'] || req.ip;
      if (rateLimited(ip)) return res.status(429).json({ error: 'rate_limited' });

      const { period } = req.query;
      if (!period) return res.status(400).json({ error: 'period_required' });

      // Read the pre-computed cached digest for this period (maintained by
      // the Django backend via firebase-admin, and/or refreshed hourly by
      // the refreshMICSDigest scheduled function below).
      const snap = await db.collection('mics_digest').doc(period).get();
      if (!snap.exists) {
        return res.status(404).json({ error: 'no_data_for_period', period });
      }

      const payload = snap.data();
      // Strip any fields prefixed with _ (internal)
      const clean = Object.fromEntries(Object.entries(payload).filter(([k]) => !k.startsWith('_')));

      return res.status(200).json(clean);
    } catch (e) {
      functions.logger.error('getMICSDigest failed:', e);
      return res.status(500).json({ error: 'internal_error' });
    }
  });
});

// ═════════════════════════════════════════════════════════════════════════
// getMICSDrill — public drill-down endpoint
// ═════════════════════════════════════════════════════════════════════════

exports.getMICSDrill = regional.https.onRequest((req, res) => {
  corsHandler(req, res, async () => {
    try {
      const ip = req.headers['x-forwarded-for'] || req.ip;
      if (rateLimited(ip)) return res.status(429).json({ error: 'rate_limited' });

      const { key } = req.query;
      if (!key) return res.status(400).json({ error: 'key_required' });

      const [, slice] = key.split('-');  // 'gdp-minting' -> 'minting'
      if (!slice) return res.status(400).json({ error: 'invalid_key' });

      const snap = await db.collection('mics_drill').doc(slice).get();
      if (!snap.exists) return res.status(404).json({ error: 'no_drill_data', slice });

      return res.status(200).json(snap.data());
    } catch (e) {
      functions.logger.error('getMICSDrill failed:', e);
      return res.status(500).json({ error: 'internal_error' });
    }
  });
});

// ═════════════════════════════════════════════════════════════════════════
// onUnitMint — maintain aggregate counters in mics_digest
// ═════════════════════════════════════════════════════════════════════════

exports.onUnitMint = regional.firestore
  .document('minting_records/{recordId}')
  .onCreate(async (snap) => {
    const data = snap.data();
    const grams = data.gramsPure || 0;

    // Update the MTD aggregate atomically
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
          pureGoldGrams: (kpis.pureGoldGrams || 0) + grams
        },
        _updatedAt: admin.firestore.FieldValue.serverTimestamp()
      }, { merge: true });
    });
  });

// ═════════════════════════════════════════════════════════════════════════
// onDisputeChange — maintain dispute rollups
// ═════════════════════════════════════════════════════════════════════════

exports.onDisputeChange = regional.firestore
  .document('disputes/{caseId}')
  .onWrite(async () => {
    // Recompute and write dispute rollup into mics_digest
    const openSnap = await db.collection('disputes').where('status', 'in', ['Filed', 'Under Review', 'Hearing']).get();
    const closedSnap = await db.collection('disputes').where('status', '==', 'Closed').get();

    await db.collection('mics_digest').doc('mtd').set({
      complaintsRollup: {
        open:   openSnap.size,
        closed: closedSnap.size
      },
      _updatedAt: admin.firestore.FieldValue.serverTimestamp()
    }, { merge: true });
  });

// ═════════════════════════════════════════════════════════════════════════
// refreshMICSDigest — hourly scheduled full recomputation
// ═════════════════════════════════════════════════════════════════════════

exports.refreshMICSDigest = regional.pubsub
  .schedule('every 60 minutes')
  .timeZone('Asia/Kolkata')
  .onRun(async () => {
    // Full recompute of the canonical aggregates. In production this would
    // read from the authoritative Django models (via the paa-bridge pattern)
    // and write the canonical snapshot. Currently emits a heartbeat so the
    // collection is always writeable.
    await db.collection('mics_digest').doc('mtd').set({
      _refreshedAt: admin.firestore.FieldValue.serverTimestamp(),
      _source:      'scheduled_refresh'
    }, { merge: true });
    return null;
  });
