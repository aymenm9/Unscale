"use client";

import { useState } from "react";

import { Button } from "@/components/ui";
import { errorText, post } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post("/auth/login", { email, password });
      window.location.href = "/home";
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <div className="flex flex-col justify-between bg-ink p-8 text-white md:w-[45%] md:p-12">
        <div className="wide text-[21px] font-extrabold">Ledgerwise</div>
        <div className="my-12">
          <p className="wide text-4xl leading-tight font-extrabold md:text-5xl">
            Your AI sales assistant finds the brands. You approve what goes out.
          </p>
        </div>
        <p className="text-sm text-[#BDBDBD]">Every email goes to a demo inbox. No real prospects are contacted.</p>
      </div>
      <form onSubmit={submit} className="flex flex-1 flex-col justify-center px-6 py-12 md:px-16">
        <div className="w-full max-w-sm">
          <h1 className="wide text-3xl font-extrabold">Log in</h1>
          <label className="mt-8 block font-bold" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2 min-h-11 w-full border-2 border-ink px-3"
          />
          <label className="mt-5 block font-bold" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-2 min-h-11 w-full border-2 border-ink px-3"
          />
          {error && <p className="mt-4 text-red" role="alert">{error}</p>}
          <Button tone="dark" type="submit" disabled={busy} className="mt-6 w-full">
            {busy ? "Logging in…" : "Log in"}
          </Button>
        </div>
      </form>
    </div>
  );
}
