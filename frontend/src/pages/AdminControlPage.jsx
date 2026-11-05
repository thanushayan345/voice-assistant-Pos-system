import React, { useEffect, useState } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Eye,
  Save,
  Sliders,
  Flame,
  Server,
  Clock,
  RefreshCw,
} from "lucide-react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { DEFAULT_FEATURE_FLAGS, useSystemStatus } from "../hooks/useSystemStatus";
import { formatDateTime } from "../utils/formatters";

const DURATION_PRESETS = ["15 minutes", "30 minutes", "1 hour", "2 hours", "Tonight 11:00 PM"];

const FEATURE_FLAG_DEFINITIONS = [
  {
    key: "posBilling",
    label: "POS & Billing Checkout",
    description: "Controls sales billing cart and checkout endpoints (/api/sales).",
  },
  {
    key: "voiceAssistant",
    label: "Local AI Voice Assistant",
    description: "Controls local Ollama (qwen2.5:3b) voice processing (/api/voice).",
  },
  {
    key: "productManagement",
    label: "Product Catalog Mutations",
    description: "Controls adding, editing, and deleting shop products (/api/products).",
  },
  {
    key: "inventoryAdjustments",
    label: "Inventory Stock Adjustments",
    description: "Controls manual stock additions and reductions (/api/inventory/adjust).",
  },
  {
    key: "reportsAnalytics",
    label: "Sales & Inventory Reports",
    description: "Controls analytics and valuation reporting (/api/reports).",
  },
];

export default function AdminControlPage() {
  const { user } = useAuth();
  const {
    maintenance,
    blocking,
    message,
    estimatedTime,
    updatedAt,
    features,
    firebaseConfigured,
    firebaseConnected,
    firebaseError,
    setAdminPreviewBlocking,
    refreshSystemStatus,
    updateSystemStatus,
  } = useSystemStatus();

  const isAdmin =
    user?.role?.toLowerCase() === "owner" || user?.role?.toLowerCase() === "admin";

  const [draftMessage, setDraftMessage] = useState(message);
  const [draftDuration, setDraftDuration] = useState(estimatedTime);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  useEffect(() => {
    setDraftMessage(message);
  }, [message]);

  useEffect(() => {
    setDraftDuration(estimatedTime);
  }, [estimatedTime]);

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  const applyUpdate = async (patch, successText) => {
    setSaving(true);
    setFeedback(null);
    try {
      const { firestoreSyncWarning } = await updateSystemStatus(patch);
      setFeedback({
        type: firestoreSyncWarning ? "warning" : "success",
        text: firestoreSyncWarning ? `${successText} (${firestoreSyncWarning})` : successText,
      });
    } catch (err) {
      setFeedback({
        type: "error",
        text: err?.message || "Failed to update system maintenance status.",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveDetails = (e) => {
    e.preventDefault();
    applyUpdate(
      {
        message: draftMessage,
        estimatedTime: draftDuration,
      },
      "Maintenance message and estimated duration saved."
    );
  };

  const handleToggleFeature = (flagKey) => {
    const currentFlags = { ...DEFAULT_FEATURE_FLAGS, ...(features || {}) };
    const nextValue = !currentFlags[flagKey];
    applyUpdate(
      {
        features: {
          ...currentFlags,
          [flagKey]: nextValue,
        },
      },
      `Feature '${flagKey}' ${nextValue ? "enabled" : "disabled"} in real time.`
    );
  };

  return (
    <div className="space-y-6 w-full">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p className="text-sm text-slate-600">
            Real-time Maintenance Mode (Firestore <code className="font-mono text-xs bg-slate-200 px-1.5 py-0.5 rounded">system/status</code> + FastAPI HTTP 503 Guard) and Feature Flags.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {maintenance && blocking && (
            <button
              type="button"
              onClick={() => setAdminPreviewBlocking(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition"
            >
              <Eye className="w-4 h-4" />
              Preview Blocking Screen
            </button>
          )}
          <button
            type="button"
            onClick={refreshSystemStatus}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-100 text-xs font-bold text-slate-700"
          >
            <RefreshCw className="w-4 h-4" />
            Sync Status
          </button>
        </div>
      </div>

      {feedback && (
        <div
          className={`p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2.5 ${
            feedback.type === "error"
              ? "bg-rose-50 border-rose-200 text-rose-800"
              : feedback.type === "warning"
              ? "bg-amber-50 border-amber-200 text-amber-900"
              : "bg-emerald-50 border-emerald-200 text-emerald-800"
          }`}
        >
          {feedback.type === "success" ? (
            <CheckCircle2 className="w-5 h-5 shrink-0" />
          ) : (
            <AlertTriangle className="w-5 h-5 shrink-0" />
          )}
          <span>{feedback.text}</span>
        </div>
      )}

      {/* Real-time Sync Infrastructure Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-4 flex items-center gap-3.5 shadow-xs">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              maintenance
                ? blocking
                  ? "bg-rose-100 text-rose-700"
                  : "bg-amber-100 text-amber-700"
                : "bg-emerald-100 text-emerald-700"
            }`}
          >
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs text-slate-500 block">Current System State</span>
            <strong className="text-sm text-slate-900">
              {!maintenance
                ? "Normal Operation"
                : blocking
                ? "Maintenance ON (Blocking 503)"
                : "Maintenance ON (Banner Mode)"}
            </strong>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-4 flex items-center gap-3.5 shadow-xs">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              firebaseConnected
                ? "bg-emerald-100 text-emerald-700"
                : "bg-slate-100 text-slate-600"
            }`}
          >
            <Flame className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-xs text-slate-500 block">
              Firebase Firestore (onSnapshot)
            </span>
            <strong className="text-xs text-slate-900 block truncate">
              {firebaseConnected
                ? "Connected (system/status live)"
                : firebaseConfigured
                ? firebaseError || "Connecting..."
                : "Optional (Set VITE_FIREBASE_* in frontend/.env)"}
            </strong>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-4 flex items-center gap-3.5 shadow-xs">
          <div className="w-10 h-10 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs text-slate-500 block">FastAPI HTTP 503 Protection</span>
            <strong className="text-xs text-slate-900 block">
              Active • Updated {updatedAt ? formatDateTime(updatedAt) : "Just now"}
            </strong>
          </div>
        </div>
      </div>

      {/* Main 2-Column Admin Controls */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Left 7 Cols: Maintenance Switch, Display Mode, Message & Duration */}
        <div className="xl:col-span-7 bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-100">
            <div>
              <h3 className="text-base font-extrabold text-slate-900">
                Maintenance Mode Master Switch
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Instantly broadcast maintenance status to all active browser sessions without page refresh.
              </p>
            </div>
            <button
              type="button"
              disabled={saving}
              onClick={() =>
                applyUpdate(
                  { maintenance: !maintenance },
                  !maintenance
                    ? "Maintenance mode ENABLED across all sessions."
                    : "Maintenance mode DISABLED — normal operation restored."
                )
              }
              className={`px-5 py-3 rounded-xl text-xs font-extrabold uppercase tracking-wider transition shrink-0 disabled:opacity-50 ${
                maintenance
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                  : "bg-rose-600 hover:bg-rose-700 text-white"
              }`}
            >
              {maintenance ? "Disable Maintenance" : "Enable Maintenance"}
            </button>
          </div>

          {/* Display Mode Selector: Banner-Only vs Full-Screen Blocking */}
          <div className="space-y-2.5">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
              Maintenance Enforcement Mode
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                disabled={saving}
                onClick={() =>
                  applyUpdate(
                    { blocking: false },
                    "Switched to Banner-Only maintenance mode."
                  )
                }
                className={`p-4 rounded-2xl border-2 text-left transition ${
                  !blocking
                    ? "border-indigo-600 bg-indigo-50/60"
                    : "border-slate-200 hover:border-slate-300 bg-white"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-extrabold text-slate-900">
                    Banner-Only Mode
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                    Non-Blocking
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Displays a prominent top alert banner while keeping POS billing and inventory operations open.
                </p>
              </button>

              <button
                type="button"
                disabled={saving}
                onClick={() =>
                  applyUpdate(
                    { blocking: true },
                    "Switched to Full-Screen Blocking mode (FastAPI HTTP 503 active)."
                  )
                }
                className={`p-4 rounded-2xl border-2 text-left transition ${
                  blocking
                    ? "border-rose-600 bg-rose-50/60"
                    : "border-slate-200 hover:border-slate-300 bg-white"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-extrabold text-slate-900">
                    Full-Screen Blocking
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800">
                    HTTP 503 Enforced
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Shows a full-screen maintenance page to staff and blocks protected API mutations with HTTP 503.
                </p>
              </button>
            </div>
          </div>

          {/* Message & Estimated Duration Editor */}
          <form onSubmit={handleSaveDetails} className="space-y-4 pt-2">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  Public Maintenance Message
                </label>
                <span className="text-[11px] text-slate-400">
                  {(draftMessage || "").length}/500
                </span>
              </div>
              <textarea
                rows={3}
                maxLength={500}
                value={draftMessage}
                onChange={(e) => setDraftMessage(e.target.value)}
                placeholder="Scheduled system maintenance is currently in progress..."
                className="w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Messages are automatically sanitized so internal paths, SQL, or backend secrets are never exposed.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
                Estimated Maintenance Duration
              </label>
              <div className="relative">
                <Clock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  maxLength={120}
                  value={draftDuration}
                  onChange={(e) => setDraftDuration(e.target.value)}
                  placeholder="e.g., 30 minutes"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {DURATION_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setDraftDuration(preset)}
                    className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-xs font-semibold text-slate-700 transition"
                  >
                    {preset}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              Save Message & Duration
            </button>
          </form>
        </div>

        {/* Right 5 Cols: Real-Time Feature Flags */}
        <div className="xl:col-span-5 bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
            <Sliders className="w-5 h-5 text-indigo-600" />
            <div>
              <h3 className="text-base font-extrabold text-slate-900">
                Real-Time Feature Flags
              </h3>
              <p className="text-xs text-slate-500">
                Enable or disable individual modules across UI and FastAPI endpoints.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {FEATURE_FLAG_DEFINITIONS.map((item) => {
              const enabled = features ? features[item.key] !== false : true;
              return (
                <div
                  key={item.key}
                  className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-900">
                        {item.label}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          enabled
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-rose-100 text-rose-800"
                        }`}
                      >
                        {enabled ? "ENABLED" : "DISABLED"}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{item.description}</p>
                  </div>

                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => handleToggleFeature(item.key)}
                    aria-pressed={enabled}
                    className={`relative w-12 h-7 rounded-full transition-colors shrink-0 disabled:opacity-50 ${
                      enabled ? "bg-emerald-600" : "bg-slate-300"
                    }`}
                  >
                    <span
                      className={`absolute top-1 left-1 w-5 h-5 rounded-full bg-white shadow-xs transition-transform ${
                        enabled ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
