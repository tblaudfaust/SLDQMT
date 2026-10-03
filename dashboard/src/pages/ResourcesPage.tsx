import { useQuery } from "@tanstack/react-query";
import { BookOpen, Download, ExternalLink, FileText, Smartphone } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { openResource, type Resource } from "../api/resources";
import { Card, ErrorBox, Spinner } from "../components/ui";

const icons: Record<string, JSX.Element> = {
  pdf: <BookOpen size={28} className="text-navy" />,
  docx: <FileText size={28} className="text-navy" />,
  apk: <Smartphone size={28} className="text-emerald-700" />,
};

export default function ResourcesPage() {
  const q = useQuery({ queryKey: ["resources"], queryFn: () => api.get<Resource[]>("/resources") });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const act = async (r: Resource) => {
    setError(null);
    setBusy(r.key);
    try {
      await openResource(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="mb-1 text-2xl font-bold">User's manuals &amp; App</h1>
        <p className="text-sm text-slate-500">The user manual and the tablet app for Field Monitors. Available to signed-in users only; each download is recorded in the audit log.</p>
      </div>
      <ErrorBox error={error} />
      {q.isLoading ? (
        <Spinner />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {(q.data ?? []).map((r) => (
            <Card key={r.key}>
              <div className="flex gap-4">
                <div className="shrink-0 pt-1">{icons[r.kind]}</div>
                <div className="flex-1">
                  <h2 className="text-lg font-semibold">{r.title}</h2>
                  {!r.available && <p className="mt-1 text-xs text-slate-500">Not uploaded yet</p>}
                  <div className="mt-3">
                    <button className="btn-primary" disabled={!r.available || busy === r.key} onClick={() => act(r)}>
                      {r.opens_in_tab ? <ExternalLink size={16} /> : <Download size={16} />}
                      {busy === r.key ? "Preparing…" : r.opens_in_tab ? "Open in a new tab" : "Download"}
                    </button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
      <Card>
        <h2 className="text-lg font-semibold">Installing the tablet app</h2>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
          <li>On the tablet, sign in to this dashboard in Chrome and tap <b>Download</b> on the tablet app above. Alternatively download it on a computer and copy the APK to the tablet by USB cable.</li>
          <li>Open the downloaded file from the notification or from the Files app. If asked, allow installation from this source, then tap <b>Install</b>.</li>
          <li>Open the app, allow Location and Notifications, sign in once with the Field Monitor's username and password while online, then choose a 6-digit PIN.</li>
        </ol>
        <p className="mt-3 text-sm text-slate-600">Field Monitor accounts work on the tablet only, so a District DQM or administrator downloads the app and manual for the monitors in their district.</p>
      </Card>
    </div>
  );
}
