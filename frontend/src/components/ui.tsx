// Shared pieces in the D style. Plain components, no UI library.

import Link from "next/link";

export function when(iso: string | null | undefined) {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins >= 0 && mins < 60) return mins <= 1 ? "Just now" : `${mins} min ago`;
  if (mins >= 0 && mins < 60 * 24) return `${Math.round(mins / 60)}h ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function PageHeader({
  title,
  sub,
  back,
  children,
}: {
  title: string;
  sub?: React.ReactNode;
  back?: { href: string; label: string };
  children?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        {back && (
          <Link
            href={back.href}
            className="group inline-flex min-h-9 items-center gap-2 border-2 border-ink px-3 text-sm font-bold text-ink no-underline hover:bg-ink hover:text-yellow"
          >
            <span aria-hidden className="transition-transform group-hover:-translate-x-0.5">
              ←
            </span>
            Back to {back.label}
          </Link>
        )}
        <h1 className="wide mt-3 text-4xl font-extrabold leading-none tracking-tight md:text-[44px]">{title}</h1>
        {sub && <p className="mt-2.5 text-[17px] text-ink-2">{sub}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </header>
  );
}

export function Button({
  tone = "line",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "dark" | "line" | "yellow" | "quiet" }) {
  const tones = {
    dark: "bg-ink text-white border-2 border-ink font-bold",
    line: "bg-transparent text-ink border-2 border-ink",
    yellow: "bg-yellow text-ink border-2 border-yellow font-bold",
    quiet: "bg-transparent text-ink border-2 border-rule",
  };
  return (
    <button
      {...props}
      className={`inline-flex min-h-11 items-center justify-center gap-2 px-4 disabled:cursor-not-allowed disabled:opacity-40 ${tones[tone]} ${className}`}
    />
  );
}

export function Stats({ items }: { items: { n: number | string; label: string }[] }) {
  return (
    <div className="mt-6 flex flex-wrap border-y-2 border-ink">
      {items.map((x, i) => (
        <div key={x.label} className={`min-w-[120px] flex-1 py-3.5 pr-5 ${i ? "border-l border-rule pl-5" : ""}`}>
          <div className="semi-wide text-[32px] font-extrabold leading-none tabular-nums">{x.n}</div>
          <div className="mt-1 text-[13px] text-muted">{x.label}</div>
        </div>
      ))}
    </div>
  );
}

export function Progress({ done, total, label, note }: { done: number; total: number; label: string; note?: string }) {
  const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
  return (
    <div>
      <div className="flex justify-between gap-3 text-sm">
        <span className="font-bold">{label}</span>
        <span className="tabular-nums">{total ? `${done} of ${total}` : ""}</span>
      </div>
      <div className="mt-1.5 h-2.5 bg-rule-soft" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-2.5 bg-ink transition-[width]" style={{ width: `${pct}%` }} />
      </div>
      {note && <p className="mt-1.5 text-[13px] text-muted">{note}</p>}
    </div>
  );
}

const STOPS = ["Researched", "Qualified", "Emailed", "Replied", "Call booked"];
const SHORT = ["Found", "Scored", "Emailed", "Replied", "Booked"];

/** B's parcel-tracking line: where a company is on the 5 stops. */
export function Track({ step, out = false, small = false, labels = true }: { step: number; out?: boolean; small?: boolean; labels?: boolean }) {
  const color = out ? "#8A8A8A" : "#000";
  const big = small ? 16 : 22;
  const dot = small ? 8 : 12;
  return (
    <div aria-label={`Step ${step} of 5: ${STOPS[step - 1]}`}>
      <div className="grid grid-cols-5 items-center">
        {STOPS.map((label, i) => {
          const n = i + 1;
          const done = n <= step;
          const current = n === step;
          return (
            <div key={label} className="relative flex h-[22px] items-center">
              {i > 0 && (
                <span
                  className="absolute right-1/2 -left-1/2 h-[3px]"
                  style={{ top: small ? 7 : 10, background: done ? color : "#D0D0D0" }}
                />
              )}
              <span
                className="relative z-10 box-border rounded-full"
                style={
                  current
                    ? { width: big, height: big, background: out ? "#8A8A8A" : "#FFC600", border: `3px solid ${color}` }
                    : {
                        width: dot,
                        height: dot,
                        marginLeft: (big - dot) / 2,
                        background: done ? color : "#fff",
                        border: `2px solid ${done ? color : "#D0D0D0"}`,
                      }
                }
              />
            </div>
          );
        })}
      </div>
      {labels && (
        <div className="mt-1 grid grid-cols-5 text-[11px] leading-tight">
          {SHORT.map((label, i) => (
            <span key={label} title={STOPS[i]} className={`min-w-0 truncate pr-1 ${i + 1 === step ? "font-bold" : i + 1 < step ? "" : "text-faint"}`}>
              {label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** D's small 5-segment progress bar. */
export function Bars({ step, out = false }: { step: number; out?: boolean }) {
  return (
    <span className="flex gap-0.5" aria-label={`Step ${step} of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className="h-1.5 w-3.5" style={{ background: i <= step ? (out ? "#9A9A9A" : "#000") : "#D0D0D0" }} />
      ))}
    </span>
  );
}

export function NeedsYou() {
  return <span className="bg-ink px-2 py-px text-[13px] font-bold text-yellow">Needs you</span>;
}

const THREAD_TAG: Record<string, [string, string]> = {
  needs_human: ["Needs you", "bg-ink text-yellow px-2 font-bold"],
  open: ["Agent handling", ""],
  booked: ["Call booked", "bg-blue text-white px-2 font-bold"],
  suppressed: ["Opted out", "text-muted line-through"],
  closed: ["Closed", "text-muted"],
};

export function ThreadTag({ status, mode }: { status: string; mode?: string }) {
  const [label, cls] =
    status === "open" && mode === "human" ? ["You're handling", "border border-ink px-1.5"] : (THREAD_TAG[status] ?? [status, ""]);
  return <span className={`py-px text-[13px] ${cls}`}>{label}</span>;
}

export function Score({ value, verdict }: { value: number | null; verdict: string | null }) {
  if (value === null) return <span className="text-faint">—</span>;
  const cls =
    verdict === "good" ? "bg-ink text-white" : verdict === "maybe" ? "bg-yellow text-ink" : "border border-faint text-muted";
  return <span className={`inline-block min-w-9 px-1.5 py-0.5 text-center font-bold tabular-nums ${cls}`}>{value}</span>;
}

export function Checks({ checks }: { checks: { name: string; passed: boolean; detail: string }[] }) {
  return (
    <ul className="grid gap-1 text-sm">
      {checks.map((c) => (
        <li key={c.name} className="flex gap-2">
          <span aria-hidden className={c.passed ? "font-bold" : "font-bold text-red"}>
            {c.passed ? "✓" : "✕"}
          </span>
          <span className={c.passed ? "text-ink-2" : "text-red"}>{c.detail}</span>
        </li>
      ))}
    </ul>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="border-t-2 border-ink py-8 text-[17px] text-ink-2">{children}</div>;
}

export function Loading() {
  return <p className="py-10 text-muted">Loading…</p>;
}

export function Tabs<T extends string>({
  value,
  onChange,
  items,
}: {
  value: T;
  onChange: (v: T) => void;
  items: { key: T; label: string }[];
}) {
  return (
    <div role="tablist" className="flex flex-wrap gap-2">
      {items.map((t) => {
        const on = t.key === value;
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={on}
            onClick={() => onChange(t.key)}
            className={`min-h-9 border-2 px-3.5 ${on ? "border-ink bg-ink font-bold text-white" : "border-rule bg-white"}`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

/** Email body with [n] markers turned into small source links. */
export function Cited({ body, citations }: { body: string; citations: { url: string; quote: string }[] }) {
  const parts = body.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        if (!m) return <span key={i}>{p}</span>;
        const c = citations[Number(m[1]) - 1];
        return c ? (
          <a key={i} href={c.url} target="_blank" rel="noreferrer" title={c.quote} className="align-super text-[11px] font-bold">
            [{m[1]}]
          </a>
        ) : (
          <span key={i} className="align-super text-[11px] text-red">
            {p}
          </span>
        );
      })}
    </>
  );
}

/** What the reply agent did, in plain words. */
export const ACTION: Record<string, string> = {
  send: "Replied on its own",
  book: "Booked a call",
  suppress: "Added to Do not contact",
  handoff: "Asked you to step in",
  none: "Did nothing",
};
