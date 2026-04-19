/**
 * irg_gdp — Firebase client init for the vanilla HTML frontends
 * (index.html, wallet.html, heir-guide.html).
 *
 * Uses the CDN modular SDK so no bundler is needed. Configuration values
 * are injected at build time by replacing the __PLACEHOLDER__ strings —
 * see scripts/inject-firebase-config.sh in the deploy pipeline.
 *
 * Project: irg-gdp-prod (sovereign; do not share with sibling projects)
 */
import { initializeApp }    from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js';
import { getAuth }          from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js';
import { getFirestore }     from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js';
import { getStorage }       from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-storage.js';

const firebaseConfig = {
  apiKey:            window.__FIREBASE_API_KEY__             || 'AIzaSyAloxpaDMVcOimJfrDqWiXrTvijdmJSk20',
  authDomain:        window.__FIREBASE_AUTH_DOMAIN__         || 'irggdp.firebaseapp.com',
  projectId:         window.__FIREBASE_PROJECT_ID__          || 'irggdp',
  storageBucket:     window.__FIREBASE_STORAGE_BUCKET__      || 'irggdp.firebasestorage.app',
  messagingSenderId: window.__FIREBASE_MESSAGING_SENDER_ID__ || '128695548877',
  appId:             window.__FIREBASE_APP_ID__              || '1:128695548877:web:a1b599fe72aa0dbad66284',
  measurementId:     window.__FIREBASE_MEASUREMENT_ID__      || 'G-370M4K1XEX'
};

export const firebaseApp = initializeApp(firebaseConfig);
export const auth        = getAuth(firebaseApp);
export const db          = getFirestore(firebaseApp);
export const storage     = getStorage(firebaseApp);
