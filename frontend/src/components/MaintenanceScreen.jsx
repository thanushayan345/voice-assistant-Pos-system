import React from "react";
import { Clock, LogOut, Radio, ShieldCheck, Wrench } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useSystemStatus } from "../hooks/useSystemStatus";
import { formatDateTime } from "../utils/formatters";

export default function MaintenanceScreen() {
  const {
    message,
    estimatedTime,
    updatedAt,
    adminPreviewBlocking,
    setAdminPreviewBlocking,
    updateSystemStatus,
  } = useSystemStatus();
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const isAdmin =
    user?.role?.toLowerCase() === "owner" || user?.role?.toLowerCase() === "admin";

  const handleSwitchToAdminLogin = async () => {
    await logout();
    navigate("/login");
  };

  const handleDisableNow = async () => {
    try {
      await updateSystemStatus({ maintenance: false });
      setAdminPreviewBlocking(false);
    } catch {
      setAdminPreviewBlocking(false);
      navigate("/admin");
    }
  };

  return (
    <div className="min-h-screen w-full bg-slate-950 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-3xl p-8 sm:p-10 shadow-2xl text-center space-y-6">
        <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 flex items-center justify-center mx-auto">
          <Wrench className="w-8 h-8" />
        </div>

        <div className="space-y-2">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 text-xs font-bold">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
            Scheduled System Maintenance
          </span>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight pt-1">
            We&rsquo;ll Be Right Back
          </h1>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-md mx-auto">
            {message || "Scheduled system maintenance is currently in progress."}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left bg-slate-950/70 border border-slate-800 rounded-2xl p-4">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-indigo-400 shrink-0" />
            <div>
              <span className="text-[11px] uppercase tracking-wider text-slate-400 block font-semibold">
                Estimated Duration
              </span>
              <strong className="text-sm text-white">
                {estimatedTime || "Shortly"}
              </strong>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <span className="text-[11px] uppercase tracking-wider text-slate-400 block font-semibold">
                Auto-Recovery
              </span>
              <strong className="text-xs text-emerald-300">
                Real-Time Active (No Refresh Needed)
              </strong>
            </div>
          </div>
        </div>

        {updatedAt && (
          <p className="text-xs text-slate-500">
            Last status update: {formatDateTime(updatedAt)}
          </p>
        )}

        {/* Administrator Preview / Login Controls */}
        <div className="pt-4 border-t border-slate-800 flex flex-wrap items-center justify-center gap-3">
          {isAdmin && adminPreviewBlocking ? (
            <>
              <button
                type="button"
                onClick={() => setAdminPreviewBlocking(false)}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition"
              >
                Exit Admin Preview
              </button>
              <button
                type="button"
                onClick={handleDisableNow}
                className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition"
              >
                Disable Maintenance Now
              </button>
            </>
          ) : isAuthenticated ? (
            <button
              type="button"
              onClick={handleSwitchToAdminLogin}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition"
            >
              <LogOut className="w-4 h-4" />
              Sign In as Administrator
            </button>
          ) : (
            <button
              type="button"
              onClick={() => navigate("/login")}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition"
            >
              Administrator Sign In
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
