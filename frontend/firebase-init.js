/**
 * irg_gdp — Firebase client init for the vanilla HTML frontends
 * (index.html, wallet.html, heir-guide.html).
 *
<<<<<<< HEAD
 * Project: irggdp
 */
import { initializeApp }    from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js';
import { getAuth }          from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js';
import { getFirestore }     from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore.js';
import { getStorage }       from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-storage.js';

const firebaseConfig = {
  apiKey:            'AIzaSyAloxpaDMVcOimJfrDqWiXrTvijdmJSk20',
  authDomain:        'irggdp.firebaseapp.com',
  projectId:         'irggdp',
  storageBucket:     'irggdp.firebasestorage.app',
  messagingSenderId: '128695548877',
  appId:             '1:128695548877:web:a1b599fe72aa0dbad66284',
  measurementId:     'G-370M4K1XEX',
=======
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
  apiKey:            window.__FIREBASE_API_KEY__             || '__FIREBASE_API_KEY__',
  authDomain:        window.__FIREBASE_AUTH_DOMAIN__         || 'irg-gdp-prod.firebaseapp.com',
  projectId:         window.__FIREBASE_PROJECT_ID__          || 'irg-gdp-prod',
  storageBucket:     window.__FIREBASE_STORAGE_BUCKET__      || 'irg-gdp-prod.appspot.com',
  messagingSenderId: window.__FIREBASE_MESSAGING_SENDER_ID__ || '',
  appId:             window.__FIREBASE_APP_ID__              || ''
>>>>>>> 6f5e39f (changhes05)
};

export const firebaseApp = initializeApp(firebaseConfig);
export const auth        = getAuth(firebaseApp);
export const db          = getFirestore(firebaseApp);
export const storage     = getStorage(firebaseApp);
