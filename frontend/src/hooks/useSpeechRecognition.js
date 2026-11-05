import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Browser Web Speech API (SpeechRecognition / webkitSpeechRecognition) hook
 * supporting Tamil (ta-LK / ta-IN) and English (en-US) with graceful fallback.
 */
export function useSpeechRecognition({ language = "en-US", onFinalResult } = {}) {
  const SpeechRecognitionImpl =
    typeof window !== "undefined"
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null;

  const isSupported = Boolean(SpeechRecognitionImpl);
  const recognitionRef = useRef(null);
  const onFinalRef = useRef(onFinalResult);
  onFinalRef.current = onFinalResult;

  const [isListening, setIsListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [speechError, setSpeechError] = useState("");

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore already stopped
      }
    }
    setIsListening(false);
  }, []);

  const startListening = useCallback(() => {
    if (!SpeechRecognitionImpl) {
      setSpeechError(
        "Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge, or type your command below."
      );
      return;
    }

    setSpeechError("");
    setInterimTranscript("");

    try {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignore
        }
      }

      const recognition = new SpeechRecognitionImpl();
      recognition.lang = language || "en-US";
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      let finalCaptured = "";

      recognition.onstart = () => {
        setIsListening(true);
        setSpeechError("");
      };

      recognition.onresult = (event) => {
        let interim = "";
        let finalChunk = "";

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const transcriptPiece = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalChunk += transcriptPiece;
          } else {
            interim += transcriptPiece;
          }
        }

        if (finalChunk) {
          finalCaptured = `${finalCaptured} ${finalChunk}`.trim();
          setInterimTranscript(finalCaptured);
        } else {
          setInterimTranscript(interim);
        }
      };

      recognition.onerror = (event) => {
        setIsListening(false);
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          setSpeechError(
            "Microphone permission was denied. Please allow microphone access in your browser address bar, or use manual text input."
          );
        } else if (event.error === "no-speech") {
          setSpeechError(
            "No speech was detected. Please tap the microphone and speak clearly."
          );
        } else if (event.error === "language-not-supported") {
          setSpeechError(
            `Browser speech engine does not support '${language}'. Try switching to 'en-US' or type your command.`
          );
        } else if (event.error === "network") {
          setSpeechError(
            "Browser speech recognition encountered a network error. Check your internet connection or use manual text input."
          );
        } else if (event.error !== "aborted") {
          setSpeechError(`Speech recognition error: ${event.error}`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        if (finalCaptured && onFinalRef.current) {
          const textToSend = finalCaptured;
          finalCaptured = "";
          setInterimTranscript("");
          onFinalRef.current(textToSend);
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      setIsListening(false);
      setSpeechError("Could not start microphone recognition. Please try again or use text input.");
    }
  }, [SpeechRecognitionImpl, language]);

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignore cleanup error
        }
      }
    };
  }, []);

  return {
    isSupported,
    isListening,
    interimTranscript,
    speechError,
    setSpeechError,
    startListening,
    stopListening,
  };
}
