import React from "react";
import {
  Mic,
  Volume2,
  Server,
  User,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { useConfig } from "../context/ConfigContext";
import { useAuth } from "../context/AuthContext";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import { formatCurrency } from "../utils/formatters";

export default function SettingsPage() {
  const {
    config,
    refreshConfig,
    voiceLanguage,
    setVoiceLanguage,
    resetVoiceLanguageToDefault,
    ttsEnabled,
    setTtsEnabled,
    preferredVoiceURI,
    setPreferredVoiceURI,
  } = useConfig();

  const { user } = useAuth();
  const { isSupported: sttSupported } = useSpeechRecognition({
    language: voiceLanguage,
  });
  const {
    isSupported: ttsSupported,
    voices,
    speak,
  } = useSpeechSynthesis({
    enabled: true,
    preferredVoiceURI,
  });

  const sym = config.currency_symbol || "Rs.";

  const handleTestVoice = () => {
    speak("Hello! Voice POS audio synthesis is ready.", "en");
  };

  return (
    <div className="space-y-6 w-full">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">
          Configure speech recognition, voice synthesis, and inspect backend environment settings.
        </p>
        <button
          type="button"
          onClick={refreshConfig}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-100"
        >
          <RefreshCw className="w-4 h-4" />
          Reload Config
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Speech & Voice Assistant Preferences */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-5">
          <div className="flex items-center gap-2.5">
            <Mic className="w-5 h-5 text-indigo-600" />
            <h3 className="text-base font-bold text-slate-900">
              Speech Recognition & Text-to-Speech
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1.5">
                Voice Recognition Language
              </label>
              <select
                value={voiceLanguage}
                onChange={(e) => setVoiceLanguage(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-slate-300 text-sm font-semibold bg-white"
              >
                {(config.supported_languages || []).map((opt) => (
                  <option key={opt.code} value={opt.code}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={resetVoiceLanguageToDefault}
                className="mt-1.5 text-xs font-semibold text-indigo-700 hover:underline"
              >
                Reset to backend .env default ({config.language})
              </button>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1.5">
                Voice Synthesis (TTS) Output
              </label>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setTtsEnabled(!ttsEnabled)}
                  className={`px-4 py-3 rounded-xl text-sm font-bold border transition flex-1 ${
                    ttsEnabled
                      ? "bg-indigo-50 border-indigo-300 text-indigo-800"
                      : "bg-slate-100 border-slate-300 text-slate-600"
                  }`}
                >
                  {ttsEnabled ? "Enabled" : "Muted"}
                </button>
                <button
                  type="button"
                  disabled={!ttsSupported}
                  onClick={handleTestVoice}
                  className="inline-flex items-center gap-1.5 px-4 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-bold disabled:opacity-50"
                >
                  <Volume2 className="w-4 h-4" />
                  Test
                </button>
              </div>
            </div>
          </div>

          {ttsSupported && voices.length > 0 && (
            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1.5">
                Preferred Browser Voice (Optional)
              </label>
              <select
                value={preferredVoiceURI}
                onChange={(e) => setPreferredVoiceURI(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm bg-white"
              >
                <option value="">Auto-select default system voice</option>
                {voices.map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name} ({v.lang})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <span className="text-slate-500 block">Web Speech Recognition</span>
              <strong className={sttSupported ? "text-emerald-700" : "text-amber-700"}>
                {sttSupported ? "Supported in Browser" : "Unsupported (Use Manual Input)"}
              </strong>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <span className="text-slate-500 block">SpeechSynthesis API</span>
              <strong className={ttsSupported ? "text-emerald-700" : "text-amber-700"}>
                {ttsSupported ? `Supported (${voices.length} voices)` : "Unsupported"}
              </strong>
            </div>
          </div>
        </div>

        {/* Backend Public Environment Configuration */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
            <div className="flex items-center gap-2.5">
              <Server className="w-5 h-5 text-indigo-600" />
              <h3 className="text-base font-bold text-slate-900">
                Backend Environment Configuration
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-xs text-slate-500 block">Currency (CURRENCY)</span>
                <strong className="text-slate-900">
                  {config.currency} ({sym})
                </strong>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-xs text-slate-500 block">Default Language (LANGUAGE)</span>
                <strong className="text-slate-900">{config.language}</strong>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-xs text-slate-500 block">
                  Low-Stock Default (LOW_STOCK_DEFAULT)
                </span>
                <strong className="text-slate-900">{config.low_stock_default}</strong>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-xs text-slate-500 block">
                  High-Value Alert (BIG_AMOUNT)
                </span>
                <strong className="text-slate-900">
                  {formatCurrency(config.big_amount, sym)}
                </strong>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-xs text-slate-500 block">
                  Gemini Model (GEMINI_MODEL)
                </span>
                <strong className="text-slate-900 font-mono text-xs">
                  {config.gemini_model}
                </strong>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-xs text-slate-500 block">Gemini API Key Status</span>
                {config.ai_configured ? (
                  <span className="inline-flex items-center gap-1 font-bold text-emerald-700 text-xs mt-0.5">
                    <CheckCircle2 className="w-4 h-4" /> Connected
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 font-bold text-amber-700 text-xs mt-0.5">
                    <AlertTriangle className="w-4 h-4" /> Set GEMINI_API_KEY in backend/.env
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
            <div className="flex items-center gap-2.5 mb-3">
              <User className="w-5 h-5 text-indigo-600" />
              <h3 className="text-base font-bold text-slate-900">Signed-In User</h3>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm text-slate-700">
              <div>
                <span className="text-xs text-slate-500 block">Full Name</span>
                <strong>{user?.full_name}</strong>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Username</span>
                <strong>{user?.username}</strong>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Role</span>
                <strong className="capitalize">{user?.role}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
