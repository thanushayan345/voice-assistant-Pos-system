/**
 * Firebase Web SDK Client Configuration & Firestore `system/status` Real-Time Helper.
 *
 * SECURITY:
 * - Reads ONLY public VITE_FIREBASE_* client environment variables.
 * - NEVER stores or accepts Firebase Admin SDK / service-account private keys.
 */

import { getApps, initializeApp } from "firebase/app";
import {
  doc,
  getFirestore,
  onSnapshot,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";

const firebaseConfig = {
  apiKey: (import.meta.env.VITE_FIREBASE_API_KEY || "").trim(),
  authDomain: (import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "").trim(),
  projectId: (import.meta.env.VITE_FIREBASE_PROJECT_ID || "").trim(),
  storageBucket: (import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "").trim(),
  messagingSenderId: (import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "").trim(),
  appId: (import.meta.env.VITE_FIREBASE_APP_ID || "").trim(),
};

const PLACEHOLDER_VALUES = new Set([
  "",
  "your_firebase_web_api_key",
  "your-project-id",
  "replace_me",
]);

export function isFirebaseConfigured() {
  return (
    !PLACEHOLDER_VALUES.has(firebaseConfig.apiKey) &&
    !PLACEHOLDER_VALUES.has(firebaseConfig.projectId) &&
    firebaseConfig.apiKey.length >= 10 &&
    firebaseConfig.projectId.length >= 3
  );
}

let cachedDb = null;

export function getFirestoreClient() {
  if (!isFirebaseConfigured()) {
    return null;
  }
  if (cachedDb) {
    return cachedDb;
  }
  const existingApps = getApps();
  const app =
    existingApps.length > 0 ? existingApps[0] : initializeApp(firebaseConfig);
  cachedDb = getFirestore(app);
  return cachedDb;
}

function normalizeTimestamp(rawVal) {
  if (!rawVal) return null;
  if (typeof rawVal?.toDate === "function") {
    return rawVal.toDate().toISOString();
  }
  if (typeof rawVal?.seconds === "number") {
    return new Date(rawVal.seconds * 1000).toISOString();
  }
  if (rawVal instanceof Date) {
    return rawVal.toISOString();
  }
  if (typeof rawVal === "string") {
    return rawVal;
  }
  return null;
}

/**
 * Subscribe to Firestore document `system/status` in real time using `onSnapshot()`.
 * Returns an unsubscribe function.
 */
export function subscribeToFirestoreSystemStatus({ onData, onError }) {
  const db = getFirestoreClient();
  if (!db) {
    return () => {};
  }

  const statusRef = doc(db, "system", "status");
  return onSnapshot(
    statusRef,
    (snapshot) => {
      if (!snapshot.exists()) {
        onData(null);
        return;
      }
      const raw = snapshot.data() || {};
      onData({
        maintenance: Boolean(raw.maintenance),
        message:
          typeof raw.message === "string" && raw.message.trim()
            ? raw.message.trim()
            : "Scheduled system maintenance is currently in progress.",
        estimatedTime:
          typeof raw.estimatedTime === "string" && raw.estimatedTime.trim()
            ? raw.estimatedTime.trim()
            : "Shortly",
        updatedAt: normalizeTimestamp(raw.updatedAt),
        blocking: Boolean(raw.blocking),
        features: raw.features && typeof raw.features === "object" ? raw.features : null,
      });
    },
    (err) => {
      if (onError) {
        onError(err);
      }
    }
  );
}

/**
 * Write updated system status fields to Firestore `system/status` with `serverTimestamp()`.
 * Subject to `firestore.rules` (only authorized Firebase admins can write).
 */
export async function syncSystemStatusToFirestore(statusPayload) {
  const db = getFirestoreClient();
  if (!db) {
    return { synced: false, reason: "FIREBASE_NOT_CONFIGURED" };
  }

  const statusRef = doc(db, "system", "status");
  await setDoc(
    statusRef,
    {
      maintenance: Boolean(statusPayload.maintenance),
      message: String(statusPayload.message || ""),
      estimatedTime: String(statusPayload.estimatedTime || ""),
      blocking: Boolean(statusPayload.blocking),
      features: statusPayload.features || {},
      updatedAt: serverTimestamp(),
    },
    { merge: true }
  );
  return { synced: true };
}
