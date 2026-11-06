import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import type { Dashboard } from "../types";
import { cx } from "./ui";

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <svg viewBox="0 0 32 32" className="h-6 w-6" aria-hidden>
        <rect x="2" y="5" width="28" height="4" rx="1" fill="var(--st-ta)" />
        <rect x="5" y="11" width="22" height="4" rx="1" fill="var(--st-rs)" />
        <rect x="8" y="17" width="16" height="4" rx="1" fill="var(--st-sc)" />
        <rect x="11" y="23" width="10" height="4" rx="1" fill="var(--st-sp)" />
      </svg>
      <span className="text-[15px] font-semibold text-ink">Hiring funnel</span>
    </div>
  );
}

export function Layout() {
  const { user, logout, can } = useAuth();
  const [open, setOpen] = useState(false);
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/api/v1/dashboard"), staleTime: 60_000 });
  const conflicts = dash.data?.open_conflicts ?? 0;

  const links = [
    { to: "/", label: "Overview", end: true },
    ...(can("editor") ? [{ to: "/analyses/new", label: "New analysis" }] : []),
    { to: "/jobs", label: "Jobs" },
    { to: "/companies", label: "Companies" },
    { to: "/students", label: "Students" },
    { to: "/conflicts", label: "Identity conflicts", badge: conflicts },
    { to: "/settings", label: "Settings" },
  ];

  const nav = (
    <nav className="flex flex-col gap-0.5" aria-label="Main">
      {links.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          end={"end" in l ? l.end : false}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            cx("flex items-center justify-between rounded-md px-3 py-2 text-sm transition",
              isActive ? "bg-sunken font-semibold text-ink" : "text-muted hover:bg-sunken hover:text-ink")
          }
        >
          {l.label}
          {"badge" in l && l.badge ? (
            <span className="num rounded-full bg-warn-bg px-2 text-xs font-semibold text-warn">{l.badge}</span>
          ) : null}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-full lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="hidden border-r border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:p-4">
        <div className="mb-6 pt-1"><Brand /></div>
        {nav}
        <div className="mt-auto border-t border-line pt-4 text-sm">
          <div className="truncate font-medium text-ink">{user?.name || user?.email}</div>
          <div className="mb-2 text-xs capitalize text-muted">{user?.role}</div>
          <button onClick={logout} className="text-sm text-primary hover:underline">Log out</button>
        </div>
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-surface px-4 py-3 lg:hidden">
        <Brand />
        <button onClick={() => setOpen(!open)} aria-expanded={open} className="rounded-md border border-line px-3 py-1.5 text-sm">
          {open ? "Close" : "Menu"}
        </button>
      </header>
      {open && (
        <div className="border-b border-line bg-surface p-3 lg:hidden">
          {nav}
          <button onClick={logout} className="mt-2 px-3 text-sm text-primary">Log out</button>
        </div>
      )}

      <main className="min-w-0 px-4 py-6 sm:px-8 lg:py-8">
        <div className="mx-auto max-w-[1240px]">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
