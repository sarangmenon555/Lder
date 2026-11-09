"use client";

import { useCallback, useRef, useState } from "react";

const TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

export function useRecorder() {
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");

  const start = useCallback(async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = TYPES.find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t));
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      return true;
    } catch {
      setError("The microphone is not available. Allow microphone access, or type the reply instead.");
      return false;
    }
  }, []);

  const stop = useCallback(
    () =>
      new Promise((resolve) => {
        const recorder = recorderRef.current;
        if (!recorder || recorder.state === "inactive") {
          setRecording(false);
          resolve(null);
          return;
        }
        recorder.onstop = () => {
          const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
          if (streamRef.current) streamRef.current.getTracks().forEach((track) => track.stop());
          setRecording(false);
          resolve(blob);
        };
        recorder.stop();
      }),
    []
  );

  return { recording, error, start, stop };
}
