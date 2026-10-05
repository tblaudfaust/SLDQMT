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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy">
      <LoginWatermark />
      <form onSubmit={submit} className="relative w-full max-w-sm space-y-4 rounded-lg bg-white p-8 shadow-lg">
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
        <p className="pt-2 text-center text-xs text-slate-500">The user manual and the tablet app are available after signing in.</p>
      </form>
    </div>
  );
}

/** Decorative, very faint background behind the sign-in card: the census emblem, field staff silhouettes and a caption. */
function LoginWatermark() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none">
      <img src="/census-logo.png" alt="" className="absolute -left-24 top-1/2 hidden w-[560px] -translate-y-1/2 opacity-[0.07] md:block" />
<svg viewBox="0 0 560 300" className="absolute -right-4 bottom-6 hidden w-[540px] text-white opacity-[0.09] lg:block" fill="currentColor">
        {/* three census field staff: a monitor with a tablet, a supervisor pointing, an enumerator with a clipboard */}
        <circle cx="90" cy="50" r="21" />
        <rect x="60" y="78" width="60" height="104" rx="26" />
        <rect x="64" y="170" width="22" height="110" rx="11" />
        <rect x="94" y="170" width="22" height="110" rx="11" />
        <rect x="112" y="106" width="16" height="62" rx="8" transform="rotate(-35 120 137)" />
        <rect x="124" y="134" width="44" height="30" rx="4" transform="rotate(-12 146 149)" />
        <circle cx="250" cy="40" r="21" />
        <rect x="220" y="68" width="60" height="104" rx="26" />
        <rect x="224" y="160" width="22" height="110" rx="11" />
        <rect x="254" y="160" width="22" height="110" rx="11" />
        <rect x="272" y="84" width="16" height="78" rx="8" transform="rotate(-70 280 123)" />
        <circle cx="410" cy="56" r="21" />
        <rect x="380" y="84" width="60" height="104" rx="26" />
        <rect x="384" y="176" width="22" height="110" rx="11" />
        <rect x="414" y="176" width="22" height="110" rx="11" />
        <rect x="432" y="112" width="16" height="56" rx="8" transform="rotate(-20 440 140)" />
        <rect x="446" y="128" width="32" height="42" rx="3" />
        <rect x="454" y="122" width="16" height="9" rx="2" />
        <rect x="0" y="282" width="560" height="4" rx="2" />
        {/* a house and a tree for the enumeration area */}
        <path d="M486 282v-50l34-26 34 26v50z" />
        <circle cx="30" cy="222" r="30" />
        <rect x="26" y="240" width="8" height="42" rx="3" />
      </svg>
      <div className="absolute bottom-8 left-0 right-0 hidden text-center text-[11px] font-semibold uppercase tracking-[0.35em] text-white opacity-[0.22] md:block">
        Census Field Monitoring Staff · SLPHC 2026
      </div>
    </div>
  );
}
