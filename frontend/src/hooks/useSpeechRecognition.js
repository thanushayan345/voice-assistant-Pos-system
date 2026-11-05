import { useCallback, useEffect, useRef, useState } from "react";

const MIC_DEVICE_STORAGE_KEY = "vpos_mic_device_id";

/**
 * Strictly Local Browser Speech Recognition + Live Microphone Volume Meter Hook:
 * - Uses Browser Web Speech API (SpeechRecognition / webkitSpeechRecognition) for Tamil & English.
 * - Uses local Web Audio API (AnalyserNode) to display a real-time 0-100% mic input meter
 *   and detect muted/silent microphones immediately.
 * - Zero external cloud audio uploads.
 */
export function useSpeechRecognition({ language = "en-US", onFinalResult } = {}) {
  const SpeechRecognitionImpl =
    typeof window !== "undefined"
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null;

  const isSupported = Boolean(SpeechRecognitionImpl);

  const onFinalRef = useRef(onFinalResult);
  onFinalRef.current = onFinalResult;

  const recognitionRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const levelIntervalRef = useRef(null);
  const maxDurationTimerRef = useRef(null);
  const finishingRef = useRef(false);

  const finalTextRef = useRef("");
  const interimTextRef = useRef("");
  const peakLevelRef = useRef(0);
  const speechFramesRef = useRef(0);
  const lastVoiceAtRef = useRef(0);

  const [isListening, setIsListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [speechError, setSpeechError] = useState("");
  const [audioLevel, setAudioLevel] = useState(0);
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedDeviceId, setSelectedDeviceIdState] = useState(
    () => localStorage.getItem(MIC_DEVICE_STORAGE_KEY) || ""
  );

  const refreshAudioDevices = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
      return;
    }
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const mics = devices
        .filter((d) => d.kind === "audioinput")
        .map((d, idx) => ({
          deviceId: d.deviceId,
          label: d.label || `Microphone ${idx + 1}`,
        }));
      setAudioDevices(mics);
    } catch {
      // Ignore enumeration errors
    }
  }, []);

  useEffect(() => {
    refreshAudioDevices();
    if (typeof navigator !== "undefined" && navigator.mediaDevices?.addEventListener) {
      navigator.mediaDevices.addEventListener("devicechange", refreshAudioDevices);
      return () => {
        navigator.mediaDevices.removeEventListener("devicechange", refreshAudioDevices);
      };
    }
    return undefined;
  }, [refreshAudioDevices]);

  const setSelectedDeviceId = useCallback((deviceId) => {
    const val = deviceId || "";
    setSelectedDeviceIdState(val);
    if (val) {
      localStorage.setItem(MIC_DEVICE_STORAGE_KEY, val);
    } else {
      localStorage.removeItem(MIC_DEVICE_STORAGE_KEY);
    }
  }, []);

  const cleanupHardware = useCallback(() => {
    if (levelIntervalRef.current) {
      clearInterval(levelIntervalRef.current);
      levelIntervalRef.current = null;
    }
    if (maxDurationTimerRef.current) {
      clearTimeout(maxDurationTimerRef.current);
      maxDurationTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onend = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.stop();
      } catch {
        // Ignore
      }
      recognitionRef.current = null;
    }
    if (mediaStreamRef.current) {
      for (const track of mediaStreamRef.current.getTracks()) {
        try {
          track.stop();
        } catch {
          // Ignore
        }
      }
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch {
        // Ignore
      }
      audioContextRef.current = null;
    }
    setAudioLevel(0);
    setIsListening(false);
  }, []);

  const finishSession = useCallback(() => {
    if (finishingRef.current) return;
    finishingRef.current = true;

    cleanupHardware();

    const capturedText = (finalTextRef.current || interimTextRef.current || "").trim();
    setInterimTranscript("");

    if (capturedText && onFinalRef.current) {
      onFinalRef.current(capturedText);
      return;
    }

    if (peakLevelRef.current < 3) {
      setSpeechError(
        "Microphone volume stayed at 0% (silent). Check that your mic isn't muted (Fn+F4 / Windows Sound settings), or use manual text input below."
      );
    } else {
      setSpeechError(
        "No clear speech was recognized by the browser speech engine. Please use Google Chrome or Microsoft Edge and speak clearly, or type your command below."
      );
    }
  }, [cleanupHardware]);

  const stopListening = useCallback(() => {
    finishSession();
  }, [finishSession]);

  const startListening = useCallback(async () => {
    if (!SpeechRecognitionImpl) {
      setSpeechError(
        "Browser SpeechRecognition is not supported here. Please open in Google Chrome or Microsoft Edge, or type your command below."
      );
      return;
    }

    if (typeof window !== "undefined" && window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // Ignore
      }
    }

    cleanupHardware();
    finishingRef.current = false;
    finalTextRef.current = "";
    interimTextRef.current = "";
    peakLevelRef.current = 0;
    speechFramesRef.current = 0;
    lastVoiceAtRef.current = 0;
    setSpeechError("");
    setInterimTranscript("");

    // Start local Web Audio API volume monitor (purely local, no network)
    if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
      try {
        const audioConstraints = selectedDeviceId
          ? { audio: { deviceId: { exact: selectedDeviceId } } }
          : { audio: true };
        let stream;
        try {
          stream = await navigator.mediaDevices.getUserMedia(audioConstraints);
        } catch {
          stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        }
        mediaStreamRef.current = stream;
        refreshAudioDevices();

        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          const ctx = new AudioCtx();
          if (ctx.state === "suspended") {
            await ctx.resume().catch(() => {});
          }
          const source = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 512;
          source.connect(analyser);
          audioContextRef.current = ctx;

          const dataArray = new Uint8Array(analyser.fftSize);
          levelIntervalRef.current = setInterval(() => {
            analyser.getByteTimeDomainData(dataArray);
            let sumSquares = 0;
            for (let i = 0; i < dataArray.length; i += 1) {
              const norm = (dataArray[i] - 128) / 128;
              sumSquares += norm * norm;
            }
            const rms = Math.sqrt(sumSquares / dataArray.length);
            const scaled = Math.min(100, Math.round(rms * 380));
            setAudioLevel(scaled);
            if (scaled > peakLevelRef.current) {
              peakLevelRef.current = scaled;
            }

            const now = Date.now();
            if (scaled >= 7) {
              speechFramesRef.current += 1;
              lastVoiceAtRef.current = now;
            } else if (
              (finalTextRef.current || interimTextRef.current) &&
              lastVoiceAtRef.current > 0 &&
              now - lastVoiceAtRef.current >= 1500
            ) {
              finishSession();
            }
          }, 80);
        }
      } catch {
        // Proceed with SpeechRecognition even if AudioContext meter couldn't attach
      }
    }

    try {
      const recognition = new SpeechRecognitionImpl();
      recognition.lang = language || "en-US";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

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
          finalTextRef.current = `${finalTextRef.current} ${finalChunk}`.trim();
        }
        interimTextRef.current = interim.trim();
        const combined = `${finalTextRef.current} ${interimTextRef.current}`.trim();
        if (combined) {
          setInterimTranscript(combined);
          lastVoiceAtRef.current = Date.now();
          speechFramesRef.current = Math.max(speechFramesRef.current, 3);
        }
      };

      recognition.onerror = (event) => {
        const hasCaptured = Boolean(
          (finalTextRef.current || interimTextRef.current || "").trim()
        );
        if (hasCaptured) {
          finishSession();
          return;
        }
        cleanupHardware();
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          setSpeechError(
            "Microphone permission was denied. Please allow microphone access in your browser address bar, or use manual text input."
          );
        } else if (event.error === "no-speech") {
          setSpeechError(
            peakLevelRef.current < 3
              ? "Microphone input stayed at 0% (silent). Please unmute your microphone or check Windows Sound input settings."
              : "No speech was recognized. Please speak clearly in Google Chrome or Microsoft Edge, or type your command below."
          );
        } else if (event.error === "language-not-supported") {
          setSpeechError(
            `Browser speech engine does not support '${language}'. Try switching to 'en-US' or type your command.`
          );
        } else if (event.error !== "aborted") {
          setSpeechError(`Speech recognition error (${event.error}). You can also type your command below.`);
        }
      };

      recognition.onend = () => {
        if (!finishingRef.current) {
          finishSession();
        }
      };

      recognitionRef.current = recognition;
      recognition.start();

      maxDurationTimerRef.current = setTimeout(() => {
        finishSession();
      }, 10000);
    } catch {
      cleanupHardware();
      setSpeechError("Could not start microphone recognition. Please try again or type your command.");
    }
  }, [
    SpeechRecognitionImpl,
    cleanupHardware,
    finishSession,
    language,
    refreshAudioDevices,
    selectedDeviceId,
  ]);

  useEffect(() => {
    return () => {
      cleanupHardware();
    };
  }, [cleanupHardware]);

  return {
    isSupported,
    isListening,
    interimTranscript,
    speechError,
    setSpeechError,
    audioLevel,
    audioDevices,
    selectedDeviceId,
    setSelectedDeviceId,
    startListening,
    stopListening,
  };
}
