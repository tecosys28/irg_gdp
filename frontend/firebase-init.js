/**
 * irg_gdp — Firebase client init for the vanilla HTML frontends
 * (index.html, wallet.html, heir-guide.html).
 *
 * Uses the CDN modular SDK so no bundler is needed. Configuration values
 * are injected at build time by replacing the __PLACEHOLDER__ strings —
 * see scripts/inject-firebase-config.sh in the deploy pipeline.
 *
 * Project: irg-gdp-project (sovereign; do not share with sibling projects)
 */
import { initializeApp }    from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js';
import { getAuth }          from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js';
import { getFirestore }     from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore.js';
import { getStorage }       from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-storage.js';

const firebaseConfig = {
  apiKey:            window.__FIREBASE_API_KEY__             || 'REPLACE_WITH_API_KEY',
  authDomain:        window.__FIREBASE_AUTH_DOMAIN__         || 'irg-gdp-project.firebaseapp.com',
  projectId:         window.__FIREBASE_PROJECT_ID__          || 'irg-gdp-project',
  storageBucket:     window.__FIREBASE_STORAGE_BUCKET__      || 'irg-gdp-project.firebasestorage.app',
  messagingSenderId: window.__FIREBASE_MESSAGING_SENDER_ID__ || 'REPLACE_WITH_SENDER_ID',
  appId:             window.__FIREBASE_APP_ID__              || 'REPLACE_WITH_APP_ID',
};

export const firebaseApp = initializeApp(firebaseConfig);
export const auth        = getAuth(firebaseApp);
export const db          = getFirestore(firebaseApp);
export const storage     = getStorage(firebaseApp);
