import { useState } from "react";
import { Link } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function Signup() {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [message, setMessage] = useState(""); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); if (!supabase) return setError("Authentication is not configured yet."); setLoading(true); setError(""); const { error: authError } = await supabase.auth.signUp({ email, password }); setLoading(false); if (authError) return setError(authError.message); setMessage("Check your inbox to confirm your email, then sign in."); };
  return <main className="grid min-h-screen place-items-center bg-background p-5"><form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-2xl border border-border bg-card p-7 shadow-sm"><div><p className="text-sm font-bold text-accent">Agentception</p><h1 className="mt-2 text-3xl font-bold tracking-tight">Build your career workspace</h1><p className="mt-2 text-sm text-muted-foreground">Save roles, keep resume versions private, and learn from every application.</p></div><Input aria-label="Email" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required /><Input aria-label="Password" type="password" placeholder="Create a password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />{error && <p className="text-sm text-destructive">{error}</p>}{message && <p className="text-sm text-accent">{message}</p>}<Button className="w-full" disabled={loading}>{loading ? "Creating account…" : "Create account"}</Button><p className="text-center text-sm text-muted-foreground">Already have an account? <Link className="font-semibold text-foreground underline" to="/login">Sign in</Link></p></form></main>;
}
