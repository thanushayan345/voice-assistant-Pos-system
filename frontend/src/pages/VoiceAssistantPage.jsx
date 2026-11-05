import React, { useCallback, useEffect, useState } from "react";
import {
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  Square,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sparkles,
  Receipt,
  History,
} from "lucide-react";
import { api } from "../services/api";
import { useConfig } from "../context/ConfigContext";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import ReceiptModal from "../components/ReceiptModal";
import {
  formatCurrency,
  formatDateTime,
  formatQuantity,
} from "../utils/formatters";

const DEMO_COMMANDS = [
  {
    category: "Check Stock",
    prompt: "How much rice is available?",
  },
  {
    category: "Add Stock",
    prompt: "Add 20 bags of rice",
  },
  {
    category: "Record Sale",
    prompt: "Sell 2 kilograms of sugar",
  },
  {
    category: "Check Price",
    prompt: "What is the price of soap?",
  },
  {
    category: "Low Stock Alert",
    prompt: "Show low-stock products",
  },
  {
    category: "Today's Sales",
    prompt: "What are today's sales?",
  },
  {
    category: "Search Product",
    prompt: "Do we have milk in stock?",
  },
];

export default function VoiceAssistantPage() {
  const {
    config,
    refreshConfig,
    voiceLanguage,
    setVoiceLanguage,
    ttsEnabled,
    setTtsEnabled,
    preferredVoiceURI,
  } = useConfig();

  const [manualText, setManualText] = useState("");
  const [processing, setProcessing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [activeResponse, setActiveResponse] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [history, setHistory] = useState([]);
  const [receiptSale, setReceiptSale] = useState(null);

  const sym = config.currency_symbol || "Rs.";

  const {
    isSupported: ttsSupported,
    isSpeaking,
    speak,
    stopSpeaking,
  } = useSpeechSynthesis({
    enabled: ttsEnabled,
    preferredVoiceURI,
  });

  const loadHistory = useCallback(async () => {
    try {
      const items = await api.getVoiceHistory(15);
      setHistory(items);
    } catch {
      // Non-blocking history fetch
    }
  }, []);

  useEffect(() => {
    refreshConfig();
    loadHistory();
  }, [loadHistory, refreshConfig]);

  const submitCommandText = useCallback(
    async (text, langOverride = null) => {
      const cleaned = (text || "").trim();
      if (!cleaned) return;

      setProcessing(true);
      setErrorMsg("");
      stopSpeaking();

      try {
        const res = await api.processVoice(cleaned, langOverride || voiceLanguage);
        setActiveResponse(res);
        setManualText("");
        if (!config.ai_configured) {
          refreshConfig();
        }
        if (res.response_text) {
          speak(res.response_text, "en");
        }
        loadHistory();
      } catch (err) {
        setErrorMsg(err.message || "Failed to process voice command.");
      } finally {
        setProcessing(false);
      }
    },
    [config.ai_configured, loadHistory, refreshConfig, speak, stopSpeaking, voiceLanguage]
  );

  const {
    isSupported: sttSupported,
    isListening,
    interimTranscript,
    speechError,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    language: voiceLanguage,
    onFinalResult: (recognizedText) => {
      submitCommandText(recognizedText, voiceLanguage);
    },
  });

  const handleConfirm = async () => {
    if (!activeResponse?.confirmation_token) return;
    setConfirming(true);
    setErrorMsg("");
    stopSpeaking();

    try {
      const confirmed = await api.confirmVoice(activeResponse.confirmation_token);
      setActiveResponse(confirmed);
      if (confirmed.response_text) {
        speak(confirmed.response_text, "en");
      }
      loadHistory();
    } catch (err) {
      setErrorMsg(err.message || "Confirmation failed.");
    } finally {
      setConfirming(false);
    }
  };

  const handleCancel = async () => {
    if (!activeResponse?.confirmation_token) return;
    setConfirming(true);
    setErrorMsg("");
    stopSpeaking();

    try {
      const cancelled = await api.cancelVoice(activeResponse.confirmation_token);
      setActiveResponse(cancelled);
      if (cancelled.response_text) {
        speak(cancelled.response_text, "en");
      }
      loadHistory();
    } catch (err) {
      setErrorMsg(err.message || "Could not cancel command.");
    } finally {
      setConfirming(false);
    }
  };

  const handleManualSubmit = (e) => {
    e.preventDefault();
    if (!manualText.trim() || processing) return;
    submitCommandText(manualText);
  };

  return (
    <div className="space-y-5 w-full">
      {!config.ai_configured && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-sm text-amber-900">
              <p className="font-bold">Gemini API Key Required</p>
              <p className="text-xs text-amber-800 mt-0.5">
                Add <code className="px-1.5 py-0.5 rounded bg-amber-100 font-mono">GEMINI_API_KEY</code> in{" "}
                <code className="px-1.5 py-0.5 rounded bg-amber-100 font-mono">backend/.env</code>, save the file, and click{" "}
                <strong>Re-check Key</strong>.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={refreshConfig}
            className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold shrink-0 self-start sm:self-center"
          >
            Re-check Key
          </button>
        </div>
      )}

      {/* Full-Screen 2-Column Workspace */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        {/* Left 7 Cols: Voice Control Studio + Live Result */}
        <div className="xl:col-span-7 space-y-5">
          {/* Sleek Voice Control Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
              <div>
                <h3 className="text-lg font-extrabold text-slate-900">
                  AI Voice Command Console
                </h3>
                <p className="text-xs text-slate-500">
                  Speak or type commands to check stock, add inventory, or record sales.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={voiceLanguage}
                  onChange={(e) => setVoiceLanguage(e.target.value)}
                  className="px-3 py-2 rounded-xl border border-slate-300 bg-slate-50 text-xs font-bold text-slate-700"
                >
                  {(config.supported_languages || []).map((langOpt) => (
                    <option key={langOpt.code} value={langOpt.code}>
                      {langOpt.label}
                    </option>
                  ))}
                </select>

                <button
                  type="button"
                  onClick={() => setTtsEnabled(!ttsEnabled)}
                  className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-bold transition ${
                    ttsEnabled
                      ? "bg-indigo-50 border-indigo-200 text-indigo-800"
                      : "bg-white border-slate-300 text-slate-600"
                  }`}
                >
                  {ttsEnabled ? (
                    <>
                      <Volume2 className="w-3.5 h-3.5 text-indigo-600" />
                      Audio ON
                    </>
                  ) : (
                    <>
                      <VolumeX className="w-3.5 h-3.5 text-slate-400" />
                      Muted
                    </>
                  )}
                </button>

                {isSpeaking && (
                  <button
                    type="button"
                    onClick={stopSpeaking}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold"
                  >
                    <Square className="w-3 h-3 fill-current" />
                    Stop
                  </button>
                )}
              </div>
            </div>

            {/* Horizontal Mic + Status Row */}
            <div className="flex flex-col sm:flex-row items-center gap-6 py-2">
              <div className="relative flex items-center justify-center shrink-0">
                {isListening && (
                  <>
                    <span className="absolute w-24 h-24 rounded-full bg-rose-400/40 animate-voice-ring" />
                    <span
                      className="absolute w-28 h-28 rounded-full bg-rose-300/30 animate-voice-ring"
                      style={{ animationDelay: "0.4s" }}
                    />
                  </>
                )}

                <button
                  type="button"
                  disabled={processing || !sttSupported}
                  onClick={isListening ? stopListening : startListening}
                  aria-label={isListening ? "Stop listening" : "Start voice command"}
                  className={`relative z-10 w-24 h-24 rounded-2xl flex flex-col items-center justify-center gap-1 shadow-lg transition-transform active:scale-95 disabled:opacity-50 ${
                    isListening
                      ? "bg-rose-600 hover:bg-rose-700 text-white"
                      : "bg-indigo-600 hover:bg-indigo-700 text-white"
                  }`}
                >
                  {isListening ? (
                    <>
                      <MicOff className="w-8 h-8" />
                      <span className="text-[11px] font-extrabold uppercase">Stop</span>
                    </>
                  ) : (
                    <>
                      <Mic className="w-8 h-8" />
                      <span className="text-[11px] font-extrabold uppercase">
                        {processing ? "Wait" : "Speak"}
                      </span>
                    </>
                  )}
                </button>
              </div>

              <div className="flex-1 w-full space-y-3 text-center sm:text-left">
                <div>
                  <p className="text-sm font-bold text-slate-900">
                    {isListening
                      ? "Listening now... Speak clearly into your microphone"
                      : processing
                      ? "Processing command with Google Gemini AI..."
                      : sttSupported
                      ? `Ready for voice input (${voiceLanguage})`
                      : "Browser SpeechRecognition unavailable — type command below"}
                  </p>
                  {interimTranscript && (
                    <p className="mt-1.5 px-3.5 py-2 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-900 text-sm font-semibold">
                      &ldquo;{interimTranscript}&rdquo;
                    </p>
                  )}
                  {speechError && (
                    <p className="mt-1.5 px-3.5 py-2 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-medium">
                      {speechError}
                    </p>
                  )}
                </div>

                {/* Manual Text Input Bar */}
                <form onSubmit={handleManualSubmit} className="flex gap-2">
                  <input
                    type="text"
                    value={manualText}
                    onChange={(e) => setManualText(e.target.value)}
                    disabled={processing}
                    placeholder="Or type a command (e.g., How much rice is available?)"
                    className="flex-1 px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button
                    type="submit"
                    disabled={processing || !manualText.trim()}
                    className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-bold transition disabled:opacity-50 shrink-0"
                  >
                    <Send className="w-4 h-4" />
                    Send
                  </button>
                </form>
              </div>
            </div>
          </div>

          {/* Error Alert */}
          {errorMsg && (
            <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm font-medium flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="font-bold">Voice Command Error</p>
                <p className="mt-0.5 break-words">{errorMsg}</p>
              </div>
            </div>
          )}

          {/* Active AI Response & Confirmation Card */}
          {activeResponse && (
            <div
              className={`rounded-2xl border-2 p-6 shadow-xs transition ${
                activeResponse.requires_confirmation
                  ? "bg-amber-50/70 border-amber-300"
                  : activeResponse.status === "CANCELLED"
                  ? "bg-white border-slate-300"
                  : "bg-emerald-50/60 border-emerald-300"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-3 py-1 rounded-full bg-white border border-slate-200 text-xs font-extrabold text-slate-800">
                    Intent: {activeResponse.intent}
                  </span>
                  <span className="px-2.5 py-1 rounded-full bg-white/80 text-xs font-semibold text-slate-600">
                    Confidence: {Math.round((activeResponse.confidence || 0) * 100)}%
                  </span>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                      activeResponse.status === "PENDING_CONFIRMATION"
                        ? "bg-amber-200 text-amber-900"
                        : activeResponse.status === "CONFIRMED" ||
                          activeResponse.status === "COMPLETED"
                        ? "bg-emerald-200 text-emerald-900"
                        : "bg-slate-200 text-slate-800"
                    }`}
                  >
                    {activeResponse.status}
                  </span>
                </div>

                {ttsSupported && activeResponse.response_text && (
                  <button
                    type="button"
                    onClick={() => speak(activeResponse.response_text, "en")}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-100"
                  >
                    <Volume2 className="w-3.5 h-3.5 text-indigo-600" />
                    Read Aloud
                  </button>
                )}
              </div>

              <p className="text-xs text-slate-500">
                Command: <span className="font-semibold text-slate-800">&ldquo;{activeResponse.transcript}&rdquo;</span>
              </p>

              <p className="text-lg font-extrabold text-slate-900 leading-snug mt-2">
                {activeResponse.response_text}
              </p>

              {activeResponse.is_big_amount_warning && (
                <div className="mt-4 p-3.5 rounded-xl bg-rose-100 border border-rose-300 text-rose-900 text-xs font-bold flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  High-Value Transaction Alert: Exceeds {formatCurrency(config.big_amount, sym)} threshold!
                </div>
              )}

              {activeResponse.data?.operation && (
                <div className="mt-4 p-4 rounded-xl bg-white border border-slate-200 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <span className="text-slate-500 block">Product</span>
                    <strong className="text-slate-900 text-sm">
                      {activeResponse.data.product_name}
                    </strong>
                  </div>
                  {activeResponse.data.quantity !== undefined && (
                    <div>
                      <span className="text-slate-500 block">Quantity</span>
                      <strong className="text-slate-900 text-sm">
                        {formatQuantity(activeResponse.data.quantity)} {activeResponse.data.unit}
                      </strong>
                    </div>
                  )}
                  {activeResponse.data.projected_stock !== undefined && (
                    <div>
                      <span className="text-slate-500 block">Stock Update</span>
                      <strong className="text-indigo-700 text-sm">
                        {formatQuantity(activeResponse.data.current_stock)} →{" "}
                        {formatQuantity(activeResponse.data.projected_stock)} {activeResponse.data.unit}
                      </strong>
                    </div>
                  )}
                  {activeResponse.data.total_amount !== undefined && (
                    <div>
                      <span className="text-slate-500 block">Bill Total</span>
                      <strong className="text-emerald-700 text-sm">
                        {formatCurrency(activeResponse.data.total_amount, sym)}
                      </strong>
                    </div>
                  )}
                </div>
              )}

              {activeResponse.requires_confirmation &&
                activeResponse.status === "PENDING_CONFIRMATION" && (
                  <div className="mt-5 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      disabled={confirming}
                      onClick={handleConfirm}
                      className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-sm shadow-sm transition disabled:opacity-50"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      {confirming ? "Executing..." : "Confirm"}
                    </button>
                    <button
                      type="button"
                      disabled={confirming}
                      onClick={handleCancel}
                      className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white hover:bg-rose-50 text-rose-700 border border-rose-300 font-extrabold text-sm transition disabled:opacity-50"
                    >
                      <XCircle className="w-4 h-4" />
                      Cancel
                    </button>
                  </div>
                )}

              {activeResponse.data?.sale && (
                <div className="mt-4">
                  <button
                    type="button"
                    onClick={() => setReceiptSale(activeResponse.data.sale)}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-xs"
                  >
                    <Receipt className="w-4 h-4" />
                    View / Print Receipt ({activeResponse.data.sale.invoice_number})
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Recent Voice Command Log */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
            <div className="flex items-center gap-2 mb-3">
              <History className="w-4 h-4 text-slate-600" />
              <h3 className="text-sm font-bold text-slate-900">Recent Voice Command Log</h3>
            </div>

            {history.length === 0 ? (
              <p className="text-xs text-slate-500 py-4 text-center">
                No voice commands recorded yet.
              </p>
            ) : (
              <div className="divide-y divide-slate-100 max-h-64 overflow-y-auto">
                {history.map((item) => (
                  <div
                    key={item.id}
                    className="py-2.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-bold text-slate-900">
                          &ldquo;{item.transcript}&rdquo;
                        </span>
                        <span className="px-2 py-0.5 rounded-md bg-slate-100 text-[10px] font-bold text-slate-700">
                          {item.intent}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            item.status === "CONFIRMED" || item.status === "COMPLETED"
                              ? "bg-emerald-100 text-emerald-800"
                              : item.status === "PENDING_CONFIRMATION"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {item.status}
                        </span>
                      </div>
                      {item.response_text && (
                        <p className="text-xs text-slate-500 mt-0.5 truncate">
                          {item.response_text}
                        </p>
                      )}
                    </div>
                    <span className="text-[11px] text-slate-400 shrink-0">
                      {formatDateTime(item.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right 5 Cols: Quick Sample Voice Commands */}
        <div className="xl:col-span-5 bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-5 h-5 text-indigo-600" />
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Quick Voice Commands
              </h3>
              <p className="text-xs text-slate-500">
                Click any command below to test live AI processing
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2.5">
            {DEMO_COMMANDS.map((cmd) => (
              <button
                key={cmd.category}
                type="button"
                disabled={processing}
                onClick={() => submitCommandText(cmd.prompt, "en-US")}
                className="w-full text-left p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-indigo-50 hover:border-indigo-300 transition flex items-center justify-between gap-3 group disabled:opacity-50"
              >
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 block">
                    {cmd.category}
                  </span>
                  <span className="text-sm font-bold text-slate-900">
                    &ldquo;{cmd.prompt}&rdquo;
                  </span>
                </div>
                <span className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-xs font-bold text-slate-600 group-hover:bg-indigo-600 group-hover:text-white group-hover:border-indigo-600 transition shrink-0">
                  Run
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <ReceiptModal sale={receiptSale} onClose={() => setReceiptSale(null)} />
    </div>
  );
}
