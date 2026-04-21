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

// Firebase Hosting rewrites to 2nd-gen Cloud Functions require a gcloud IAM
// grant that isn't set up yet. Call the Firebase Functions URL directly — CORS
// is configured in apiProxy to allow all Firebase Hosting origins.
export const API_BASE = 'https://asia-south1-irggdp.cloudfunctions.net/apiProxy';
