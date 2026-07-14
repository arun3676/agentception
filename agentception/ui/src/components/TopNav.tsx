import { useEffect, useRef, useState } from "react";
import { Link, NavLink as RouterNavLink, useLocation } from "react-router-dom";
import { BookOpen, LockKeyhole, Menu, Search, Sparkles, X, type LucideIcon } from "lucide-react";

const navItems = [
  { label: "Search", href: "/", icon: Search, end: true },
  { label: "Study", href: "/resources", icon: BookOpen },
  { label: "Feature status", href: "/dashboard", icon: LockKeyhole },
] satisfies Array<{ label: string; href: string; icon: LucideIcon; end?: boolean }>;

const navClass = ({ isActive }: { isActive: boolean }) =>
  [
    "group flex min-h-11 items-center gap-3 rounded-xl px-3.5 text-sm font-semibold transition-all",
    isActive
      ? "bg-foreground text-background shadow-sm"
      : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground",
  ].join(" ");

const Brand = ({ onClick }: { onClick?: () => void }) => (
  <Link to="/" className="flex items-center gap-2.5" onClick={onClick}>
    <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-foreground text-background">
      <Sparkles className="h-[18px] w-[18px]" aria-hidden="true" />
    </span>
    <span className="font-[Manrope] text-[15px] font-extrabold tracking-[-0.045em]">agentception</span>
  </Link>
);

export const TopNav = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => setMobileOpen(false), [location.pathname]);

  useEffect(() => {
    if (mobileOpen) closeButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [mobileOpen]);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 px-4 py-3 backdrop-blur-xl lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <Brand />
          <button
            onClick={() => setMobileOpen(true)}
            className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-card text-foreground"
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
            aria-controls="mobile-navigation"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </header>

      {mobileOpen && (
        <>
          <button
            className="fixed inset-0 z-50 bg-foreground/45 backdrop-blur-sm lg:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          />
          <aside
            id="mobile-navigation"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="animate-slide-in-right fixed inset-y-0 right-0 z-50 flex w-[min(88vw,340px)] flex-col border-l border-border bg-background shadow-2xl lg:hidden"
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <Brand onClick={() => setMobileOpen(false)} />
              <button
                ref={closeButtonRef}
                onClick={() => setMobileOpen(false)}
                className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-card"
                aria-label="Close navigation"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <nav className="flex-1 space-y-1.5 overflow-y-auto px-5 py-6" aria-label="Primary navigation">
              {navItems.map((item) => (
                <RouterNavLink key={item.href} to={item.href} end={item.end} className={navClass}>
                  <item.icon className="h-[18px] w-[18px]" aria-hidden="true" />
                  <span>{item.label}</span>
                </RouterNavLink>
              ))}
            </nav>
            <p className="border-t border-border p-5 text-xs leading-5 text-muted-foreground">
              Resume and saved workspace features are unavailable until private account ownership is verified.
            </p>
          </aside>
        </>
      )}

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[17rem] flex-col border-r border-border bg-background px-5 py-6 lg:flex">
        <div className="px-2"><Brand /></div>
        <nav className="mt-9 space-y-1.5" aria-label="Primary navigation">
          {navItems.map((item) => (
            <RouterNavLink key={item.href} to={item.href} end={item.end} className={navClass}>
              <item.icon className="h-[18px] w-[18px]" aria-hidden="true" />
              <span>{item.label}</span>
            </RouterNavLink>
          ))}
        </nav>
        <div className="mt-auto rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2 text-xs font-bold">
            <LockKeyhole className="h-4 w-4 text-muted-foreground" aria-hidden="true" /> Private features paused
          </div>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">Public search does not collect resume data.</p>
        </div>
      </aside>

      <nav className="pb-safe fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 border-t border-border bg-background/95 px-2 backdrop-blur-xl lg:hidden" aria-label="Mobile navigation">
        {navItems.map((item) => (
          <RouterNavLink
            key={item.href}
            to={item.href}
            end={item.end}
            className={({ isActive }) => [
              "relative flex min-h-[58px] flex-col items-center justify-center gap-1 rounded-xl text-[10px] font-semibold",
              isActive ? "text-foreground" : "text-muted-foreground",
            ].join(" ")}
          >
            {({ isActive }) => (
              <>
                <item.icon className={`h-[19px] w-[19px] ${isActive ? "text-accent" : ""}`} aria-hidden="true" />
                <span className="max-w-full truncate">{item.label}</span>
              </>
            )}
          </RouterNavLink>
        ))}
      </nav>
    </>
  );
};
