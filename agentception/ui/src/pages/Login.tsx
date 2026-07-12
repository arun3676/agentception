import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function Login() {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const navigate = useNavigate(); const location = useLocation();
  const submit = async (event: React.FormEvent) => { event.preventDefault(); if (!supabase) return setError("Authentication is not configured yet."); setLoading(true); setError(""); const { error: authError } = await supabase.auth.signInWithPassword({ email, password }); setLoading(false); if (authError) return setError(authError.message); navigate((location.state as { from?: Location })?.from?.pathname || "/dashboard", { replace: true }); };
  return <main className="grid min-h-screen place-items-center bg-background p-5"><form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-2xl border border-border bg-card p-7 shadow-sm"><div><p className="text-sm font-bold text-accent">Agentception</p><h1 className="mt-2 text-3xl font-bold tracking-tight">Welcome back</h1><p className="mt-2 text-sm text-muted-foreground">Your job search, evidence, and applications in one place.</p></div><Input aria-label="Email" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required /><Input aria-label="Password" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />{error && <p className="text-sm text-destructive">{error}</p>}<Button className="w-full" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</Button><p className="text-center text-sm text-muted-foreground">New here? <Link className="font-semibold text-foreground underline" to="/signup">Create an account</Link></p></form></main>;
}
