"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { api, type Home } from "@/lib/api";

export default function Nav() {
  const path = usePathname();
  const home = useQuery({ queryKey: ["home"], queryFn: () => api<Home>("/home"), refetchInterval: 10000 });
  const replies = home.data?.waiting.filter((w) => w.kind === "reply").length ?? 0;
  const drafts = home.data?.waiting.filter((w) => w.kind === "draft").length ?? 0;
  const running = home.data?.running;

  const items = [
    { href: "/home", label: "Home" },
    { href: "/campaigns", label: "Campaigns" },
    { href: "/companies", label: "Companies" },
    { href: "/review", label: "Approve drafts", count: drafts },
    { href: "/inbox", label: "Conversations", count: replies },
    { href: "/calls", label: "Calls", count: home.data?.stats.calls },
    { href: "/outbox", label: "Test inbox" },
    { href: "/do-not-contact", label: "Do not contact" },
    { href: "/log", label: "Activity log" },
  ];

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  }

  return (
    <aside aria-label="Main menu" className="flex shrink-0 flex-col bg-ink text-white md:sticky md:top-0 md:h-screen md:w-[232px]">
      <div className="wide flex items-center justify-between px-5 pt-5 pb-3 text-[21px] font-extrabold tracking-tight md:pb-6">
        Ledgerwise
        <button onClick={logout} className="text-xs font-normal text-[#BDBDBD] md:hidden" style={{ fontStretch: "100%" }}>
          Log out
        </button>
      </div>
      <nav className="flex overflow-x-auto md:flex-col md:overflow-visible">
        {items.map((it) => {
          const current = path === it.href || path.startsWith(it.href + "/");
          return (
            <Link
              key={it.href}
              href={it.href}
              aria-current={current ? "page" : undefined}
              className={`flex min-h-11 shrink-0 items-center justify-between gap-3 px-5 py-2.5 whitespace-nowrap no-underline ${
                current ? "bg-yellow font-bold text-ink" : "text-[#D6D6D6] hover:text-white"
              }`}
            >
              {it.label}
              {!!it.count && (
                <span className={current ? "bg-ink px-1.5 text-[13px] font-bold text-yellow" : "text-[13px] text-[#9A9A9A]"}>
                  {it.count}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto hidden p-5 md:block">
        {running ? (
          <p className="mb-2.5 text-[13px] text-[#BDBDBD]">
            {running.name}: {running.message}
          </p>
        ) : (
          <p className="mb-2.5 text-[13px] text-[#BDBDBD]">No search running.</p>
        )}
        <Link href="/campaigns/new" className="flex min-h-11 items-center justify-center bg-yellow font-bold text-ink no-underline">
          New campaign
        </Link>
        <button onClick={logout} className="mt-3 w-full text-left text-[13px] text-[#BDBDBD] hover:text-white">
          Log out {home.data ? `(${home.data.user})` : ""}
        </button>
      </div>
    </aside>
  );
}
