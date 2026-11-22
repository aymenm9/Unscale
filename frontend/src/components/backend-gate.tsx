"use client";

import { useEffect, useState } from "react";

/* The demo backend runs on Render's free plan, which sleeps after 15 minutes without visits.
   Waking it takes about a minute. Instead of a broken page, show what is happening and
   open the app as soon as the backend answers. */

const SHOW_AFTER_MS = 700; // a warm backend answers faster than this, so no flash
const RETRY_MS = 3000;
const SKIP_FOR_MS = 10 * 60 * 1000; // checked recently in this tab: open the app at once
const KEY = "backend-awake-at";

async function backendAnswers(): Promise<boolean> {
  try {
    const res = await fetch("/api/health", { cache: "no-store", signal: AbortSignal.timeout(15000) });
    if (!res.ok) return false;
    const body = await res.json();
    return body.status === "ok";
  } catch {
    return false; // timeout, proxy error, or Render's own waking page
  }
}

function recentlyAwake(): boolean {
  try {
    return Date.now() - Number(sessionStorage.getItem(KEY) || 0) < SKIP_FOR_MS;
  } catch {
    return false;
  }
}

function rememberAwake() {
  try {
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    // private mode: we just check again next time
  }
}

export default function BackendGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"checking" | "waking" | "ready">("checking");
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    let stopped = false;
    const showTimer = setTimeout(() => !stopped && setState((s) => (s === "checking" ? "waking" : s)), SHOW_AFTER_MS);
    const started = Date.now();
    const clock = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);

    async function poll() {
      if (recentlyAwake()) {
        setState("ready");
        return;
      }
      while (!stopped) {
        if (await backendAnswers()) {
          rememberAwake();
          if (!stopped) setState("ready");
          return;
        }
        await new Promise((r) => setTimeout(r, RETRY_MS));
      }
    }
    poll();

    return () => {
      stopped = true;
      clearTimeout(showTimer);
      clearInterval(clock);
    };
  }, []);

  if (state === "ready") return <>{children}</>;
  if (state === "checking") return null;
  return <WakingScreen seconds={seconds} />;
}

function WakingScreen({ seconds }: { seconds: number }) {
  const slow = seconds >= 120;
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <div className="flex flex-col justify-between bg-ink p-8 text-white md:w-[45%] md:p-12">
        <div className="wide text-[21px] font-extrabold">Ledgerwise</div>
        <p className="wide my-12 text-4xl leading-tight font-extrabold md:text-5xl">
          Waking up the server.
        </p>
        <p className="text-sm text-[#BDBDBD]">Every email goes to a demo inbox. No real prospects are contacted.</p>
      </div>
      <div className="flex flex-1 flex-col justify-center px-6 py-12 md:px-16" role="status" aria-live="polite">
        <div className="w-full max-w-md">
          <h1 className="wide text-3xl font-extrabold">Sorry for the wait</h1>
          <p className="mt-4 leading-relaxed text-ink-2">
            This demo runs its backend on Render&apos;s free plan. It goes to sleep after 15 minutes
            without visits, and the first visit takes about a minute to start it again.
          </p>
          <p className="mt-3 leading-relaxed text-ink-2">The app opens by itself as soon as the backend answers.</p>

          <div className="mt-8 h-2 w-full overflow-hidden bg-rule-soft" aria-hidden="true">
            <div className="wake-bar h-full w-1/3 bg-yellow" />
          </div>
          <p className="mt-3 text-sm text-muted tabular-nums">
            Waiting {seconds}s. Checking again every 3 seconds.
          </p>

          {slow && (
            <p className="mt-6 border-l-4 border-yellow pl-3 text-sm text-ink-2">
              This is taking longer than usual. Refresh the page if nothing happens in the next minute.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
