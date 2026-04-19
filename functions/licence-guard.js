/**
 * IRG Licence Guard — plain Node.js for Firebase Cloud Functions.
 *
 * Perpetual licence, Ed25519-signed.
 *
 * Usage in functions/index.js:
 *   const { verifyLicenceOrDie, currentLicenceInfo } = require('./licence-guard');
 *   if (process.env.FUNCTIONS_EMULATOR !== 'true') {
 *     verifyLicenceOrDie('DAC');  // or 'GOV'
 *   }
 *   exports.licenceStatus = functions.https.onCall(async () => currentLicenceInfo());
 *
 * IPR Owner: Rohit Tidke | (c) 2026 Intech Research Group
 */

'use strict';

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');

const LICENCE_PUBLIC_KEY_HEX =
  process.env.IRG_LICENCE_PUBLIC_KEY_HEX ||
  '0000000000000000000000000000000000000000000000000000000000000000';

const LICENCE_TOKEN_PATH =
  process.env.IRG_LICENCE_TOKEN_PATH || '/etc/irg/licence.token';
const FINGERPRINT_SALT = Buffer.from('irg-fingerprint-v1');
const RECHECK_INTERVAL_MS = 60 * 60 * 1000;

const STATE = {
  valid: false, reason: 'not_checked', payload: null,
  lastCheckAt: 0, lastGoodAt: 0,
};

function primaryMac() {
  const ifaces = os.networkInterfaces();
  for (const list of Object.values(ifaces)) {
    if (!list) continue;
    for (const addr of list) {
      if (!addr.internal && addr.mac && addr.mac !== '00:00:00:00:00:00') {
        return addr.mac.replace(/:/g, '').toLowerCase();
      }
    }
  }
  return 'unknown';
}

function chainId() { return process.env.IRG_CHAIN_ID || '888101'; }
function buildVersion() { return process.env.IRG_BUILD_VERSION || 'v1.0'; }

function computeDeploymentFingerprint() {
  const h = crypto.createHash('sha256');
  h.update(FINGERPRINT_SALT);
  h.update(primaryMac());
  h.update('|');
  h.update(os.hostname());
  h.update('|');
  h.update(chainId());
  h.update('|');
  h.update(buildVersion());
  return h.digest('hex');
}

function b64urlDecode(s) {
  const pad = s.length % 4 === 0 ? '' : '='.repeat(4 - (s.length % 4));
  return Buffer.from(s + pad, 'base64url');
}

function ed25519PubKeyFromHex(hex) {
  const raw = Buffer.from(hex, 'hex');
  if (raw.length !== 32) throw new Error('bad_public_key_length');
  const der = Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), raw]);
  return crypto.createPublicKey({ key: der, format: 'der', type: 'spki' });
}

function verifySignature(message, signature) {
  try {
    return crypto.verify(null, message, ed25519PubKeyFromHex(LICENCE_PUBLIC_KEY_HEX), signature);
  } catch {
    return false;
  }
}

function parseToken(token) {
  const parts = token.trim().split('.');
  if (parts.length !== 2) throw new Error('malformed_token');
  const payload = b64urlDecode(parts[0]);
  const sig = b64urlDecode(parts[1]);
  if (!verifySignature(payload, sig)) throw new Error('bad_signature');
  return JSON.parse(payload.toString('utf8'));
}

function verifyOnce(productCode) {
  let raw;
  try {
    raw = fs.readFileSync(LICENCE_TOKEN_PATH, 'utf8').trim();
  } catch {
    return { valid: false, reason: `token_not_found:${LICENCE_TOKEN_PATH}`, payload: null };
  }
  let payload;
  try {
    payload = parseToken(raw);
  } catch (e) {
    return { valid: false, reason: e.message || 'parse_error', payload: null };
  }
  if (payload.v !== 2) return { valid: false, reason: 'unsupported_version', payload };

  const now = Math.floor(Date.now() / 1000);
  if (payload.iat > now + 300) return { valid: false, reason: 'issued_in_future', payload };

  if ((payload.fp || '').toLowerCase() !== computeDeploymentFingerprint()) {
    return { valid: false, reason: 'fingerprint_mismatch', payload };
  }

  const products = (payload.products || []).map((p) => String(p).toUpperCase());
  if (!products.includes(String(productCode).toUpperCase())) {
    return { valid: false, reason: 'product_not_licensed', payload };
  }

  return { valid: true, reason: 'ok', payload };
}

let recheckStarted = false;

function verifyLicenceOrDie(productCode) {
  const r = verifyOnce(productCode || 'DAC');
  STATE.valid = r.valid;
  STATE.reason = r.reason;
  STATE.payload = r.payload;
  STATE.lastCheckAt = Date.now();
  if (r.valid) STATE.lastGoodAt = Date.now();

  if (!r.valid) {
    console.error(
      `[irg.licence] LICENCE INVALID (${r.reason}) — refusing to start. ` +
      `Contact the licensor.`,
    );
    if (process.env.IRG_LICENCE_TEST_MODE === '1') {
      throw new Error(r.reason);
    }
    process.exit(2);
  }

  console.info(
    `[irg.licence] OK — ${productCode} licensed to ${r.payload.name} ` +
    `(${r.payload.sub}), serial ${r.payload.serial}`,
  );

  if (!recheckStarted) {
    recheckStarted = true;
    const t = setInterval(() => {
      const rr = verifyOnce(productCode || 'DAC');
      STATE.valid = rr.valid;
      STATE.reason = rr.reason;
      STATE.payload = rr.payload;
      STATE.lastCheckAt = Date.now();
      if (rr.valid) STATE.lastGoodAt = Date.now();
      if (!rr.valid) console.error(`[irg.licence] recheck failed: ${rr.reason}`);
    }, RECHECK_INTERVAL_MS);
    if (typeof t.unref === 'function') t.unref();
  }
}

function currentLicenceInfo() {
  return {
    valid: STATE.valid,
    reason: STATE.reason,
    lastCheckAt: STATE.lastCheckAt,
    lastGoodAt: STATE.lastGoodAt,
    licensee: STATE.payload ? STATE.payload.name : null,
    licenseeUid: STATE.payload ? STATE.payload.sub : null,
    serial: STATE.payload ? STATE.payload.serial : null,
    products: STATE.payload ? STATE.payload.products : [],
    territory: STATE.payload ? STATE.payload.territory : [],
  };
}

module.exports = {
  verifyLicenceOrDie, currentLicenceInfo, computeDeploymentFingerprint,
};
