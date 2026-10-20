"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useRecorder } from "@/lib/useRecorder";

const MAX_SECONDS = 60;

function clock(total) {
  const m = Math.floor(total / 60);
  const s = String(total % 60).padStart(2, "0");
  return `${m}:${s}`;
}

export default function SimulatorPage() {
  const { token } = useParams();
  const [state, setState] = useState(null);
  const [prompt, setPrompt] = useState(null);
  const [result, setResult] = useState(null);
  const [phase, setPhase] = useState("loading");
  const [error, setError] = useState("");
  const [typed, setTyped] = useState("");
  const [seconds, setSeconds] = useState(0);
  const { recording, error: micError, start, stop } = useRecorder();
  const audioRef = useRef(null);
  const timerRef = useRef(null);

  const play = useCallback((url) => {
    if (!url || !audioRef.current) return;
    audioRef.current.src = url;
    audioRef.current.play().catch(() => {});
  }, []);

  const load = useCallback(async () => {
    try {
      const s = await api.simState(token);
      setState(s);
      if (s.awaiting) setPrompt(s.awaiting);
      setPhase("ready");
    } catch (err) {
      setError(err.message);
      setPhase("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!recording) {
      setSeconds(0);
      return undefined;
    }
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [recording]);

  const begin = async () => {
    setError("");
    try {
      const p = await api.simStart(token);
      setPrompt(p);
      play(p.audio_url);
    } catch (err) {
      setError(err.message);
    }
  };

  const send = async (form) => {
    setPhase("sending");
    setError("");
    try {
      const r = await api.simReply(token, form);
      setResult(r);
      setPrompt(null);
      setPhase("done");
      play(r.ack_audio_url);
    } catch (err) {
      setError(err.message);
      setPhase("ready");
    }
  };

  const toggleRecording = async () => {
    if (recording) {
      clearTimeout(timerRef.current);
      const blob = await stop();
      if (!blob || blob.size === 0) {
        setError("Nothing was recorded. Please try again.");
        return;
      }
      const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
      const form = new FormData();
      form.append("audio", blob, `reply.${ext}`);
      send(form);
      return;
    }
    const ok = await start();
    if (ok) {
      timerRef.current = setTimeout(async () => {
        const blob = await stop();
        if (blob && blob.size > 0) {
          const form = new FormData();
          form.append("audio", blob, "reply.webm");
          send(form);
        }
      }, MAX_SECONDS * 1000);
    }
  };

  const sendTyped = (event) => {
    event.preventDefault();
    if (!typed.trim()) return;
    const form = new FormData();
    form.append("text", typed.trim());
    setTyped("");
    send(form);
  };

  const optOut = async () => {
    if (!window.confirm("Stop all check-ins? Your family can turn them back on later.")) return;
    await api.simOptOut(token);
    load();
  };

  const reset = () => {
    setResult(null);
    setPhase("ready");
    load();
  };

  const enabled = state && state.consent && state.active;
  const step = phase === "done" ? 3 : prompt ? 2 : 1;

  return (
    <main className="sim">
      <audio ref={audioRef} />
      <header className="sim-top">
        <span className="sim-brand">Lder</span>
      </header>

      <div className="sim-card">
        {phase === "loading" && <p className="sim-note">Loading</p>}
        {phase === "error" && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {state && !state.consent && (
          <p className="sim-note">Check-ins have not been switched on yet. Please ask your family to confirm your consent first.</p>
        )}
        {state && state.consent && !state.active && <p className="sim-note">Check-ins are stopped for you.</p>}

        {enabled && (
          <>
            <ol className="sim-steps" aria-label="Steps">
              <li className={step === 1 ? "now" : "past"}>
                <span>1</span> Hear the question
              </li>
              <li className={step === 2 ? "now" : step > 2 ? "past" : ""}>
                <span>2</span> Say your answer
              </li>
              <li className={step === 3 ? "now" : ""}>
                <span>3</span> All done
              </li>
            </ol>

            {phase !== "done" && (
              <>
                <h1 lang="ml" className="sim-hello">
                  നമസ്കാരം, {state.elder_name}
                </h1>

                {!prompt ? (
                  <>
                    <p className="sim-en">Press the big button to hear today&apos;s question.</p>
                    <button className="sim-start" onClick={begin}>
                      <span lang="ml">ചോദ്യം കേൾക്കാം</span>
                      <small>Hear the question</small>
                    </button>
                  </>
                ) : (
                  <>
                    <div className="sim-question">
                      <p lang="ml" className="sim-ml">
                        {prompt.text_ml}
                      </p>
                      <p className="sim-en">{prompt.text_en}</p>
                      <button className="link-btn" onClick={() => play(prompt.audio_url)} disabled={!prompt.audio_url}>
                        Hear it again
                      </button>
                    </div>

                    <div className="sim-record">
                      <button
                        className={`rec-btn ${recording ? "on" : ""}`}
                        onClick={toggleRecording}
                        disabled={phase === "sending"}
                        aria-pressed={recording}
                      >
                        <span lang="ml">{recording ? "നിർത്താൻ അമർത്തുക" : "സംസാരിക്കാൻ അമർത്തുക"}</span>
                        <small>{recording ? "Press when you have finished" : "Press and speak"}</small>
                      </button>
                      {recording && (
                        <p className="sim-timer" aria-live="polite">
                          Listening {clock(seconds)} of {clock(MAX_SECONDS)}
                        </p>
                      )}
                      {phase === "sending" && <p className="sim-note">Listening to your reply</p>}
                    </div>

                    <details className="sim-type-box">
                      <summary>Prefer to type your answer?</summary>
                      <form onSubmit={sendTyped} className="sim-type">
                        <label className="field">
                          <span>Your answer</span>
                          <input value={typed} onChange={(e) => setTyped(e.target.value)} lang="ml" />
                        </label>
                        <button className="btn btn-primary" disabled={!typed.trim() || phase === "sending"}>
                          Send
                        </button>
                      </form>
                    </details>
                  </>
                )}

                {(error || micError) && (
                  <p className="error" role="alert">
                    {error || micError}
                  </p>
                )}
              </>
            )}

            {phase === "done" && result && (
              <div className="sim-result">
                <p className="sim-thanks" lang="ml">
                  {result.ack_text_ml}
                </p>
                <p className="sim-en">{result.ack_text_en}</p>
                <div className="bubble">
                  <span className="bubble-label">We heard you say</span>
                  <p lang="ml" className="bubble-text">
                    {result.transcript}
                  </p>
                </div>
                {result.family_notified && <p className="notice">Your family has been told.</p>}
                <button className="btn btn-primary btn-big" onClick={reset}>
                  Done
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {enabled && (
        <button className="link-btn" onClick={optOut}>
          Stop check-ins
        </button>
      )}
    </main>
  );
}
