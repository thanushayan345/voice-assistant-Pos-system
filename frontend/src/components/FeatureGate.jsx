import React from "react";
import { Lock, Wrench } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useSystemStatus } from "../hooks/useSystemStatus";

export default function FeatureGate({ featureKey, featureLabel, children }) {
  const { features, updateSystemStatus } = useSystemStatus();
  const { user } = useAuth();
  const navigate = useNavigate();

  const isEnabled = features ? features[featureKey] !== false : true;
  if (isEnabled) {
    return children;
  }

  const isAdmin =
    user?.role?.toLowerCase() === "owner" || user?.role?.toLowerCase() === "admin";

  const handleEnableFeature = async () => {
    try {
      await updateSystemStatus({
        features: {
          ...features,
          [featureKey]: true,
        },
      });
    } catch {
      navigate("/admin");
    }
  };

  return (
    <div className="w-full py-16 flex items-center justify-center">
      <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 p-8 text-center shadow-xs space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto">
          <Lock className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-lg font-extrabold text-slate-900">
            {featureLabel} Temporarily Disabled
          </h3>
          <p className="text-sm text-slate-600 mt-1">
            This module has been temporarily disabled via real-time feature flags. It will
            automatically reappear here as soon as an administrator re-enables it.
          </p>
        </div>

        {isAdmin && (
          <div className="pt-2 flex flex-wrap items-center justify-center gap-2.5">
            <button
              type="button"
              onClick={handleEnableFeature}
              className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition"
            >
              Re-enable {featureLabel}
            </button>
            <button
              type="button"
              onClick={() => navigate("/admin")}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-bold transition"
            >
              <Wrench className="w-3.5 h-3.5" />
              Feature Flag Controls
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
