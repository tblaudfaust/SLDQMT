import type { CreatedAccount } from "../api/types";
import { Card } from "./ui";

/** Accounts just created with their initial passwords, shown once with a CSV download. */
export default function CreatedAccountsCard({ title, created, existing, note, onClose }: { title?: string; created: CreatedAccount[]; existing?: number; note?: string; onClose: () => void }) {
  const download = () => {
    const lines = ["username,staff_code,role,district,password", ...created.map((c) => [c.username, c.staff_code, c.role, c.district, c.password].join(","))];
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `officer-accounts-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  return (
    <Card title={title ?? `${created.length} account${created.length === 1 ? "" : "s"} created`} className="mb-4" action={<button className="text-sm text-slate-500" onClick={onClose}>Close</button>}>
      <p className="text-sm text-slate-700">
        {existing ? `${existing} officers already had an account. ` : ""}{note ?? ""} The initial passwords below are shown only now: download the file and hand each officer their password. Officers sign in with the staff code as username, then choose a tablet PIN (Field Monitors) or change the password (DQM).
      </p>
      {created.length > 0 && (
        <>
          <button className="btn-primary mt-3" onClick={download}>Download passwords (CSV)</button>
          <div className="mt-3 max-h-72 overflow-auto">
            <table className="table">
              <thead><tr><th>Username / staff code</th><th>Role</th><th>District</th><th>Initial password</th></tr></thead>
              <tbody>{created.map((c) => <tr key={c.username}><td className="font-medium">{c.staff_code}</td><td>{c.role === "FIELD_MONITOR" ? "Field Monitor" : "District DQM"}</td><td>{c.district}</td><td className="font-mono">{c.password}</td></tr>)}</tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
