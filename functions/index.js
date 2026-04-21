/**
 * irg_gdp Cloud Functions (firebase-functions v5 / Node 22)
 *
 * Exports:
 *   • apiProxy          — Proxies /api/** and /admin/** to EC2 Django backend
 *   • getMICSDigest     — PUBLIC HTTPS endpoint returning aggregate metrics
 *   • getMICSDrill      — PUBLIC HTTPS endpoint for drill-down details
 *   • onUnitMint        — Firestore trigger maintaining aggregate counters
 *   • onDisputeChange   — Firestore trigger updating dispute rollups
 *   • refreshMICSDigest — Hourly scheduled recompute
 *   • licenceStatus     — Callable: licence health check
 *
 * IPR Owner: Mr. Rohit Tidke · © 2026 Intech Research Group
 */

const { onRequest, onCall } = require('firebase-functions/v2/https');
const { onDocumentCreated, onDocumentWritten } = require('firebase-functions/v2/firestore');
const { onSchedule } = require('firebase-functions/v2/scheduler');
const { setGlobalOptions } = require('firebase-functions/v2');
const admin = require('firebase-admin');
const cors  = require('cors');
const http  = require('http');

const { currentLicenceInfo } = require('./licence-guard');

setGlobalOptions({ region: 'asia-south1' });

admin.initializeApp();
const db = admin.firestore();

// ─────────────────────────────────────────────────────────────────────────────
// Django backend proxy
// Forwards /api/** and /admin/** to the configured backend host.
// Set DJANGO_BACKEND_HOST in Firebase Functions config or .env.local:
//   firebase functions:config:set backend.host="your-domain.com"
// or export DJANGO_BACKEND_HOST=your-domain.com before deploying.
// ─────────────────────────────────────────────────────────────────────────────
const EC2_HOST = process.env.DJANGO_BACKEND_HOST || '43.205.237.197';
const EC2_PORT = parseInt(process.env.DJANGO_BACKEND_PORT || '80', 10);

exports.apiProxy = onRequest({ invoker: 'public' }, async (req, res) => {
  res.set('Access-Control-Allow-Origin', req.headers.origin || '*');
  res.set('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
  res.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.set('Access-Control-Allow-Credentials', 'true');

  if (req.method === 'OPTIONS') {
    return res.status(204).send('');
  }

  // Verify Firebase ID token here (Cloud Functions has implicit admin credentials).
  // Inject trusted headers so EC2 Django backend never needs its own Firebase creds.
  const authHeader = req.headers['authorization'] || '';
  const trustedHeaders = {};
  if (authHeader.startsWith('Bearer ')) {
    const token = authHeader.slice(7);
    try {
      const decoded = await admin.auth().verifyIdToken(token);
      trustedHeaders['x-verified-firebase-uid']   = decoded.uid;
      trustedHeaders['x-verified-firebase-email'] = decoded.email || '';
    } catch (err) {
      return res.status(401).json({ error: 'invalid_token', detail: err.message });
    }
  }

  const forwardHeaders = { ...req.headers, ...trustedHeaders };
  delete forwardHeaders['host'];

  const options = {
    hostname: EC2_HOST,
    port: EC2_PORT,
    path: req.url,
    method: req.method,
    headers: {
      ...forwardHeaders,
      host: EC2_HOST,
      'x-forwarded-for': req.ip,
      'x-forwarded-proto': 'https',
    },
  };

  const proxy = http.request(options, (backendRes) => {
    res.status(backendRes.statusCode);
    Object.entries(backendRes.headers).forEach(([k, v]) => {
      if (k.toLowerCase() !== 'transfer-encoding') res.set(k, v);
    });
    backendRes.pipe(res, { end: true });
  });

  proxy.on('error', (err) => {
    console.error('Proxy error:', err);
    res.status(502).json({ error: 'backend_unavailable', detail: err.message });
  });

  if (req.body && req.method !== 'GET' && req.method !== 'HEAD') {
    const body = typeof req.body === 'object'
      ? JSON.stringify(req.body)
      : req.body;
    proxy.write(body);
  }
  proxy.end();
});

// ─────────────────────────────────────────────────────────────────────────────
// Licence status callable
// ─────────────────────────────────────────────────────────────────────────────
exports.licenceStatus = onCall(async () => currentLicenceInfo());

// ─────────────────────────────────────────────────────────────────────────────
// CORS helper for public MICS endpoints
// ─────────────────────────────────────────────────────────────────────────────
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
