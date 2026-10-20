"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { token } = await api.login(password);
      setToken(token);
      router.replace("/");
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <main className="login-wrap">
      <section className="login-art">
        <div className="login-art-inner">
          <p className="login-brand">Lder</p>
          <h1>A daily hello, in their own language.</h1>
          <p className="login-lede">
            Lder asks your parents how they are every day, in spoken Malayalam. You hear about it the moment something is
            wrong, wherever in the world you are.
          </p>
          <ul className="login-points">
            <li>A short voice question, answered by voice</li>
            <li>Quiet alerts to family, only when it matters</li>
            <li>Their consent, their pace, and a way to stop at any time</li>
          </ul>
        </div>
      </section>
      <section className="login-panel">
        <form onSubmit={submit} className="login-form">
          <h2>Welcome back</h2>
          <p className="hint">Enter the family password to see your dashboard.</p>
          <label className="field">
            <span>Family password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus required />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn btn-primary btn-wide" disabled={busy}>
            {busy ? "Signing in" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
