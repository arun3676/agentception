import { useEffect, useState } from "react";
import { Link, NavLink as RouterNavLink, useLocation } from "react-router-dom";
import {
  Search,
  Map,
  FileText,
  Target,
  Sparkles,
  Scissors,
  BookOpen,
  GraduationCap,
  Menu,
  X,
  Activity,
  ArrowUpRight,
  type LucideIcon,
} from "lucide-react";

// Only routes with a live backend are linked. Beta surfaces remain reachable by URL
// but stay out of the primary navigation until their APIs are production-ready.
const navItems = [
  { label: "Search", href: "/", icon: Search, end: true },
  { label: "Study", href: "/resources", icon: BookOpen },
  { label: "Roadmap", href: "/learning-paths", icon: GraduationCap },
  { label: "Applications", href: "/applications", icon: FileText },
  { label: "Skill Gaps", href: "/skill-gaps", icon: Target },
] satisfies Array<{ label: string; href: string; icon: LucideIcon; end?: boolean }>;

const quickActions = [
  { label: "Tailor Resume", href: "/tailor-resume", icon: Scissors },
  { label: "Saved Paths", href: "/dashboard", icon: Map },
];

const navClass = ({ isActive }: { isActive: boolean }) =>
  [
    "group flex min-h-11 items-center gap-3 rounded-xl px-3.5 text-sm font-semibold transition-all",
    isActive
      ? "bg-foreground text-background shadow-sm"
      : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground",
  ].join(" ");

const quickClass = ({ isActive }: { isActive: boolean }) =>
  [
    "group flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors",
    isActive
      ? "bg-accent/10 font-semibold text-accent"
      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
  ].join(" ");

const Brand = ({ onClick }: { onClick?: () => void }) => (
  <Link to="/" className="flex items-center gap-2.5" onClick={onClick}>
    <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-foreground text-background">
      <Sparkles className="h-[18px] w-[18px]" />
    </span>
    <span className="font-[Manrope] text-[15px] font-extrabold tracking-[-0.045em]">agentception</span>
  </Link>
);

export const TopNav = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, []);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 px-4 py-3 backdrop-blur-xl lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <Brand />
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-accent sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" /> Live
            </span>
            <button
              onClick={() => setMobileOpen(true)}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-card text-foreground"
              aria-label="Open menu"
              aria-expanded={mobileOpen}
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      {mobileOpen && (
        <>
          <button
            className="fixed inset-0 z-50 bg-foreground/45 backdrop-blur-sm lg:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu backdrop"
          />
          <aside className="animate-slide-in-right fixed inset-y-0 right-0 z-50 flex w-[min(88vw,340px)] flex-col border-l border-border bg-background shadow-2xl lg:hidden">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <Brand onClick={() => setMobileOpen(false)} />
              <button
                onClick={() => setMobileOpen(false)}
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-card"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-6">
              <p className="section-label mb-3">Workspace</p>
              <nav className="space-y-1.5">
                {navItems.map((item) => (
                  <RouterNavLink key={item.href} to={item.href} end={item.end} className={navClass}>
                    <item.icon className="h-[18px] w-[18px]" />
                    <span>{item.label}</span>
                  </RouterNavLink>
                ))}
              </nav>

              <p className="section-label mb-3 mt-8">Quick moves</p>
              <nav className="space-y-1">
                {quickActions.map((item) => (
                  <RouterNavLink key={item.href} to={item.href} className={quickClass}>
                    <item.icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </RouterNavLink>
                ))}
              </nav>
            </div>

            <div className="border-t border-border p-5">
              <div className="rounded-xl border border-accent/25 bg-accent/10 p-4">
                <div className="flex items-center gap-2 text-xs font-bold text-accent"><Activity className="h-4 w-4" /> Career loop live</div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">Your next search can feed the roadmap and application loop.</p>
              </div>
            </div>
          </aside>
        </>
      )}

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[17rem] flex-col border-r border-border bg-background px-5 py-6 lg:flex">
        <div className="px-2"><Brand /></div>

        <div className="mt-9">
          <p className="section-label mb-3 px-3">Workspace</p>
          <nav className="space-y-1.5">
            {navItems.map((item) => (
              <RouterNavLink key={item.href} to={item.href} end={item.end} className={navClass}>
                <item.icon className="h-[18px] w-[18px]" />
                <span>{item.label}</span>
              </RouterNavLink>
            ))}
          </nav>
        </div>

        <div className="mt-8">
          <p className="section-label mb-3 px-3">Quick moves</p>
          <nav className="space-y-1">
            {quickActions.map((item) => (
              <RouterNavLink key={item.href} to={item.href} className={quickClass}>
                <item.icon className="h-4 w-4" />
                <span>{item.label}</span>
              </RouterNavLink>
            ))}
          </nav>
        </div>

        <div className="mt-auto rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-xs font-bold"><Activity className="h-4 w-4 text-accent" /> Career loop</span>
            <span className="h-2 w-2 rounded-full bg-accent shadow-[0_0_0_4px_hsl(var(--accent)/0.12)]" />
          </div>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">Live roles, learning paths, and outcomes stay connected.</p>
          <Link to="/applications" className="mt-3 flex items-center gap-1 text-xs font-bold text-foreground">
            View outcomes <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </aside>

      <nav className="pb-safe fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-border bg-background/95 px-2 backdrop-blur-xl lg:hidden">
        {navItems.slice(0, 4).map((item) => (
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
                <item.icon className={`h-[19px] w-[19px] ${isActive ? "text-accent" : ""}`} />
                <span className="max-w-full truncate">{item.label}</span>
              </>
            )}
          </RouterNavLink>
        ))}
        <button onClick={() => setMobileOpen(true)} className="flex min-h-[58px] flex-col items-center justify-center gap-1 rounded-xl text-[10px] font-semibold text-muted-foreground">
          <Menu className="h-[19px] w-[19px]" />
          <span>More</span>
        </button>
      </nav>
    </>
  );
};
