import LiquidBackground from "./LiquidBackground";
import { ReactNode } from "react";
export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <LiquidBackground />
      <header className="sticky top-0 z-10 backdrop-blur-md bg-panel/70 border-b border-white/5">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
          <div className="font-semibold tracking-wide">Agentception</div>
          <div className="text-sm text-sub">AI Engineer Job Search Assistant</div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
