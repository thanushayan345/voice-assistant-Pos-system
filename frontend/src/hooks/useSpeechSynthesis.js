import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * Browser native SpeechSynthesis hook with automatic Tamil voice selection
 * (ta-LK / ta-IN / ta) and safe fallback when speech synthesis is unavailable.
 */
export function useSpeechSynthesis({ enabled = true, preferredVoiceURI = "" } = {}) {
  const isSupported =
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance !== "undefined";

  const [voices, setVoices] = useState([]);
  const [isSpeaking, setIsSpeaking] = useState(false);

  useEffect(() => {
    if (!isSupported) return undefined;

    const loadVoices = () => {
      const available = window.speechSynthesis.getVoices() || [];
      setVoices(available);
    };

    loadVoices();
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", loadVoices);
      window.speechSynthesis.cancel();
    };
  }, [isSupported]);

  const tamilVoices = useMemo(
    () =>
      voices.filter(
        (v) =>
          v.lang?.toLowerCase().startsWith("ta") ||
          v.name?.toLowerCase().includes("tamil") ||
          v.name?.toLowerCase().includes("valluvar")
      ),
    [voices]
  );

  const hasTamilVoice = tamilVoices.length > 0;

  const stopSpeaking = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, [isSupported]);

  const speak = useCallback(
    (text, langHint = "en") => {
      if (!isSupported || !enabled || !text) return;

      try {
        window.speechSynthesis.cancel();

        const containsTamil = /[\u0B80-\u0BFF]/.test(text);
        const targetTamil = langHint?.toLowerCase().startsWith("ta") || containsTamil;

        const utterance = new window.SpeechSynthesisUtterance(text);

        let chosenVoice = null;
        if (preferredVoiceURI) {
          chosenVoice = voices.find((v) => v.voiceURI === preferredVoiceURI) || null;
        }

        if (!chosenVoice) {
          if (targetTamil) {
            chosenVoice =
              tamilVoices.find((v) => v.lang?.toLowerCase() === "ta-lk") ||
              tamilVoices.find((v) => v.lang?.toLowerCase() === "ta-in") ||
              tamilVoices[0] ||
              null;
            utterance.lang = chosenVoice?.lang || "ta-LK";
          } else {
            chosenVoice =
              voices.find((v) => v.lang?.toLowerCase() === "en-lk") ||
              voices.find((v) => v.lang?.toLowerCase() === "en-in") ||
              voices.find((v) => v.lang?.toLowerCase().startsWith("en")) ||
              null;
            utterance.lang = chosenVoice?.lang || "en-US";
          }
        } else {
          utterance.lang = chosenVoice.lang;
        }

        if (chosenVoice) {
          utterance.voice = chosenVoice;
        }

        utterance.rate = 0.98;
        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);

        window.speechSynthesis.speak(utterance);
      } catch {
        setIsSpeaking(false);
      }
    },
    [enabled, isSupported, preferredVoiceURI, tamilVoices, voices]
  );

  return {
    isSupported,
    voices,
    tamilVoices,
    hasTamilVoice,
    isSpeaking,
    speak,
    stopSpeaking,
  };
}
