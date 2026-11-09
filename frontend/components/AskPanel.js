"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function AskPanel({ elderId, elderName }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const suggestions = [
    `How has ${elderName} been this week?`,
    "Has any medicine been missed?",
    "Is there anything I should be worried about?",
  ];

  const ask = async (text) => {
    const value = text.trim();
    if (value.length < 2) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.ask(elderId, value));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const submit = (event) => {
    event.preventDefault();
    ask(question);
  };

  return (
    <section className="card block" aria-label={`Ask about ${elderName}`}>
      <h2>Ask about {elderName}</h2>
      <p className="hint">
        The answer is written from the real check-in records. It is not medical advice. If you are worried, call them.
      </p>
      <div className="chips">
        {suggestions.map((text) => (
          <button
            key={text}
            type="button"
            className="chip chip-mute"
            disabled={busy}
            onClick={() => {
              setQuestion(text);
              ask(text);
            }}
          >
            {text}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="btn-row">
        <input
          type="text"
          value={question}
          maxLength={500}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={`Ask a question about ${elderName}`}
          aria-label="Your question"
          style={{ flex: 1, minWidth: 220 }}
        />
        <button className="btn btn-primary" type="submit" disabled={busy || question.trim().length < 2}>
          {busy ? "Looking" : "Ask"}
        </button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {result && (
        <div role="status">
          <p>{result.answer}</p>
          <p className="hint">
            Answered by {result.gateway?.model || "an open model"} through Otari
            {result.mode === "mcp" ? " using the check-in tools" : ""}.
          </p>
        </div>
      )}
    </section>
  );
}
