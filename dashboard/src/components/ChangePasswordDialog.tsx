import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../api/client";
import { ErrorBox } from "./ui";

/** Self-service password change for the signed-in user. */
export default function ChangePasswordDialog({ onClose, forced = false }: { onClose: () => void; forced?: boolean }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const change = useMutation({ mutationFn: () => api.post("/auth/change-password", { current_password: current, new_password: next }), onSuccess: () => setDone(true) });
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={forced ? undefined : onClose}>
      <div className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-3 text-lg font-bold">{forced ? "Choose your own password" : "Change my password"}</h2>
        {forced && !done && <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">This account was created or reset by an administrator. Choose a new password before continuing.</p>}
        {done ? (
          <div><p className="text-sm text-green-700">Password changed.</p><div className="mt-3 flex justify-end"><button className="btn-primary" onClick={onClose}>Close</button></div></div>
        ) : (
          <div className="space-y-3">
            <input className="input" type="password" placeholder="Current password" value={current} onChange={(e) => setCurrent(e.target.value)} />
            <input className="input" type="password" placeholder="New password (min 8)" value={next} onChange={(e) => setNext(e.target.value)} />
            <input className="input" type="password" placeholder="Repeat new password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            {next && confirm && next !== confirm && <p className="text-sm text-red-700">The new passwords do not match.</p>}
            <ErrorBox error={change.error instanceof ApiError ? change.error.message : change.error} />
            <div className="flex justify-end gap-2">{!forced && <button className="btn-outline" onClick={onClose}>Cancel</button>}<button className="btn-primary" disabled={!current || next.length < 8 || next !== confirm || change.isPending} onClick={() => change.mutate()}>Change password</button></div>
          </div>
        )}
      </div>
    </div>
  );
}
