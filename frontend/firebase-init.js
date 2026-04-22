/**
 * irg_gdp — Firebase client init for the vanilla HTML frontends
 * (index.html, wallet.html, heir-guide.html).
 *
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
};

export const firebaseApp = initializeApp(firebaseConfig);
export const auth        = getAuth(firebaseApp);
export const db          = getFirestore(firebaseApp);
export const storage     = getStorage(firebaseApp);

// API calls go through Firebase Hosting rewrite rules → Cloud Function proxy → EC2.
// Using a relative path means this works on every environment (irggdp.com,
// irggdp.web.app, localhost:5000) without any per-environment config.
export const API_BASE = '';
