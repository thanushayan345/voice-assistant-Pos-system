import React from "react";
import { AlertTriangle, Clock, Eye, ShieldAlert, Wrench } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useSystemStatus } from "../hooks/useSystemStatus";
import { formatDateTime } from "../utils/formatters";

export default function MaintenanceBanner() {
  const {
    maintenance,
    blocking,
    message,
    estimatedTime,
    updatedAt,
    setAdminPreviewBlocking,
    updateSystemStatus,
  } = useSystemStatus();
  const { user } = useAuth();
  const navigate = useNavigate();

  if (!maintenance) {
    return null;
  }

  const isAdmin =
    user?.role?.toLowerCase() === "owner" || user?.role?.toLowerCase() === "admin";

  const handleQuickDisable = async () => {
    try {
      await updateSystemStatus({ maintenance: false });
    } catch {
      navigate("/admin");
    }
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className={`w-full px-4 sm:px-6 py-3 border-b flex flex-col md:flex-row md:items-center md:justify-between gap-2.5 shrink-0 z-30 ${
        blocking
          ? "bg-rose-600 text-white border-rose-700"
          : "bg-amber-500 text-slate-950 border-amber-600"
      }`}
    >
      <div className="flex items-start sm:items-center gap-3 min-w-0">
        {blocking ? (
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5 sm:mt-0" />
        ) : (
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 sm:mt-0" />
        )}
        <div className="text-xs sm:text-sm min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-extrabold uppercase tracking-wider text-[11px] px-2 py-0.5 rounded-md bg-black/15">
              {blocking ? "Blocking Maintenance (Admin Bypass)" : "Maintenance Notice"}
            </span>
            <span className="font-bold">{message}</span>
          </div>
          <div
            className={`flex flex-wrap items-center gap-3 text-[11px] mt-0.5 ${
              blocking ? "text-rose-100" : "text-slate-900/80"
            }`}
          >
            {estimatedTime && (
              <span className="inline-flex items-center gap-1 font-semibold">
                <Clock className="w-3.5 h-3.5" />
                Est. Duration: {estimatedTime}
              </span>
            )}
            {updatedAt && <span>Updated: {formatDateTime(updatedAt)}</span>}
          </div>
        </div>
      </div>

      {isAdmin && (
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {blocking && (
            <button
              type="button"
              onClick={() => setAdminPreviewBlocking(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/15 hover:bg-white/25 text-white text-xs font-bold transition"
            >
              <Eye className="w-3.5 h-3.5" />
              Preview Full Screen
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate("/admin")}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
              blocking
                ? "bg-white text-rose-700 hover:bg-rose-50"
                : "bg-slate-900 text-white hover:bg-slate-800"
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            Admin Controls
          </button>
          <button
            type="button"
            onClick={handleQuickDisable}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition ${
              blocking
                ? "border-white/40 text-white hover:bg-white/15"
                : "border-slate-900/30 text-slate-950 hover:bg-black/10"
            }`}
          >
            End Maintenance
          </button>
        </div>
      )}
    </div>
  );
}
