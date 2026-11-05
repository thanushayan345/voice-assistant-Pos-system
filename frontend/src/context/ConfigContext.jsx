import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../services/api";

const ConfigContext = createContext(null);

const VOICE_LANG_OVERRIDE_KEY = "vpos_voice_lang_override";
const TTS_ENABLED_KEY = "vpos_tts_enabled";
const PREFERRED_VOICE_URI_KEY = "vpos_preferred_voice_uri";

const FALLBACK_CONFIG = {
  app_name: "Voice POS",
  currency: "LKR",
  currency_symbol: "Rs.",
  language: "en-US",
  supported_languages: [
    { code: "en-US", label: "English (US)" },
    { code: "en-GB", label: "English (UK)" },
    { code: "en-IN", label: "English (South Asia)" },
  ],
  low_stock_default: 5,
  big_amount: 50000,
  gemini_model: "gemini-3.8-flash",
  ai_configured: false,
  supported_units: [
    "Pieces",
    "Kilograms",
    "Grams",
    "Litres",
    "Bottles",
    "Packets",
    "Boxes",
    "Bags",
  ],
};

export function ConfigProvider({ children }) {
  const [config, setConfig] = useState(FALLBACK_CONFIG);
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [voiceLanguage, setVoiceLanguageState] = useState(
    () => localStorage.getItem(VOICE_LANG_OVERRIDE_KEY) || ""
  );
  const [ttsEnabled, setTtsEnabledState] = useState(() => {
    const saved = localStorage.getItem(TTS_ENABLED_KEY);
    return saved === null ? true : saved === "true";
  });
  const [preferredVoiceURI, setPreferredVoiceURIState] = useState(
    () => localStorage.getItem(PREFERRED_VOICE_URI_KEY) || ""
  );

  const refreshConfig = useCallback(async () => {
    try {
      const remoteConfig = await api.getConfig();
      setConfig(remoteConfig);
      setVoiceLanguageState((prev) => prev || remoteConfig.language || "en-US");
    } catch {
      setVoiceLanguageState((prev) => prev || FALLBACK_CONFIG.language);
    } finally {
      setLoadingConfig(false);
    }
  }, []);

  useEffect(() => {
    refreshConfig();
  }, [refreshConfig]);

  const setVoiceLanguage = useCallback((langCode) => {
    setVoiceLanguageState(langCode);
    localStorage.setItem(VOICE_LANG_OVERRIDE_KEY, langCode);
  }, []);

  const resetVoiceLanguageToDefault = useCallback(() => {
    localStorage.removeItem(VOICE_LANG_OVERRIDE_KEY);
    setVoiceLanguageState(config.language || "en-US");
  }, [config.language]);

  const setTtsEnabled = useCallback((enabled) => {
    setTtsEnabledState(Boolean(enabled));
    localStorage.setItem(TTS_ENABLED_KEY, String(Boolean(enabled)));
  }, []);

  const setPreferredVoiceURI = useCallback((uri) => {
    setPreferredVoiceURIState(uri || "");
    if (uri) {
      localStorage.setItem(PREFERRED_VOICE_URI_KEY, uri);
    } else {
      localStorage.removeItem(PREFERRED_VOICE_URI_KEY);
    }
  }, []);

  const activeLanguage = voiceLanguage || config.language || "en-US";

  return (
    <ConfigContext.Provider
      value={{
        config,
        loadingConfig,
        refreshConfig,
        voiceLanguage: activeLanguage,
        setVoiceLanguage,
        resetVoiceLanguageToDefault,
        ttsEnabled,
        setTtsEnabled,
        preferredVoiceURI,
        setPreferredVoiceURI,
      }}
    >
      {children}
    </ConfigContext.Provider>
  );
}

export function useConfig() {
  const ctx = useContext(ConfigContext);
  if (!ctx) {
    throw new Error("useConfig must be used inside ConfigProvider");
  }
  return ctx;
}
