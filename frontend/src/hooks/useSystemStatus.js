import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api } from "../services/api";
import {
  isFirebaseConfigured,
  subscribeToFirestoreSystemStatus,
  syncSystemStatusToFirestore,
} from "../services/firebase";

export const DEFAULT_FEATURE_FLAGS = {
  posBilling: true,
  voiceAssistant: true,
  productManagement: true,
  inventoryAdjustments: true,
  reportsAnalytics: true,
};

const DEFAULT_STATUS = {
  maintenance: false,
  message: "Scheduled system maintenance is currently in progress.",
  estimatedTime: "15 minutes",
  updatedAt: null,
  blocking: false,
  features: { ...DEFAULT_FEATURE_FLAGS },
};

const SystemStatusContext = createContext(null);

function normalizeStatusPayload(raw, fallback = DEFAULT_STATUS) {
  if (!raw) return fallback;
  return {
    maintenance:
      typeof raw.maintenance === "boolean" ? raw.maintenance : fallback.maintenance,
    message:
      typeof raw.message === "string" && raw.message.trim()
        ? raw.message.trim()
        : fallback.message,
    estimatedTime:
      typeof raw.estimatedTime === "string" && raw.estimatedTime.trim()
        ? raw.estimatedTime.trim()
        : fallback.estimatedTime,
    updatedAt: raw.updatedAt || fallback.updatedAt,
    blocking: typeof raw.blocking === "boolean" ? raw.blocking : fallback.blocking,
    features: {
      ...DEFAULT_FEATURE_FLAGS,
      ...(fallback.features || {}),
      ...(raw.features || {}),
    },
  };
}

/**
 * Core real-time state manager combining:
 * 1. Firebase Firestore `system/status` via `onSnapshot()` for real-time updates without refresh.
 * 2. Authoritative FastAPI `/api/system/status` + SSE live stream so backend HTTP 503 protection
 *    and multi-tab live updates stay synchronized even if Firebase is offline or unconfigured.
 */
function useSystemStatusController() {
  const firebaseConfigured = isFirebaseConfigured();

  const [statusState, setStatusState] = useState(DEFAULT_STATUS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [firebaseConnected, setFirebaseConnected] = useState(false);
  const [firebaseError, setFirebaseError] = useState(null);
  const [adminPreviewBlocking, setAdminPreviewBlocking] = useState(false);

  const refreshSystemStatus = useCallback(async () => {
    try {
      const remote = await api.getSystemStatus();
      setStatusState((prev) => normalizeStatusPayload(remote, prev));
      setError(null);
    } catch (err) {
      setError(err?.message || "Unable to fetch backend system status.");
    } finally {
      setLoading(false);
    }
  }, []);

  // 1. Initial backend fetch + real-time SSE stream from FastAPI
  useEffect(() => {
    let active = true;
    refreshSystemStatus();

    const apiBase = import.meta.env.VITE_API_BASE_URL || "";
    let eventSource = null;
    let sseConnected = false;
    if (typeof window !== "undefined" && typeof window.EventSource !== "undefined") {
      try {
        eventSource = new window.EventSource(`${apiBase}/api/system/stream`);
        eventSource.onopen = () => {
          sseConnected = true;
        };
        eventSource.onmessage = (evt) => {
          if (!active || !evt.data) return;
          sseConnected = true;
          try {
            const parsed = JSON.parse(evt.data);
            setStatusState((prev) => normalizeStatusPayload(parsed, prev));
            setLoading(false);
          } catch {
            // Ignore malformed SSE frame
          }
        };
        eventSource.onerror = () => {
          sseConnected = false;
        };
      } catch {
        // Ignore SSE connection error; Firestore onSnapshot or fallback poll still works
      }
    }

    const handleStatusChanged = () => {
      if (active) refreshSystemStatus();
    };
    const handleVisibility = () => {
      if (active && document.visibilityState === "visible") {
        refreshSystemStatus();
      }
    };

    if (typeof window !== "undefined") {
      window.addEventListener("pos:system-status-changed", handleStatusChanged);
      document.addEventListener("visibilitychange", handleVisibility);
    }

    // Fallback poll only when SSE stream is disconnected and Firebase is unconfigured
    const pollTimer = setInterval(() => {
      if (active && !sseConnected && !firebaseConfigured) {
        refreshSystemStatus();
      }
    }, 5000);

    return () => {
      active = false;
      clearInterval(pollTimer);
      if (typeof window !== "undefined") {
        window.removeEventListener("pos:system-status-changed", handleStatusChanged);
        document.removeEventListener("visibilitychange", handleVisibility);
      }
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [firebaseConfigured, refreshSystemStatus]);

  // 2. Real-time Firebase Firestore `onSnapshot(doc(db, "system", "status"))` listener
  useEffect(() => {
    if (!firebaseConfigured) {
      setFirebaseConnected(false);
      return undefined;
    }

    let unsubscribe = () => {};
    try {
      unsubscribe = subscribeToFirestoreSystemStatus({
        onData: (firestoreDoc) => {
          setFirebaseConnected(true);
          setFirebaseError(null);
          setLoading(false);
          if (firestoreDoc) {
            setStatusState((prev) => normalizeStatusPayload(firestoreDoc, prev));
          }
        },
        onError: (fsErr) => {
          setFirebaseConnected(false);
          setFirebaseError(
            fsErr?.code === "permission-denied"
              ? "Firestore permission denied for system/status. Check firestore.rules."
              : "Firebase real-time connection interrupted; using backend status fallback."
          );
          setLoading(false);
        },
      });
    } catch {
      setFirebaseConnected(false);
      setFirebaseError("Could not initialize Firebase Firestore listener.");
      setLoading(false);
    }

    return () => {
      try {
        unsubscribe();
      } catch {
        // Ignore cleanup errors
      }
    };
  }, [firebaseConfigured]);

  // Automatically clear admin preview if maintenance is turned off
  useEffect(() => {
    if (!statusState.maintenance || !statusState.blocking) {
      setAdminPreviewBlocking(false);
    }
  }, [statusState.blocking, statusState.maintenance]);

  // 3. Administrator update action (updates FastAPI 503 guard + syncs Firestore `system/status`)
  const updateSystemStatus = useCallback(async (patch) => {
    const updatedBackend = await api.updateSystemStatus(patch);
    const normalized = normalizeStatusPayload(updatedBackend);
    setStatusState(normalized);

    let firestoreSyncWarning = null;
    if (isFirebaseConfigured()) {
      try {
        await syncSystemStatusToFirestore(normalized);
      } catch (fsWriteErr) {
        firestoreSyncWarning =
          fsWriteErr?.code === "permission-denied"
            ? "Backend 503 status updated. Firestore write requires an authenticated Firebase admin token."
            : "Backend status updated, but Firestore sync encountered a connection issue.";
      }
    }

    return { status: normalized, firestoreSyncWarning };
  }, []);

  return useMemo(
    () => ({
      maintenance: statusState.maintenance,
      message: statusState.message,
      estimatedTime: statusState.estimatedTime,
      updatedAt: statusState.updatedAt,
      blocking: statusState.blocking,
      features: statusState.features,
      loading,
      error,
      firebaseConfigured,
      firebaseConnected,
      firebaseError,
      adminPreviewBlocking,
      setAdminPreviewBlocking,
      refreshSystemStatus,
      updateSystemStatus,
    }),
    [
      adminPreviewBlocking,
      error,
      firebaseConfigured,
      firebaseConnected,
      firebaseError,
      loading,
      refreshSystemStatus,
      statusState,
      updateSystemStatus,
    ]
  );
}

export function SystemStatusProvider({ children }) {
  const value = useSystemStatusController();
  return React.createElement(SystemStatusContext.Provider, { value }, children);
}

/**
 * Reusable React hook `useSystemStatus` for reading real-time maintenance mode & feature flags.
 */
export function useSystemStatus() {
  const ctx = useContext(SystemStatusContext);
  if (ctx) {
    return ctx;
  }
  throw new Error("useSystemStatus must be used within a SystemStatusProvider");
}
