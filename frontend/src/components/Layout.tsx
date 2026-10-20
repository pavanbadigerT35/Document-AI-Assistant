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
    <div className="min-h-screen bg-white md:flex">
      <header className="flex items-center justify-between bg-rail px-4 py-3 text-white md:hidden">
        <span className="font-serif text-lg">Document learning assistant</span>
        <button className="rounded p-1.5 hover:bg-rail-hover" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} aria-controls="main-nav" onClick={() => setOpen(!open)}>
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>
      <aside id="main-nav" className={`${open ? "block" : "hidden"} flex-col justify-between bg-rail p-5 text-white md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0`}>
        <div>
          <div className="mb-8 hidden items-center gap-3 px-2 md:flex">
            <span className="flex h-10 w-10 items-center justify-center rounded-full border border-white/25 text-white"><BookOpenCheck className="h-5 w-5" aria-hidden /></span>
            <div>
              <p className="font-serif text-lg leading-tight">Document</p>
              <p className="font-serif text-lg leading-tight">learning assistant</p>
            </div>
          </div>
          <p className="eyebrow mb-3 px-3 text-white/55">Your workspace</p>
          <nav aria-label="Main">
            <ul className="space-y-1">
              {NAV.map(({ to, label, icon: Icon, end }) => (
                <li key={to}>
                  <NavLink to={to} end={end} className={({ isActive }) => `flex items-center gap-3 rounded-lg border-l-2 px-3 py-2.5 text-sm transition-colors ${isActive ? "border-white bg-white font-medium text-rail" : "border-transparent text-white/80 hover:bg-rail-hover hover:text-white"}`}>
                    <Icon className="h-4 w-4" aria-hidden /> {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="mt-8 border-t border-rail-line pt-4">
          <p className="eyebrow mb-3 text-white/55">System status</p>
          <BackendStatus />
          <p className="mt-3 text-xs text-white/50">Personal learning prototype. Not an official company system.</p>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-5 py-7 sm:px-8 md:px-12 md:py-12">
        <div className="mx-auto w-full min-w-0 max-w-6xl"><Outlet /></div>
      </main>
    </div>
  );
}
