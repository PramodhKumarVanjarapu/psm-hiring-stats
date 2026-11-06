import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { Button, Field, Input, Note } from "../components/ui";

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-full place-items-center px-4 py-12">
      <div className="w-full max-w-sm">
        <svg viewBox="0 0 32 32" className="mb-6 h-10 w-10" aria-hidden>
          <rect x="2" y="5" width="28" height="4" rx="1" fill="var(--st-ta)" />
          <rect x="5" y="11" width="22" height="4" rx="1" fill="var(--st-rs)" />
          <rect x="8" y="17" width="16" height="4" rx="1" fill="var(--st-sc)" />
          <rect x="11" y="23" width="10" height="4" rx="1" fill="var(--st-sp)" />
        </svg>
        <h1 className="text-2xl font-semibold tracking-tight">Log in to Hiring funnel</h1>
        <p className="mt-1 mb-6 text-sm text-muted">Placement funnel stats for every job, company and student.</p>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email">
            <Input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password">
            <Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          {error && <Note tone="bad">{error}</Note>}
          <Button type="submit" variant="primary" className="w-full" disabled={busy}>{busy ? "Logging in…" : "Log in"}</Button>
        </form>
        <p className="mt-6 text-xs text-muted">No account? Ask an admin to add you.</p>
      </div>
    </div>
  );
}
