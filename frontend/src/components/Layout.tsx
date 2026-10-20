import { BookOpenCheck, FileText, LayoutDashboard, ListTree, Menu, MessageSquareText, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api/client";
import type { ReadyInfo } from "../types";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/library", label: "Document library", icon: FileText },
  { to: "/search", label: "Knowledge search", icon: Search },
  { to: "/chat", label: "AI chat", icon: MessageSquareText },
  { to: "/topics", label: "Topic explorer", icon: ListTree },
  { to: "/quiz", label: "Quiz and revision", icon: BookOpenCheck },
];

function BackendStatus() {
  const [info, setInfo] = useState<ReadyInfo | null | "offline">(null);
  useEffect(() => { api.ready().then(setInfo).catch(() => setInfo("offline")); }, []);
  if (info === null) return <p className="text-xs text-white/60">Checking backend…</p>;
  if (info === "offline") return <p className="text-xs text-red-200">Backend offline. Start it, then reload.</p>;
  const llm = info.checks.llm;
  return (
    <div className="space-y-1 text-xs text-white/70">
      <p>Embeddings: {info.checks.embeddings.model.split("/").pop()} (local)</p>
      <p>{llm.configured ? `Chat model: ${llm.model}` : "Chat model: not configured"}</p>
    </div>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  return (
    <div className="min-h-screen md:flex">
      <header className="flex items-center justify-between bg-rail px-4 py-3 text-white md:hidden">
        <span className="font-serif text-lg font-semibold">Document learning assistant</span>
        <button className="rounded p-1.5 hover:bg-rail-hover" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} aria-controls="main-nav" onClick={() => setOpen(!open)}>
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>
      <aside id="main-nav" className={`${open ? "block" : "hidden"} flex-col justify-between bg-rail p-4 text-white md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0`}>
        <div>
          <p className="mb-6 hidden px-2 font-serif text-xl font-semibold leading-tight md:block">Document learning assistant</p>
          <nav aria-label="Main">
            <ul className="space-y-1">
              {NAV.map(({ to, label, icon: Icon, end }) => (
                <li key={to}>
                  <NavLink to={to} end={end} className={({ isActive }) => `flex items-center gap-3 rounded-md px-3 py-2 text-sm ${isActive ? "bg-white font-medium text-rail" : "text-white/85 hover:bg-rail-hover"}`}>
                    <Icon className="h-4 w-4" aria-hidden /> {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="mt-6 border-t border-rail-line pt-4">
          <BackendStatus />
          <p className="mt-3 text-xs text-white/50">Personal learning prototype. Not an official company system.</p>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-10">
        <div className="mx-auto max-w-4xl"><Outlet /></div>
      </main>
    </div>
  );
}
