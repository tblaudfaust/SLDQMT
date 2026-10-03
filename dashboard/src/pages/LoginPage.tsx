import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox } from "../components/ui";

export default function LoginPage() {
  const { user, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-navy">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-lg bg-white p-8 shadow-lg">
        <div className="flex flex-col items-center text-center">
          <img src="/statsl-logo.png" alt="Statistics Sierra Leone" className="mb-3 h-28 w-28" />
          <div className="text-sm font-semibold text-navy">Statistics Sierra Leone</div>
          <div className="mt-2 text-xs uppercase tracking-wider text-slate-500">SLPHC 2026</div>
          <h1 className="text-xl font-bold">Field Monitor Error Follow-up</h1>
          <p className="text-sm text-slate-500">Dashboard and reports</p>
        </div>
        <input className="input" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <input className="input" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <ErrorBox error={error} />
        <button className="btn-primary w-full justify-center" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="pt-2 text-center text-xs text-slate-500">
          Field Monitors: <a href="/downloads/" className="font-medium text-navy underline">download the tablet app and the user manual</a>
        </p>
      </form>
    </div>
  );
}
